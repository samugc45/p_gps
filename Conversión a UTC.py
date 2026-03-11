"""
Módulo de transformación de coordenadas geográficas a UTM.

Implementa las ecuaciones de Gauss-Krüger para la proyección UTM elipsoidal,
con soporte para los elipsoides WGS84 y Europeo 1950 (ED50).

Referencias:
- Ecuaciones de Gauss-Krüger según el enunciado de la práctica.
- Parámetros de los elipsoides WGS84 y ED50.
"""

import math


# ──────────────────────────────────────────────────────────────
#  PARÁMETROS DE LOS ELIPSOIDES
# ──────────────────────────────────────────────────────────────
#
#  a = semieje mayor (radio ecuatorial)
#  f = achatamiento (flattening) = (a - b) / a
#  b = semieje menor (radio polar) = a * (1 - f)
#  e2 = cuadrado de la excentricidad = (a² - b²) / b²  [primera excentricidad al cuadrado]
#       NOTA: en el enunciado se usa e'² que es la segunda excentricidad al cuadrado
#  c = radio polar de curvatura = a² / b
#

ELIPSOIDES = {
    'WGS84': {
        'nombre': 'WGS84',
        'a': 6378137.0,                    # Radio ecuatorial (m)
        'f': 1.0 / 298.25722,              # Achatamiento
        'e2': 0.00669437999013,             # Cuadrado de la primera excentricidad
        'c': 6399593.626,                   # Radio polar de curvatura
    },
    'ED50': {
        'nombre': 'Europeo 1950 (ED50)',
        'a': 6378388.0,                     # Radio ecuatorial (m)
        'f': 1.0 / 297.0,                  # Achatamiento
        'e2': 0.00672267,                   # Cuadrado de la primera excentricidad
        'c': 6399936.608,                   # Radio polar de curvatura
    }
}


def geograficas_a_utm(latitud_deg, longitud_deg, elipsoide='WGS84', huso=30):
    """
    Transforma coordenadas geográficas (latitud, longitud) en coordenadas UTM
    (Easting, Northing) utilizando las ecuaciones de Gauss-Krüger.

    Parámetros:
        latitud_deg (float): Latitud en grados decimales (positivo = Norte).
        longitud_deg (float): Longitud en grados decimales (positivo = Este, negativo = Oeste).
        elipsoide (str): 'WGS84' o 'ED50'.
        huso (int): Huso UTM (1-60). En España = 30.

    Retorna:
        dict: Diccionario con 'easting', 'northing', 'huso'.
    """

    # Seleccionar parámetros del elipsoide
    if elipsoide.upper() not in ELIPSOIDES:
        raise ValueError(f"Elipsoide no soportado: {elipsoide}. Use 'WGS84' o 'ED50'.")

    elip = ELIPSOIDES[elipsoide.upper()]
    a = elip['a']
    e2 = elip['e2']        # e'² (cuadrado de la primera excentricidad)

    # ──────────────────────────────────────────────
    #  Paso 1: Convertir grados a radianes
    # ──────────────────────────────────────────────
    phi = math.radians(latitud_deg)       # φ (latitud en radianes)
    lam = math.radians(longitud_deg)      # λ (longitud en radianes)

    # ──────────────────────────────────────────────
    #  Paso 2: Calcular el meridiano central del huso
    # ──────────────────────────────────────────────
    # λ₀g = Huso · 6 - 183° (en grados)
    lambda_0g = huso * 6 - 183            # Meridiano central en grados
    lambda_0 = math.radians(lambda_0g)    # λ₀ en radianes

    # ──────────────────────────────────────────────
    #  Paso 3: Calcular variables intermedias
    # ──────────────────────────────────────────────

    # e' = e'² / (1 - e'²)  — segunda excentricidad al cuadrado
    e_prima2 = e2 / (1.0 - e2)

    # N = a / sqrt(1 - e'² · sin²(φ))  — radio de curvatura en el primer vertical
    N = a / math.sqrt(1.0 - e2 * math.sin(phi) ** 2)

    # T = tan²(φ)
    T = math.tan(phi) ** 2

    # C = e' · cos²(φ)   donde e' = e'²/(1-e'²) => C = e_prima2 · cos²(φ)
    C = e_prima2 * math.cos(phi) ** 2

    # A = cos(φ) · (λ - λ₀)
    A = math.cos(phi) * (lam - lambda_0)

    # ──────────────────────────────────────────────
    #  Paso 4: Calcular M (longitud del arco de meridiano)
    # ──────────────────────────────────────────────
    #
    # M = a · [ (1 - e²/4 - 3/64·(e²)² - 5/256·(e²)³) · φ
    #          - (3/8·e² + 3/32·(e²)² + 45/1024·(e²)³) · sin(2φ)
    #          + (15/256·(e²)² + 45/1024·(e²)³) · sin(4φ)
    #          - (35/3072·(e²)³) · sin(6φ) ]
    #
    e2_sq = e2 ** 2       # (e'²)²
    e2_cb = e2 ** 3       # (e'²)³

    M = a * (
        (1.0 - e2 / 4.0 - 3.0 / 64.0 * e2_sq - 5.0 / 256.0 * e2_cb) * phi
        - (3.0 / 8.0 * e2 + 3.0 / 32.0 * e2_sq + 45.0 / 1024.0 * e2_cb) * math.sin(2.0 * phi)
        + (15.0 / 256.0 * e2_sq + 45.0 / 1024.0 * e2_cb) * math.sin(4.0 * phi)
        - (35.0 / 3072.0 * e2_cb) * math.sin(6.0 * phi)
    )

    # ──────────────────────────────────────────────
    #  Paso 5: Calcular UTM Easting (X)
    # ──────────────────────────────────────────────
    #
    # Easting = 0.9996 · N · [ A + (1-T+C)·A³/6
    #           + (5 - 18T + T² + 72C - 58e'²)·A⁵/120 ] + 500000
    #
    easting = 0.9996 * N * (
        A
        + (1.0 - T + C) * A ** 3 / 6.0
        + (5.0 - 18.0 * T + T ** 2 + 72.0 * C - 58.0 * e_prima2) * A ** 5 / 120.0
    ) + 500000.0

    # ──────────────────────────────────────────────
    #  Paso 6: Calcular UTM Northing (Y)
    # ──────────────────────────────────────────────
    #
    # Northing = 0.9996 · [ M + N · tan(φ) · ( A²/2
    #            + (5 - T + 9C + 4C²)·A⁴/24
    #            + (61 - 58T + T² + 600C - 330e'²)·A⁶/720 ) ]
    #
    northing = 0.9996 * (
        M + N * math.tan(phi) * (
            A ** 2 / 2.0
            + (5.0 - T + 9.0 * C + 4.0 * C ** 2) * A ** 4 / 24.0
            + (61.0 - 58.0 * T + T ** 2 + 600.0 * C - 330.0 * e_prima2) * A ** 6 / 720.0
        )
    )

    # Si la latitud es sur, se añade 10.000.000 al Northing
    if latitud_deg < 0:
        northing += 10000000.0

    return {
        'easting': easting,
        'northing': northing,
        'huso': huso,
        'elipsoide': elip['nombre'],
    }


# ──────────────────────────────────────────────
#  FUNCIÓN DE PRUEBA
# ──────────────────────────────────────────────
if __name__ == '__main__':
    # Ejemplo del enunciado: $GPGGA,123519,4807.038,N,01131.000,E,...
    # Latitud:  48° 07.038' N  = 48.1173°
    # Longitud: 011° 31.000' E = 11.516667°

    lat = 48.0 + 7.038 / 60.0    # 48.1173°
    lon = 11.0 + 31.000 / 60.0   # 11.51667°

    print("=" * 55)
    print("  PRUEBA DE CONVERSIÓN GEOGRÁFICAS → UTM")
    print("=" * 55)
    print(f"\n  Coordenadas geográficas:")
    print(f"    Latitud:  {lat:.6f}°")
    print(f"    Longitud: {lon:.6f}°")

    for elip_nombre in ['WGS84', 'ED50']:
        resultado = geograficas_a_utm(lat, lon, elipsoide=elip_nombre, huso=32)
        print(f"\n  --- {resultado['elipsoide']} (Huso {resultado['huso']}) ---")
        print(f"    UTM Easting (X):  {resultado['easting']:.3f} m")
        print(f"    UTM Northing (Y): {resultado['northing']:.3f} m")

    print()