import time
import json
import os
from u_ads import ADS131M08

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

CURRENT_DIVIDER = 6.0
ADS_VREF        = 1.2
ADC_FULL_SCALE  = 16_777_216.0
SAMPLE_COUNT    = 160000


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {"current": {}}


def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)


def raw_to_sensor_voltage(raw):
    adc_voltage    = raw * (2.0 * ADS_VREF) / ADC_FULL_SCALE
    sensor_voltage = adc_voltage * CURRENT_DIVIDER
    return sensor_voltage


def calibrate_ch3(ads):
    print("CH3 오프셋 교정 시작")
    print("센서를 0A 상태로 유지하세요.")
    input("준비되면 Enter를 누르세요...")

    # Queue 비우기
    while not ads.data_queue.empty():
        ads.data_queue.get()

    print(f"{SAMPLE_COUNT}샘플 측정 중...")

    samples = []
    while len(samples) < SAMPLE_COUNT:
        try:
            frame = ads.data_queue.get(timeout=1.0)
            offset = 3 + 3 * 3  # CH3
            val = (
                (frame[offset]   << 16) |
                (frame[offset+1] << 8)  |
                frame[offset+2]
            )
            if val & 0x800000:
                val -= 0x1000000
            samples.append(val)
        except Exception:
            continue

    avg_raw        = sum(samples) / len(samples)
    sensor_voltage = raw_to_sensor_voltage(avg_raw)

    print(f"수집 샘플 수   : {len(samples)}")
    print(f"CH3 평균 raw   : {avg_raw:.1f}")
    print(f"CH3 오프셋 전압: {sensor_voltage:.4f} V")

    config = load_config()
    config["current"]["ch3_offset"] = round(sensor_voltage, 4)
    save_config(config)

    print(f"config.json 저장 완료: ch3_offset = {sensor_voltage:.4f}")


def main():
    ads = ADS131M08()

    try:
        ads.init()
        ads.start_capture()

        time.sleep(0.5)  # 안정화 대기

        calibrate_ch3(ads)

    except Exception as e:
        print(f"오류: {e}")

    finally:
        ads.close()


if __name__ == "__main__":
    main()
