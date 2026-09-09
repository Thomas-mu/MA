import time

from adxl345 import I2C_BUS_NUMBER, connect, read_acceleration_g


def main() -> None:
    bus = connect()

    print(f"ADXL345 verbunden auf I2C-Bus {I2C_BUS_NUMBER}.")
    print("Messwerte in g (Strg+C zum Beenden):")
    print()

    try:
        while True:
            x_g, y_g, z_g = read_acceleration_g(bus)

            print(
                f"x = {x_g:+.3f} g   "
                f"y = {y_g:+.3f} g   "
                f"z = {z_g:+.3f} g"
            )

            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        bus.close()


if __name__ == "__main__":
    main()
