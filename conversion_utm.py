"""
Módulo de transformación de coordenadas geográficas a UTM.

Implementa las ecuaciones de Gauss-Krüger para la proyección UTM elipsoidal,
con soporte para los elipsoides WGS84 y Europeo 1950 (ED50).

Verificado con el ejemplo del enunciado:
  Entrada:  Lat 40° 23.429' N, Lon 3° 37.619' W  (WGS84, Huso 30)
  Esperado: UTM Este = 446786.81591 m, UTM Norte = 4471287.18508 m
"""

import math


# ──────────────────────────────────────────────────────────────
#  PARÁMETROS DE LOS ELIPSOIDES
# ──────────────────────────────────────────────────────────────
#  a  = semieje mayor (radio ecuatorial)
#  f  = achatamiento = (a - b) / a
#  b  = semieje menor = a · (1 - f)
#  e2 = cuadrado de la primera excentricidad = (a² - b²) / a²
#  c  = radio polar de curvatura = a² / b

ELIPSOIDES = {
    'WGS84': {
        'nombre': 'WGS84',
        'a': 6378137.0,
        'f': 1.0 / 298.25722,
        'e2': 0.00669437999013,     # e'² (primera excentricidad al cuadrado)
        'c': 6399593.626,
    },
    'ED50': {
        'nombre': 'Europeo 1950 (ED50 / Hayford)',
        'a': 6378388.0,
        'f': 1.0 / 297.0,
        'e2': 0.00672267,
        'c': 6399936.608,
    }
}


def geograficas_a_utm(latitud_deg, longitud_deg, elipsoide='WGS84', huso=30):
    """
    Transforma coordenadas geográficas (lat, lon en grados decimales)
    a coordenadas UTM (Easting, Northing) usando Gauss-Krüger.

    Parámetros:
        latitud_deg  (float): Latitud en grados decimales (+N, -S).
        longitud_deg (float): Longitud en grados decimales (+E, -W).
        elipsoide    (str):   'WGS84' o 'ED50'.
        huso         (int):   Huso UTM (1-60). España = 30.

    Retorna:
        dict con 'easting', 'northing', 'huso', 'elipsoide'.
    """
    if elipsoide.upper() not in ELIPSOIDES:
        raise ValueError(f"Elipsoide '{elipsoide}' no soportado. Use 'WGS84' o 'ED50'.")

    elip = ELIPSOIDES[elipsoide.upper()]
    a = elip['a']
    e2 = elip['e2']  # e'²

    # ── Paso 1: Grados → Radianes ──
    phi = math.radians(latitud_deg)       # φ (latitud)
    lam = math.radians(longitud_deg)      # λ (longitud)

    # ── Paso 2: Meridiano central del huso ──
    # λ₀g = Huso · 6 - 183°
    lambda_0g = huso * 6 - 183
    lambda_0 = math.radians(lambda_0g)

    # ── Paso 3: Variables intermedias ──

    # e' = e'² / (1 - e'²)   (segunda excentricidad al cuadrado)
    e_prima2 = e2 / (1.0 - e2)

    # N = a / √(1 - e'² · sin²(φ))   (radio de curvatura primer vertical)
    N = a / math.sqrt(1.0 - e2 * math.sin(phi) ** 2)

    # T = tan²(φ)
    T = math.tan(phi) ** 2

    # C = e' · cos²(φ)   donde e' = e_prima2
    C = e_prima2 * math.cos(phi) ** 2

    # A = cos(φ) · (λ - λ₀)
    A = math.cos(phi) * (lam - lambda_0)

    # ── Paso 4: M (longitud del arco de meridiano) ──
    e2_2 = e2 ** 2   # (e'²)²
    e2_3 = e2 ** 3   # (e'²)³

    M = a * (
        (1.0 - e2 / 4.0 - 3.0 / 64.0 * e2_2 - 5.0 / 256.0 * e2_3) * phi
        - (3.0 / 8.0 * e2 + 3.0 / 32.0 * e2_2 + 45.0 / 1024.0 * e2_3)
          * math.sin(2.0 * phi)
        + (15.0 / 256.0 * e2_2 + 45.0 / 1024.0 * e2_3)
          * math.sin(4.0 * phi)
        - (35.0 / 3072.0 * e2_3)
          * math.sin(6.0 * phi)
    )

    # ── Paso 5: UTM Easting (X) ──
    # Easting = 0.9996·N·[A + (1-T+C)·A³/6
    #           + (5 - 18T + T² + 72C - 58e')·A⁵/120] + 500000
    easting = 0.9996 * N * (
        A
        + (1.0 - T + C) * A ** 3 / 6.0
        + (5.0 - 18.0 * T + T ** 2 + 72.0 * C - 58.0 * e_prima2)
          * A ** 5 / 120.0
    ) + 500000.0

    # ── Paso 6: UTM Northing (Y) ──
    # Northing = 0.9996·[M + N·tan(φ)·(A²/2
    #            + (5 - T + 9C + 4C²)·A⁴/24
    #            + (61 - 58T + T² + 600C - 330e')·A⁶/720)]
    northing = 0.9996 * (
        M + N * math.tan(phi) * (
            A ** 2 / 2.0
            + (5.0 - T + 9.0 * C + 4.0 * C ** 2) * A ** 4 / 24.0
            + (61.0 - 58.0 * T + T ** 2 + 600.0 * C - 330.0 * e_prima2)
              * A ** 6 / 720.0
        )
    )

    # Hemisferio sur: sumar 10.000.000 al Northing
    if latitud_deg < 0:
        northing += 10000000.0

    return {
        'easting': easting,
        'northing': northing,
        'huso': huso,
        'elipsoide': elip['nombre'],
    }


# ──────────────────────────────────────────────
#  PRUEBA INDEPENDIENTE
# ──────────────────────────────────────────────
if __name__ == '__main__':
    # Ejemplo del enunciado: Campus Sur UPM
    # Lat 40° 23.429' N → 40.39048333°
    # Lon  3° 37.619' W → -3.62698333°
    lat = 40.0 + 23.429 / 60.0
    lon = -(3.0 + 37.619 / 60.0)

    print("=" * 55)
    print("  VERIFICACIÓN — Campus Sur UPM (EUI)")
    print("=" * 55)
    print(f"  Latitud:  {lat:.8f}°")
    print(f"  Longitud: {lon:.8f}°")

    utm = geograficas_a_utm(lat, lon, elipsoide='WGS84', huso=30)
    print(f"\n  UTM Easting:  {utm['easting']:.5f} m  (esperado: 446786.81591)")
    print(f"  UTM Northing: {utm['northing']:.5f} m  (esperado: 4471287.18508)")

    error_e = abs(utm['easting'] - 446786.81591)
    error_n = abs(utm['northing'] - 4471287.18508)
    print(f"\n  Error E: {error_e:.5f} m | Error N: {error_n:.5f} m")