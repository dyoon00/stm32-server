from dataclasses import dataclass


FRAME_SIZE = 30
CHANNEL_COUNT = 8

ADS_VREF = 1.2
ADS_GAIN = 1.0
ADC_FULL_SCALE = 16_777_216.0

# 기존 STM 코드의 전압 분압비
VOLTAGE_DIVIDER = 1321.0

VOLTAGE_LSB = (
    2.0 *
    ADS_VREF *
    VOLTAGE_DIVIDER
) / (
    ADC_FULL_SCALE *
    ADS_GAIN
)


@dataclass(frozen=True)
class ADSFrame:
    status: int
    raw_channels: tuple
    voltage_channels: tuple
    crc: int


def signed_24(
    byte0,
    byte1,
    byte2
):
    value = (
        (byte0 << 16) |
        (byte1 << 8) |
        byte2
    )

    # 24비트 부호 확장
    if value & 0x800000:
        value -= 0x1000000

    return value


def parse_frame(frame):
    if len(frame) != FRAME_SIZE:
        raise ValueError(
            f"프레임 길이 오류: "
            f"{len(frame)}, 기대값 {FRAME_SIZE}"
        )

    # STATUS 상위 16비트
    status = (
        (frame[0] << 8) |
        frame[1]
    )

    channels = []

    # CH0~CH7 파싱
    for channel in range(CHANNEL_COUNT):
        offset = 3 + channel * 3

        value = signed_24(
            frame[offset],
            frame[offset + 1],
            frame[offset + 2]
        )

        channels.append(value)

    # CH0~CH2에 전압 분압비 적용
    voltages = (
        channels[0] * VOLTAGE_LSB,
        channels[1] * VOLTAGE_LSB,
        channels[2] * VOLTAGE_LSB
    )

    # 마지막 3바이트 CRC
    crc = (
        (frame[27] << 16) |
        (frame[28] << 8) |
        frame[29]
    )

    return ADSFrame(
        status=status,
        raw_channels=tuple(channels),
        voltage_channels=voltages,
        crc=crc
    )
