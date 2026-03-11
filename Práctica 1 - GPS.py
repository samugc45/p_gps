"""
Práctica 1: Lectura y adquisición de datos de un receptor GPS
Asignatura: Sistemas y Servicios de Navegación con GPS (2025/2026)

Este módulo lee tramas NMEA GGA desde un puerto serie,
extrae las coordenadas geográficas (latitud, longitud)
y las transforma en coordenadas UTM mediante las ecuaciones de Gauss-Krüger.
"""

import serial
import time
from nmea_parser import parsear_gga
from coordenadas_utm import geograficas_a_utm


def conectar_gps(puerto='COM3', baudrate=9600, timeout=1):
    """
    Abre la conexión con el receptor GPS a través del puerto serie.

    Parámetros:
        puerto (str): Nombre del puerto serie (ej: 'COM3', '/dev/ttyUSB0').
        baudrate (int): Velocidad de comunicación en baudios.
        timeout (int): Tiempo de espera en segundos.

    Retorna:
        serial.Serial: Objeto de conexión serie.
    """
    try:
        conexion = serial.Serial(puerto, baudrate, timeout=timeout)
        print(f"[OK] Conectado al receptor GPS en {puerto} a {baudrate} baudios.")
        return conexion
    except serial.SerialException as e:
        print(f"[ERROR] No se pudo abrir el puerto {puerto}: {e}")
        return None


def leer_tramas_gps(conexion, elipsoide='WGS84', huso=30, num_lecturas=None):
    """
    Lee tramas del receptor GPS de forma continua, filtra las GGA,
    y muestra las coordenadas geográficas y UTM.

    Parámetros:
        conexion (serial.Serial): Conexión serie abierta.
        elipsoide (str): 'WGS84' o 'ED50' (European 1950).
        huso (int): Huso UTM (en España, 30).
        num_lecturas (int o None): Número de lecturas a realizar. None = infinito.
    """
    contador = 0
    print("\n" + "=" * 70)
    print("  RECEPTOR GPS — Lectura de tramas GGA")
    print(f"  Elipsoide: {elipsoide} | Huso UTM: {huso}")
    print("=" * 70)
    print()

    try:
        while True:
            linea = conexion.readline().decode('ascii', errors='replace').strip()

            if not linea:
                continue

            # Filtramos solo las tramas GGA ($GPGGA o $GNGGA)
            if '$GPGGA' in linea or '$GNGGA' in linea:
                contador += 1
                datos = parsear_gga(linea)

                if datos is None:
                    print(f"[Trama {contador}] Trama GGA inválida: {linea}")
                    continue

                if datos['calidad_fix'] == 0:
                    print(f"[Trama {contador}] Sin fix GPS (calidad = 0). "
                          f"Satélites: {datos['num_satelites']}")
                    continue

                # Transformar a UTM
                utm = geograficas_a_utm(
                    datos['latitud_decimal'],
                    datos['longitud_decimal'],
                    elipsoide=elipsoide,
                    huso=huso
                )

                # Mostrar resultados
                mostrar_datos(contador, datos, utm)

            if num_lecturas is not None and contador >= num_lecturas:
                break

    except KeyboardInterrupt:
        print("\n\n[INFO] Lectura detenida por el usuario (Ctrl+C).")
    finally:
        conexion.close()
        print("[INFO] Puerto serie cerrado.")


def mostrar_datos(numero, datos, utm):
    """Muestra los datos parseados y las coordenadas UTM por pantalla."""
    print(f"--- Trama GGA #{numero} ---")
    print(f"  Hora UTC:        {datos['hora_utc']}")
    print(f"  Latitud:         {datos['latitud_decimal']:.6f}° "
          f"({datos['latitud_grados']}° {datos['latitud_minutos']:.4f}' "
          f"{datos['latitud_direccion']})")
    print(f"  Longitud:        {datos['longitud_decimal']:.6f}° "
          f"({datos['longitud_grados']}° {datos['longitud_minutos']:.4f}' "
          f"{datos['longitud_direccion']})")
    print(f"  Calidad fix:     {datos['calidad_fix']} — {datos['calidad_texto']}")
    print(f"  Satélites:       {datos['num_satelites']}")
    print(f"  HDOP:            {datos['hdop']}")
    print(f"  Altitud:         {datos['altitud']} m")
    print(f"  Altura geoide:   {datos['altura_geoide']} m")
    print(f"  UTM Easting (X): {utm['easting']:.3f} m")
    print(f"  UTM Northing (Y):{utm['northing']:.3f} m")
    print(f"  Huso UTM:        {utm['huso']}")
    print()


def leer_desde_fichero(ruta_fichero, elipsoide='WGS84', huso=30):
    """
    Lee tramas GGA desde un fichero de texto (para pruebas sin receptor físico).

    Parámetros:
        ruta_fichero (str): Ruta al fichero con tramas NMEA.
        elipsoide (str): 'WGS84' o 'ED50'.
        huso (int): Huso UTM.
    """
    contador = 0
    print("\n" + "=" * 70)
    print("  LECTURA DESDE FICHERO — Tramas GGA")
    print(f"  Fichero: {ruta_fichero}")
    print(f"  Elipsoide: {elipsoide} | Huso UTM: {huso}")
    print("=" * 70)
    print()

    try:
        with open(ruta_fichero, 'r') as f:
            for linea in f:
                linea = linea.strip()
                if '$GPGGA' in linea or '$GNGGA' in linea:
                    contador += 1
                    datos = parsear_gga(linea)

                    if datos is None:
                        print(f"[Trama {contador}] Trama inválida: {linea}")
                        continue

                    if datos['calidad_fix'] == 0:
                        print(f"[Trama {contador}] Sin fix GPS.")
                        continue

                    utm = geograficas_a_utm(
                        datos['latitud_decimal'],
                        datos['longitud_decimal'],
                        elipsoide=elipsoide,
                        huso=huso
                    )
                    mostrar_datos(contador, datos, utm)

    except FileNotFoundError:
        print(f"[ERROR] No se encontró el fichero: {ruta_fichero}")


# ──────────────────────────────────────────────
#  EJECUCIÓN PRINCIPAL
# ──────────────────────────────────────────────
if __name__ == '__main__':
    import sys

    print("╔══════════════════════════════════════════════════╗")
    print("║   Práctica 1 — Lectura de datos GPS (NMEA GGA)  ║")
    print("║   Sistemas y Servicios de Navegación con GPS     ║")
    print("╚══════════════════════════════════════════════════╝")
    print()
    print("Seleccione modo de ejecución:")
    print("  1. Leer desde receptor GPS (puerto serie)")
    print("  2. Leer desde fichero de tramas NMEA")
    print("  3. Ejecutar ejemplo de demostración")
    print()

    opcion = input("Opción [1/2/3]: ").strip()

    if opcion == '1':
        puerto = input("Puerto serie (ej: COM3, /dev/ttyUSB0): ").strip()
        baudrate = input("Baudrate [9600]: ").strip()
        baudrate = int(baudrate) if baudrate else 9600
        elipsoide = input("Elipsoide [WGS84/ED50]: ").strip().upper() or 'WGS84'
        huso = input("Huso UTM [30]: ").strip()
        huso = int(huso) if huso else 30

        conexion = conectar_gps(puerto, baudrate)
        if conexion:
            leer_tramas_gps(conexion, elipsoide=elipsoide, huso=huso)

    elif opcion == '2':
        ruta = input("Ruta del fichero NMEA: ").strip()
        elipsoide = input("Elipsoide [WGS84/ED50]: ").strip().upper() or 'WGS84'
        huso = input("Huso UTM [30]: ").strip()
        huso = int(huso) if huso else 30
        leer_desde_fichero(ruta, elipsoide=elipsoide, huso=huso)

    elif opcion == '3':
        # Ejemplo de demostración con trama GGA de muestra
        from nmea_parser import parsear_gga
        from coordenadas_utm import geograficas_a_utm

        trama_ejemplo = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
        print(f"\nTrama de ejemplo: {trama_ejemplo}\n")

        datos = parsear_gga(trama_ejemplo)
        if datos:
            utm_wgs84 = geograficas_a_utm(
                datos['latitud_decimal'], datos['longitud_decimal'],
                elipsoide='WGS84', huso=30
            )
            utm_ed50 = geograficas_a_utm(
                datos['latitud_decimal'], datos['longitud_decimal'],
                elipsoide='ED50', huso=30
            )
            print("=== Resultados con WGS84 ===")
            mostrar_datos(1, datos, utm_wgs84)
            print("=== Resultados con ED50 ===")
            mostrar_datos(1, datos, utm_ed50)
    else:
        print("Opción no válida.")