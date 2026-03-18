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
    if not hora_str or len(hora_str) < 6:
        return "N/A"
    return f"{hora_str[0:2]}:{hora_str[2:4]}:{hora_str[4:]} UTC"


def parsear_gga(trama):
    if not trama or 'GGA' not in trama:
        return None

    if '*' in trama:
        if not verificar_checksum(trama):
            print(f"  [AVISO] Checksum inválido: {trama}")

    try:
        trama_limpia = trama.split('*')[0] if '*' in trama else trama
        campos = trama_limpia.split(',')

        if len(campos) < 15:
            return None

        hora_utc = formatear_hora(campos[1])

        lat = parsear_coordenada_latitud(campos[2], campos[3])
        if lat is None:
            return None
        lat_grados, lat_minutos, lat_decimal, lat_dir = lat

        lon = parsear_coordenada_longitud(campos[4], campos[5])
        if lon is None:
            return None
        lon_grados, lon_minutos, lon_decimal, lon_dir = lon

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