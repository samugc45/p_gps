"""
Módulo de parseo de tramas NMEA GGA.

Analiza tramas del estándar NMEA 0183 con sentencia GGA
y extrae los campos relevantes: posición, calidad del fix,
número de satélites, HDOP, altitud, etc.
"""


# Diccionario de calidades de fix GPS
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
        trama (str): Trama NMEA completa.

    Retorna:
        bool: True si el checksum es válido, False en caso contrario.
    """
    try:
        # Extraer la parte entre '$' y '*'
        if '$' not in trama or '*' not in trama:
            return False

        contenido = trama.split('$')[1].split('*')[0]
        checksum_recibido = trama.split('*')[1].strip()

        # Calcular XOR de todos los caracteres
        checksum_calculado = 0
        for char in contenido:
            checksum_calculado ^= ord(char)

        # Comparar (el checksum se expresa en hexadecimal, 2 dígitos)
        return f"{checksum_calculado:02X}" == checksum_recibido.upper()

    except (IndexError, ValueError):
        return False


def parsear_coordenada_latitud(valor_str, direccion):
    """
    Convierte la latitud NMEA (DDMM.MMMM) a grados decimales.

    Formato NMEA: DDMM.MMMM donde DD = grados, MM.MMMM = minutos.

    Parámetros:
        valor_str (str): Valor de latitud en formato NMEA.
        direccion (str): 'N' (Norte) o 'S' (Sur).

    Retorna:
        tuple: (grados, minutos, decimal, dirección)
    """
    if not valor_str or not direccion:
        return None

    try:
        valor = float(valor_str)
        grados = int(valor / 100)
        minutos = valor - (grados * 100)
        decimal = grados + (minutos / 60.0)

        # Si es Sur, el valor es negativo
        if direccion == 'S':
            decimal = -decimal

        return (grados, minutos, decimal, direccion)

    except ValueError:
        return None


def parsear_coordenada_longitud(valor_str, direccion):
    """
    Convierte la longitud NMEA (DDDMM.MMMM) a grados decimales.

    Formato NMEA: DDDMM.MMMM donde DDD = grados, MM.MMMM = minutos.

    Parámetros:
        valor_str (str): Valor de longitud en formato NMEA.
        direccion (str): 'E' (Este) o 'W' (Oeste).

    Retorna:
        tuple: (grados, minutos, decimal, dirección)
    """
    if not valor_str or not direccion:
        return None

    try:
        valor = float(valor_str)
        grados = int(valor / 100)
        minutos = valor - (grados * 100)
        decimal = grados + (minutos / 60.0)

        # Si es Oeste, el valor es negativo
        if direccion == 'W':
            decimal = -decimal

        return (grados, minutos, decimal, direccion)

    except ValueError:
        return None


def formatear_hora(hora_str):
    """
    Convierte la hora NMEA (HHMMSS o HHMMSS.SS) a formato legible HH:MM:SS.

    Parámetros:
        hora_str (str): Hora en formato NMEA.

    Retorna:
        str: Hora formateada.
    """
    if not hora_str or len(hora_str) < 6:
        return "N/A"

    hh = hora_str[0:2]
    mm = hora_str[2:4]
    ss = hora_str[4:]
    return f"{hh}:{mm}:{ss} UTC"


def parsear_gga(trama):
    """
    Parsea una trama NMEA GGA completa y extrae todos los campos.

    Formato esperado:
    $GPGGA,HHMMSS.SS,DDMM.MMMM,N/S,DDDMM.MMMM,E/W,Q,NN,HDOP,ALT,M,GEOID,M,DGPS_AGE,DGPS_ID*CS

    Parámetros:
        trama (str): Trama NMEA GGA completa.

    Retorna:
        dict: Diccionario con todos los campos parseados, o None si la trama es inválida.
    """
    if not trama:
        return None

    # Verificar que es una trama GGA
    if 'GGA' not in trama:
        return None

    # Verificar checksum (opcional pero recomendado)
    if '*' in trama:
        if not verificar_checksum(trama):
            print(f"[AVISO] Checksum inválido en trama: {trama}")
            # Continuamos igualmente, pero avisamos

    try:
        # Eliminar checksum para el parseo de campos
        trama_limpia = trama.split('*')[0] if '*' in trama else trama
        campos = trama_limpia.split(',')

        # Necesitamos al menos 15 campos para una trama GGA válida
        if len(campos) < 15:
            return None

        # Campo 1: Hora UTC
        hora_utc = formatear_hora(campos[1])

        # Campos 2-3: Latitud
        lat = parsear_coordenada_latitud(campos[2], campos[3])
        if lat is None:
            return None

        lat_grados, lat_minutos, lat_decimal, lat_dir = lat

        # Campos 4-5: Longitud
        lon = parsear_coordenada_longitud(campos[4], campos[5])
        if lon is None:
            return None

        lon_grados, lon_minutos, lon_decimal, lon_dir = lon

        # Campo 6: Calidad del fix
        calidad_fix = int(campos[6]) if campos[6] else 0

        # Campo 7: Número de satélites
        num_satelites = int(campos[7]) if campos[7] else 0

        # Campo 8: HDOP
        hdop = float(campos[8]) if campos[8] else 0.0

        # Campos 9-10: Altitud sobre el nivel del mar
        altitud = float(campos[9]) if campos[9] else 0.0

        # Campos 11-12: Altura del geoide sobre el elipsoide WGS84
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
        print(f"[ERROR] Error parseando trama GGA: {e}")
        return None