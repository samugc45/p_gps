import serial
import importlib

# Cargar módulos (tus ficheros con espacios)
nmea_parser = importlib.import_module("Parseo de Tramas NMEA GGA")
conv_utm = importlib.import_module("Conversión a UTC")

parsear_gga = nmea_parser.parsear_gga
geograficas_a_utm = conv_utm.geograficas_a_utm


def conectar_gps(puerto: str):
    return serial.Serial(
        port = puerto,
        baudrate = 4800,
        bytesize = serial.EIGHTBITS,
        parity = serial.PARITY_NONE,
        stopbits = serial.STOPBITS_ONE,
        xonxoff = False,
        rtscts = False,
        dsrdtr = False,
        timeout = 1
    )


def main():
    print("Práctica 1: Lectura y adquisición de datos de un receptor GPS\n")

    puerto = input("Puerto serie (ej: COM8, /dev/ttyUSB0): ").strip()

    huso = 30

    ser = None
    try:
        ser = conectar_gps(puerto)
        print(f"\n[OK] Conectado al receptor GPS en {puerto} (4800 bps, 8N1).")
        print("Leyendo tramas GGA (Ctrl+C para parar)...\n")

        contador = 0
        while True:
            linea = ser.readline().decode("ascii", errors="replace").strip()
            if not linea:
                continue

            if "$GPGGA" in linea or "$GNGGA" in linea:
                contador += 1
                datos = parsear_gga(linea)

                # Sin fix: campos vacíos o calidad 0
                if datos is None or datos.get("calidad_fix", 0) == 0:
                    print(f"[Trama {contador}] Sin fix / sin coordenadas aún: {linea}")
                    continue

                utm = geograficas_a_utm(
                    datos["latitud_decimal"],
                    datos["longitud_decimal"],
                    elipsoide="WGS84",
                    huso=huso
                )

                print(f"--- Trama GGA #{contador} ---")
                print(f"Hora UTC:   {datos['hora_utc']}")
                print(f"Latitud:    {datos['latitud_decimal']:.8f}°")
                print(f"Longitud:   {datos['longitud_decimal']:.8f}°")
                print(f"Satélites:  {datos['num_satelites']} | HDOP: {datos['hdop']}")
                print(f"Altitud:    {datos['altitud']} m")
                print(f"UTM (WGS84) — Huso {huso}")
                print(f"  Easting (X):  {utm['easting']:.3f} m")
                print(f"  Northing (Y): {utm['northing']:.3f} m")
                print()

    except KeyboardInterrupt:
        print("\n[INFO] Detenido por el usuario (Ctrl+C).")
    except serial.SerialException as e:
        print(f"[ERROR] Problema con el puerto serie: {e}")
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        print("[INFO] Puerto serie cerrado.")


if __name__ == "__main__":
    main()