import math

ELIPSOIDES = {
    'WGS84': {
        'nombre': 'WGS84',
        'a': 6378137.0,
        'f': 1.0 / 298.25722,
        'e2': 0.00669437999013,
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
    if elipsoide.upper() not in ELIPSOIDES:
        raise ValueError(f"Elipsoide '{elipsoide}' no soportado. Use 'WGS84' o 'ED50'.")

    elip = ELIPSOIDES[elipsoide.upper()]
    a = elip['a']
    e2 = elip['e2']

    phi = math.radians(latitud_deg)
    lam = math.radians(longitud_deg)

    lambda_0g = huso * 6 - 183
    lambda_0 = math.radians(lambda_0g)

    e_prima2 = e2 / (1.0 - e2)

    N = a / math.sqrt(1.0 - e2 * math.sin(phi) ** 2)

    T = math.tan(phi) ** 2

    C = e_prima2 * math.cos(phi) ** 2

    A = math.cos(phi) * (lam - lambda_0)

    e2_2 = e2 ** 2
    e2_3 = e2 ** 3

    M = a * (
        (1.0 - e2 / 4.0 - 3.0 / 64.0 * e2_2 - 5.0 / 256.0 * e2_3) * phi
        - (3.0 / 8.0 * e2 + 3.0 / 32.0 * e2_2 + 45.0 / 1024.0 * e2_3)
          * math.sin(2.0 * phi)
        + (15.0 / 256.0 * e2_2 + 45.0 / 1024.0 * e2_3)
          * math.sin(4.0 * phi)
        - (35.0 / 3072.0 * e2_3)
          * math.sin(6.0 * phi)
    )

    easting = 0.9996 * N * (
        A
        + (1.0 - T + C) * A ** 3 / 6.0
        + (5.0 - 18.0 * T + T ** 2 + 72.0 * C - 58.0 * e_prima2)
          * A ** 5 / 120.0
    ) + 500000.0

    northing = 0.9996 * (
        M + N * math.tan(phi) * (
            A ** 2 / 2.0
            + (5.0 - T + 9.0 * C + 4.0 * C ** 2) * A ** 4 / 24.0
            + (61.0 - 58.0 * T + T ** 2 + 600.0 * C - 330.0 * e_prima2)
              * A ** 6 / 720.0
        )
    )

    if latitud_deg < 0:
        northing += 10000000.0

    return {
        'easting': easting,
        'northing': northing,
        'huso': huso,
        'elipsoide': elip['nombre'],
    }