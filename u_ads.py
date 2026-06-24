import time
import queue

import lgpio
import spidev


SYNC_RESET_PIN = 18
DRDY_PIN = 25

SPI_BUS = 0
SPI_DEVICE = 0
SPI_SPEED_HZ = 8_000_000
SPI_MODE = 0b01

FRAME_SIZE = 30


class ADS131M08:
    def __init__(self):
        # SPI 설정
        self.spi = spidev.SpiDev()
        self.spi.open(SPI_BUS, SPI_DEVICE)
        self.spi.max_speed_hz = SPI_SPEED_HZ
        self.spi.mode = SPI_MODE
        self.spi.bits_per_word = 8
        self.spi.lsbfirst = False

        # 수집 상태 (디버깅 변수)
        self.spi_busy    = False
        self.drdy_count  = 0
        self.frame_count = 0
        self.missed_drdy = 0

        # GPIO 설정
        self.gpio_handle = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(self.gpio_handle, SYNC_RESET_PIN, 1)

        # DRDY callback은 init() 성공 후 등록
        self.callback = None

        # 최근 수신 프레임
        self.rx_buf    = tuple([0] * FRAME_SIZE)
        self.zero_frame = [0x00] * FRAME_SIZE

        # CSV 저장용 Queue
        self.data_queue = queue.Queue()

    def _send_command(self, opcode):
        tx = [
            (opcode >> 8) & 0xFF,
            opcode & 0xFF,
            0x00
        ]
        rx = self.spi.xfer2(tx)
        time.sleep(0.001)
        return (rx[0] << 8) | rx[1]

    def _read_reg(self, reg):
        command = 0xA000 | ((reg & 0x3F) << 7)
        self._send_command(command)
        return self._send_command(0x0000)

    def _write_reg(self, reg, data):
        command = 0x6000 | ((reg & 0x3F) << 7)
        tx = [
            (command >> 8) & 0xFF,
            command & 0xFF,
            0x00,
            (data >> 8) & 0xFF,
            data & 0xFF,
            0x00
        ]
        self.spi.xfer2(tx)

        wreg_ack     = self._send_command(0x0000)
        expected_ack = 0x4000 | ((reg & 0x3F) << 7)

        if wreg_ack != expected_ack:
            raise RuntimeError(
                f"WREG 0x{reg:02X} ACK 오류: "
                f"0x{wreg_ack:04X}, "
                f"기대값 0x{expected_ack:04X}"
            )

        readback = self._read_reg(reg)

        if readback != data:
            raise RuntimeError(
                f"REG 0x{reg:02X} 검증 오류: "
                f"0x{readback:04X}, "
                f"기대값 0x{data:04X}"
            )

        return readback

    def _toggle_reset(self):
        lgpio.gpio_write(self.gpio_handle, SYNC_RESET_PIN, 0)
        time.sleep(0.001)
        lgpio.gpio_write(self.gpio_handle, SYNC_RESET_PIN, 1)
        time.sleep(0.001)

    def init(self):
        time.sleep(0.050)
        lgpio.gpio_write(self.gpio_handle, SYNC_RESET_PIN, 1)

        self._toggle_reset()

        reset_ack      = self._send_command(0x0000)
        initial_status = self._send_command(0x0000)

        if reset_ack != 0xFF28:
            raise RuntimeError(
                f"RESET ACK 오류: "
                f"0x{reset_ack:04X}, 기대값 0xFF28"
            )

        mode = self._write_reg(0x02, 0x0510)

        device_id = self._read_reg(0x00)

        if (device_id & 0xFF00) != 0x2800:
            raise RuntimeError(
                f"ID 오류: "
                f"0x{device_id:04X}, 기대값 0x28xx"
            )

# CH0: raw -2500 → OCAL = -2500 = 0xFFF63C
        self._write_reg(0x0A, 0xFFF6)
        self._write_reg(0x0B, 0x3C00)

# CH1: raw -2500 → OCAL = -2500 = 0xFFF63C
        self._write_reg(0x0F, 0xFFF6)
        self._write_reg(0x10, 0x3C00)

# CH2: raw -3500 → OCAL = -3500 = 0xFFF254
        self._write_reg(0x14, 0xFFF2)
        self._write_reg(0x15, 0x5400)
        # CH3 OCAL
        self._write_reg(0x19, 0xFFF1)
        self._write_reg(0x1A, 0x3400)


        clock = self._write_reg(0x03, 0xFF06)
        gain1 = self._read_reg(0x04)
        gain2 = self._read_reg(0x05)

        print("===========================================")
        print("  ADS131M08 Register Dump")
        print("===========================================")
        print(f"  Reset ACK  = 0x{reset_ack:04X}  (기대값 0xFF28)")
        print(f"  Status Reg = 0x{initial_status:04X}  (기대값 0x05FF)")
        print(f"  MODE       = 0x{mode:04X}  (기대값 0x0510)")
        print(f"  CLOCK      = 0x{clock:04X}  (기대값 0xFF06)")
        print(f"  ID         = 0x{device_id:04X}  (기대값 0x28xx)")
        print(f"  GAIN1      = 0x{gain1:04X}")
        print(f"  GAIN2      = 0x{gain2:04X}")

    def _drdy_callback(self, chip, gpio, level, tick):
        self.drdy_count += 1

        if self.spi_busy:
            self.missed_drdy += 1
            return

        self.spi_busy = True

        try:
            received = self.spi.xfer2(self.zero_frame)
            self.rx_buf = tuple(received)
            self.frame_count += 1
            self.data_queue.put(self.rx_buf)  # Queue에 적재
        finally:
            self.spi_busy = False

    def start_capture(self):
        if self.callback is not None:
            return

        lgpio.gpio_claim_alert(
            self.gpio_handle,
            DRDY_PIN,
            lgpio.FALLING_EDGE
        )

        self.callback = lgpio.callback(
            self.gpio_handle,
            DRDY_PIN,
            lgpio.FALLING_EDGE,
            self._drdy_callback
        )

    def get_latest_frame(self):
        return self.rx_buf, self.frame_count

    def close(self):
        if self.callback is not None:
            self.callback.cancel()
            self.callback = None

        lgpio.gpio_write(self.gpio_handle, SYNC_RESET_PIN, 1)
        lgpio.gpiochip_close(self.gpio_handle)
        self.spi.close()
