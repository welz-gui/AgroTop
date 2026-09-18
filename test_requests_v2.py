def _fetch_forecast(lat: float, lon: float):
    import requests
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max&timezone=America%2FSao_Paulo&forecast_days=7"
    try:
        r = requests.get(url, timeout=10)
        return r.json()
    except Exception as e:
        print(f"Exception: {e}")
        return None

res = _fetch_forecast(-23.55, -46.63)
print(res)
