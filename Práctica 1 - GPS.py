import serial

from parseo_tramas import parsear_gga
from conversion_utm import geograficas_a_utm


def conectar_gps(puerto: str) -> serial.Serial:
    return serial.Serial(
        port=puerto,
        baudrate=4800,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
        timeout=1,
    )


def main() -> None:
    print("Práctica 1 — Lectura GPS (NMEA GGA) → UTM (WGS84)\n")

    puerto = input("Puerto serie (ej: COM8, /dev/ttyUSB0): ").strip()
    huso = 30

    ser = None
    try:
        ser = conectar_gps(puerto)
        print(f"\n[OK] Conectado al receptor GPS en {puerto} (4800 bps, 8N1).")
        print("Leyendo tramas GGA (Ctrl+C para parar)...\n")

        contador_gga = 0

        while True:
            linea = ser.readline().decode("ascii", errors="replace").strip()
            if not linea:
                continue

            if "$GPGGA" not in linea and "$GNGGA" not in linea:
                continue

            contador_gga += 1
            datos = parsear_gga(linea)

            if datos is None or datos.get("calidad_fix", 0) == 0:
                print(f"[Trama {contador_gga}] Sin fix / sin coordenadas aún.")
                continue

            utm = geograficas_a_utm(
                datos["latitud_decimal"],
                datos["longitud_decimal"],
                elipsoide="WGS84",
                huso=huso,
            )

            print(f"--- Trama GGA #{contador_gga} ---")
            print(f"Hora UTC:   {datos['hora_utc']}")
            print(f"Latitud:    {datos['latitud_decimal']:.8f}°")
            print(f"Longitud:   {datos['longitud_decimal']:.8f}°")
            print(f"Calidad:    {datos['calidad_fix']} — {datos['calidad_texto']}")
            print(f"Satélites:  {datos['num_satelites']} | HDOP: {datos['hdop']}")
            print(f"Altitud:    {datos['altitud']} m")
            print(f"UTM (WGS84) — Huso {utm['huso']}")
            print(f"  Easting (X):  {utm['easting']:.3f} m")
            print(f"  Northing (Y): {utm['northing']:.3f} m")
            print()

    except KeyboardInterrupt:
        print("\n[INFO] Detenido por el usuario (Ctrl+C).")
    except serial.SerialException as e:
        print(f"[ERROR] No se pudo abrir/usar el puerto serie: {e}")
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        print("[INFO] Puerto serie cerrado.")


if __name__ == "__main__":
    main()