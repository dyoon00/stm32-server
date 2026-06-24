import csv
import threading
import json
import os

FRAME_SIZE    = 30
CHANNEL_COUNT = 8

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

# 전압 채널 상수 (CH0~CH2)
ADS_VREF        = 1.2
ADS_GAIN        = 1.0
ADC_FULL_SCALE  = 16_777_216.0
VOLTAGE_DIVIDER = 1321.0

VOLTAGE_LSB = (2.0 * ADS_VREF * VOLTAGE_DIVIDER) / (ADC_FULL_SCALE * ADS_GAIN)

# 전류 채널 기본값
CURRENT_DIVIDER  = 6.0
SENSITIVITY      = 0.020

# 채널별 기본 오프셋
DEFAULT_OFFSETS = {
    'ch3': 2.5,
    'ch4': 2.5,
    'ch5': 2.5,
    'ch6': 2.5,
    'ch7': 2.5,
}


def load_offsets():
    offsets = DEFAULT_OFFSETS.copy()
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        current = config.get('current', {})
        for ch in ['ch3', 'ch4', 'ch5', 'ch6', 'ch7']:
            key = f'{ch}_offset'
            if key in current:
                offsets[ch] = current[key]
    return offsets


def raw_to_voltage(raw):
    return raw * VOLTAGE_LSB


def raw_to_current(raw, offset):
    adc_voltage    = raw * (2.0 * ADS_VREF) / ADC_FULL_SCALE
    sensor_voltage = adc_voltage * CURRENT_DIVIDER
    print(f"sensor_voltage: {sensor_voltage:.4f}, offset: {offset:.4f}")
    return (sensor_voltage - offset) / SENSITIVITY

class CSVWriter:
    def __init__(self, data_queue, filename='data.csv'):
        self.data_queue  = data_queue
        self.filename    = filename
        self.running     = False
        self.write_count = 0
        self.offsets     = load_offsets()
        self.thread      = threading.Thread(
            target=self._write_loop,
            daemon=True
        )

        print("채널별 오프셋:")
        for ch in ['ch3', 'ch4', 'ch5', 'ch6', 'ch7']:
            print(f"  {ch}: {self.offsets[ch]:.4f} V")

    def start(self):
        self.running = True
        self.thread.start()
        print(f"CSV 저장 시작: {self.filename}")

    def stop(self):
        self.running = False

    def _write_loop(self):
        ch_keys = ['ch3', 'ch4', 'ch5', 'ch6', 'ch7']

        with open(self.filename, 'w', newline='') as f:
            writer = csv.writer(f)

            writer.writerow([
                'frame',
                'ch0_V', 'ch1_V', 'ch2_V',
                'ch3_A', 'ch4_A', 'ch5_A',
                'ch6_A', 'ch7_A'
            ])

            while self.running:
                try:
                    frame = self.data_queue.get(timeout=0.1)

                    channels = []
                    for ch in range(CHANNEL_COUNT):
                        offset = 3 + ch * 3
                        val = (
                            (frame[offset]   << 16) |
                            (frame[offset+1] << 8)  |
                            frame[offset+2]
                        )
                        if val & 0x800000:
                            val -= 0x1000000
                        channels.append(val)

                    row = [self.write_count]

                    # CH0~CH2 전압 변환
                    for ch in range(3):
                        row.append(round(raw_to_voltage(channels[ch]), 4))

                    # CH3~CH7 전류 변환 (채널별 오프셋 적용)
                    for i, ch in enumerate(range(3, 8)):
                        offset = self.offsets[ch_keys[i]]
                        row.append(round(raw_to_current(channels[ch], offset), 4))

                    self.write_count += 1
                    writer.writerow(row)

                except Exception:
                    continue
