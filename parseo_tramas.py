"""
Módulo de parseo de tramas NMEA GGA.

Analiza tramas del estándar NMEA 0183 con sentencia GGA y extrae:
hora UTC, latitud, longitud, calidad del fix, satélites, HDOP, altitud, etc.
"""


# Descripción textual de cada calidad de fix GPS
CALIDAD_FIX = {
    0: "Inválido (sin fix)",
    1: "GPS fix (SPS)",
    2: "DGPS fix",
    3: "PPS fix",
    4: "Real Time Kinematic (RTK)",
    5: "Float RTK",
    6: "Estimado (dead reckoning)",
    7: "Modo de entrada manual",
    8: "Modo de simulación"
}


def verificar_checksum(trama):
    """
    Verifica el checksum de una trama NMEA.
    El checksum es un XOR de todos los caracteres entre '$' y '*'.

    Parámetros:
        trama (str): Trama NMEA completa (ej: "$GPGGA,...*47").

    Retorna:
        bool: True si el checksum es correcto.
    """
    try:
        if '$' not in trama or '*' not in trama:
            return False

        contenido = trama.split('$')[1].split('*')[0]
        checksum_recibido = trama.split('*')[1].strip()

        # XOR de todos los caracteres entre $ y *
        checksum_calculado = 0
        for char in contenido:
            checksum_calculado ^= ord(char)

        return f"{checksum_calculado:02X}" == checksum_recibido.upper()

    except (IndexError, ValueError):
        return False


def parsear_coordenada_latitud(valor_str, direccion):
    """
    Convierte latitud NMEA (DDMM.MMMM, N/S) a grados decimales.

    Formato NMEA: DDMM.MMMM → DD grados + MM.MMMM minutos.

    Retorna:
        tuple: (grados_enteros, minutos_decimal, grados_decimales, dirección) o None.
    """
    if not valor_str or not direccion:
        return None
    try:
        valor = float(valor_str)
        grados = int(valor / 100)
        minutos = valor - (grados * 100)
        decimal = grados + (minutos / 60.0)
        if direccion == 'S':
            decimal = -decimal
        return (grados, minutos, decimal, direccion)
    except ValueError:
        return None


def parsear_coordenada_longitud(valor_str, direccion):
    """
    Convierte longitud NMEA (DDDMM.MMMM, E/W) a grados decimales.

    Formato NMEA: DDDMM.MMMM → DDD grados + MM.MMMM minutos.

    Retorna:
        tuple: (grados_enteros, minutos_decimal, grados_decimales, dirección) o None.
    """
    if not valor_str or not direccion:
        return None
    try:
        valor = float(valor_str)
        grados = int(valor / 100)
        minutos = valor - (grados * 100)
        decimal = grados + (minutos / 60.0)
        if direccion == 'W':
            decimal = -decimal
        return (grados, minutos, decimal, direccion)
    except ValueError:
        return None


def formatear_hora(hora_str):
    """
    Convierte hora NMEA (HHMMSS o HHMMSS.SS) a formato legible HH:MM:SS UTC.
    """
    if not hora_str or len(hora_str) < 6:
        return "N/A"
    return f"{hora_str[0:2]}:{hora_str[2:4]}:{hora_str[4:]} UTC"


def parsear_gga(trama):
    """
    Parsea una trama NMEA GGA completa y devuelve un diccionario con todos los campos.

    Formato:
      $GPGGA,HHMMSS.SS,DDMM.MMMM,N/S,DDDMM.MMMM,E/W,Q,NN,HDOP,ALT,M,GEOID,M,AGE,ID*CS

    Parámetros:
        trama (str): Trama NMEA GGA completa.

    Retorna:
        dict con todos los campos, o None si la trama es inválida.
    """
    if not trama or 'GGA' not in trama:
        return None

    # Verificar checksum si está presente
    if '*' in trama:
        if not verificar_checksum(trama):
            print(f"  [AVISO] Checksum inválido: {trama}")

    try:
        # Quitar checksum para separar campos
        trama_limpia = trama.split('*')[0] if '*' in trama else trama
        campos = trama_limpia.split(',')

        if len(campos) < 15:
            return None

        # Hora UTC
        hora_utc = formatear_hora(campos[1])

        # Latitud (campos 2-3)
        lat = parsear_coordenada_latitud(campos[2], campos[3])
        if lat is None:
            return None
        lat_grados, lat_minutos, lat_decimal, lat_dir = lat

        # Longitud (campos 4-5)
        lon = parsear_coordenada_longitud(campos[4], campos[5])
        if lon is None:
            return None
        lon_grados, lon_minutos, lon_decimal, lon_dir = lon

        # Resto de campos
        calidad_fix = int(campos[6]) if campos[6] else 0
        num_satelites = int(campos[7]) if campos[7] else 0
        hdop = float(campos[8]) if campos[8] else 0.0
        altitud = float(campos[9]) if campos[9] else 0.0
        altura_geoide = float(campos[11]) if campos[11] else 0.0

        return {
            'trama_original': trama,
            'hora_utc': hora_utc,
            'latitud_grados': lat_grados,
            'latitud_minutos': lat_minutos,
            'latitud_decimal': lat_decimal,
            'latitud_direccion': lat_dir,
            'longitud_grados': lon_grados,
            'longitud_minutos': lon_minutos,
            'longitud_decimal': lon_decimal,
            'longitud_direccion': lon_dir,
            'calidad_fix': calidad_fix,
            'calidad_texto': CALIDAD_FIX.get(calidad_fix, "Desconocido"),
            'num_satelites': num_satelites,
            'hdop': hdop,
            'altitud': altitud,
            'altura_geoide': altura_geoide,
        }

    except (ValueError, IndexError) as e:
        print(f"  [ERROR] Parseando trama GGA: {e}")
        return None