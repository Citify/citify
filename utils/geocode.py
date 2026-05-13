import requests
import time

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {'User-Agent': 'Citify/1.0 (citify.ca)'}


def geocode(address, city="Montréal", country="Canada"):
    """
    Convert a street address into latitude/longitude using Nominatim.
    Returns (lat, lon) floats or (None, None) if not found.
    """
    query = f"{address}, {city}, {country}"
    params = {
        'q': query,
        'format': 'json',
        'limit': 1,
        'countrycodes': 'ca',
    }
    try:
        time.sleep(1)  # Nominatim rate limit: 1 request/second
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=5)
        data = resp.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
    except Exception:
        pass
    return None, None
