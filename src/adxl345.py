from smbus2 import SMBus


I2C_BUS_NUMBER = 1
ADXL345_ADDRESS = 0x53

# Register-Adressen laut ADXL345-Datenblatt
REGISTER_DEVID = 0x00
REGISTER_POWER_CTL = 0x2D
REGISTER_DATA_FORMAT = 0x31
REGISTER_DATAX0 = 0x32

# Skalierungsfaktor im Standardmodus (Full Resolution, +-2g)
GRAVITY_SCALE_FACTOR = 0.0039

EXPECTED_DEVICE_ID = 0xE5


def connect(bus_number: int = I2C_BUS_NUMBER) -> SMBus:
    """Öffnet den I2C-Bus und versetzt den ADXL345 in den Messmodus."""

    bus = SMBus(bus_number)

    device_id = bus.read_byte_data(ADXL345_ADDRESS, REGISTER_DEVID)

    if device_id != EXPECTED_DEVICE_ID:
        raise RuntimeError(
            f"Unerwartete Device-ID: 0x{device_id:02X} "
            f"(erwartet: 0x{EXPECTED_DEVICE_ID:02X}). "
            "Ist wirklich ein ADXL345 an Adresse "
            f"0x{ADXL345_ADDRESS:02X} angeschlossen?"
        )

    # Messmodus aktivieren (Standardzustand nach dem Einschalten ist Standby)
    bus.write_byte_data(ADXL345_ADDRESS, REGISTER_POWER_CTL, 0x08)

    return bus


def read_acceleration_g(bus: SMBus) -> tuple[float, float, float]:
    """Liest die aktuelle Beschleunigung in g für x, y und z."""

    raw_bytes = bus.read_i2c_block_data(
        ADXL345_ADDRESS,
        REGISTER_DATAX0,
        6,
    )

    def to_signed_16bit(low_byte: int, high_byte: int) -> int:
        value = (high_byte << 8) | low_byte

        if value >= 0x8000:
            value -= 0x10000

        return value

    x_raw = to_signed_16bit(raw_bytes[0], raw_bytes[1])
    y_raw = to_signed_16bit(raw_bytes[2], raw_bytes[3])
    z_raw = to_signed_16bit(raw_bytes[4], raw_bytes[5])

    return (
        x_raw * GRAVITY_SCALE_FACTOR,
        y_raw * GRAVITY_SCALE_FACTOR,
        z_raw * GRAVITY_SCALE_FACTOR,
    )
