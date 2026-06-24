"""
vibration_receiver.py
라즈베리파이 ← RS-485(USB) ← STM32 진동 모듈
보레이트 : 115200
포트     : /dev/ttyUSB0 (환경에 따라 변경)

동작 흐름:
  1. "GET_START" 전송
  2. "START_RAW\n" 수신 대기
  3. 16384줄 수신  (index,x_g,y_g,z_g)
  4. "END_RAW\n"   확인 후 CSV 저장
"""

import serial
import csv
import time
from datetime import datetime

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
PORT = '/dev/ttyAMA1'# ls /dev/ttyUSB* 로 확인
BAUDRATE  = 115200
TIMEOUT   = 5                # 줄 수신 타임아웃 (초)
FFT_LEN   = 16384            # STM32 FFT_LEN 과 동일

# ─────────────────────────────────────────────
# 수신 함수
# ─────────────────────────────────────────────
def receive_raw_data(ser: serial.Serial) -> list:
    """
    STM32에 GET_START 전송 후 RAW 데이터 수신
    반환값: [(index, x_g, y_g, z_g), ...] 리스트
    """
    # 1. 버퍼 비우기
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # 2. GET_START 전송
    print("[TX] GET_START")
    ser.write(b"GET_START")

    # 3. START_RAW 대기
    print("[RX] START_RAW 대기 중...")
    start_time = time.time()
    while True:
        if time.time() - start_time > 10:
            raise TimeoutError("START_RAW 수신 타임아웃 (10초)")
        line = ser.readline().decode("ascii", errors="ignore").strip()
        if line == "START_RAW":
            print("[RX] START_RAW 수신 - 데이터 수신 시작")
            break
        elif line:
            print(f"[RX] (무시) {line}")

    # 4. 16384줄 수신
    data = []
    for i in range(FFT_LEN):
        raw = ser.readline()
        if not raw:
            raise TimeoutError(f"데이터 수신 타임아웃 (index {i})")

        line = raw.decode("ascii", errors="ignore").strip()

        if line == "END_RAW":
            print(f"[RX] END_RAW 조기 수신 (index {i}) - 데이터 부족")
            break

        # 파싱: "0,0.001234,0.002345,0.003456"
        parts = line.split(",")
        if len(parts) != 4:
            print(f"[WARN] 파싱 실패 (index {i}): {line}")
            continue

        try:
            idx = int(parts[0])
            x_g = float(parts[1])
            y_g = float(parts[2])
            z_g = float(parts[3])
            data.append((idx, x_g, y_g, z_g))
        except ValueError:
            print(f"[WARN] 변환 실패 (index {i}): {line}")
            continue

        # 진행률 출력 (512 단위)
        if (i + 1) % 512 == 0:
            print(f"  수신 중... {i + 1}/{FFT_LEN} ({(i+1)/FFT_LEN*100:.0f}%)")

    # 5. END_RAW 확인 (아직 못 받은 경우)
    if len(data) == FFT_LEN:
        end_line = ser.readline().decode("ascii", errors="ignore").strip()
        if end_line == "END_RAW":
            print("[RX] END_RAW 확인 - 수신 완료")
        else:
            print(f"[WARN] END_RAW 대신 수신: {end_line}")

    print(f"[INFO] 총 {len(data)}샘플 수신")
    return data


# ─────────────────────────────────────────────
# CSV 저장 함수
# ─────────────────────────────────────────────
def save_csv(data: list, filename: str = None):
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"vibration_{timestamp}.csv"

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "x_g", "y_g", "z_g"])
        writer.writerows(data)

    print(f"[SAVE] {filename} ({len(data)}행)")
    return filename


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
def main():
    print(f"포트: {PORT}  보레이트: {BAUDRATE}")

    try:
        ser = serial.Serial(
            port     = PORT,
            baudrate = BAUDRATE,
            bytesize = serial.EIGHTBITS,
            parity   = serial.PARITY_NONE,
            stopbits = serial.STOPBITS_ONE,
            timeout  = TIMEOUT,
        )
    except serial.SerialException as e:
        print(f"[ERROR] 포트 열기 실패: {e}")
        print("  → ls /dev/ttyUSB* 로 포트 확인")
        return

    try:
        data = receive_raw_data(ser)
        if data:
            save_csv(data)
    except TimeoutError as e:
        print(f"[ERROR] 타임아웃: {e}")
    except KeyboardInterrupt:
        print("\n[INFO] 사용자 중단")
    finally:
        ser.close()
        print("[INFO] 포트 닫힘")


if __name__ == "__main__":
    main()
