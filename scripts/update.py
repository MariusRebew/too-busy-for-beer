#!/usr/bin/env python3
"""
Boots-Wächter – Update-Skript
Holt Multi-Modell-Wetter (Open-Meteo) für die Streckenenden und den aktuellen
Blaualgen-/Bakterien-Stand (Google-News-RSS + amtliche Quelle) und schreibt
data.json (aktueller Stand) sowie history.json (Verlauf).

Nur Python-Standardbibliothek – keine Extra-Pakete nötig.
Ampel-Prinzip: im Zweifel vorsichtig (eher Gelb als Grün).
"""

import json, os, re, html, statistics, urllib.request, urllib.parse
from datetime import datetime, timezone, date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "Mozilla/5.0 (compatible; BootsWaechter/1.0; +https://github.com)"}
MODELS = ["icon_seamless", "gfs_seamless", "ecmwf_ifs025"]

WMO = {
    0: "klar", 1: "überwiegend klar", 2: "teils bewölkt", 3: "bewölkt",
    45: "Nebel", 48: "Reifnebel", 51: "leichter Niesel", 53: "Niesel", 55: "starker Niesel",
    61: "leichter Regen", 63: "Regen", 65: "starker Regen",
    66: "gefrierender Regen", 67: "gefrierender Regen",
    71: "leichter Schnee", 73: "Schnee", 75: "starker Schnee", 77: "Schneegriesel",
    80: "leichte Schauer", 81: "Schauer", 82: "kräftige Schauer",
    85: "Schneeschauer", 86: "Schneeschauer",
    95: "Gewitter", 96: "Gewitter mit Hagel", 99: "schweres Gewitter mit Hagel",
}
THUNDER = {95, 96, 99}


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def get_json(url, timeout=30):
    return json.loads(fetch(url, timeout))


# ---------------------------------------------------------------- WETTER

def open_meteo_daily(lat, lon, model):
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_gusts_10m_max,wind_speed_10m_max,weather_code",
        "timezone": "Europe/Berlin", "forecast_days": 16, "models": model,
    })
    return get_json("https://api.open-meteo.com/v1/forecast?" + q)


def open_meteo_hourly(lat, lon):
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,apparent_temperature,precipitation_probability,wind_speed_10m,wind_gusts_10m,weather_code",
        "timezone": "Europe/Berlin", "forecast_days": 16,
    })
    return get_json("https://api.open-meteo.com/v1/forecast?" + q)


def val_for_date(daily, key, day):
    try:
        i = daily["time"].index(day)
        return daily[key][i]
    except (ValueError, KeyError, IndexError):
        return None


def build_location(loc, trip_day):
    tmax, tmin, rain, gust, wind, codes = [], [], [], [], [], []
    for m in MODELS:
        try:
            d = open_meteo_daily(loc["lat"], loc["lon"], m)["daily"]
        except Exception as e:
            print("  model", m, "failed:", e)
            continue
        for arr, key in ((tmax, "temperature_2m_max"), (tmin, "temperature_2m_min"),
                         (rain, "precipitation_probability_max"), (gust, "wind_gusts_10m_max"),
                         (wind, "wind_speed_10m_max"), (codes, "weather_code")):
            v = val_for_date(d, key, trip_day)
            if v is not None:
                arr.append(v)

    hourly_rows, morning_temp, apparent_noon, thunder = [], None, None, False
    try:
        h = open_meteo_hourly(loc["lat"], loc["lon"])["hourly"]
        for idx, t in enumerate(h["time"]):
            if not t.startswith(trip_day):
                continue
            hh = int(t[11:13])
            code = h["weather_code"][idx]
            if code in THUNDER:
                thunder = True
            if hh == 9:
                morning_temp = h["temperature_2m"][idx]
            if hh == 12:
                apparent_noon = h["apparent_temperature"][idx]
            if hh in (9, 12, 15, 18, 21):
                hourly_rows.append({
                    "time": f"{hh:02d}:00",
                    "temp": round(h["temperature_2m"][idx]),
                    "app": round(h["apparent_temperature"][idx]),
                    "rain": h["precipitation_probability"][idx],
                    "wind": round(h["wind_speed_10m"][idx]),
                    "gust": round(h["wind_gusts_10m"][idx]),
                    "code": code, "desc": WMO.get(code, "?"),
                })
    except Exception as e:
        print("  hourly failed:", e)

    def med(a):
        return round(statistics.median(a), 1) if a else None

    tmax_med = med(tmax)
    spread = round(max(tmax) - min(tmax), 1) if len(tmax) >= 2 else 0
    rain_max = max(rain) if rain else None       # konservativ: höchster Wert
    gust_max = round(max(gust)) if gust else None
    wind_max = round(max(wind)) if wind else None
    codes_thunder = thunder or any(c in THUNDER for c in codes)

    ampel, why = weather_ampel(tmax_med, rain_max, gust_max, codes_thunder, spread,
                               has_data=bool(tmax))

    return {
        "id": loc["id"], "name": loc["name"], "short": loc.get("short", loc["name"]),
        "lat": loc["lat"], "lon": loc["lon"],
        "tmax_median": tmax_med, "tmax_min": (round(min(tmax), 1) if tmax else None),
        "tmax_max": (round(max(tmax), 1) if tmax else None),
        "tmin_median": med(tmin), "spread": spread, "model_count": len(tmax),
        "morning_temp": (round(morning_temp) if morning_temp is not None else None),
        "apparent_noon": (round(apparent_noon) if apparent_noon is not None else None),
        "rain_prob": rain_max, "gust_max": gust_max, "wind_max": wind_max,
        "thunder": codes_thunder, "hourly": hourly_rows,
        "ampel": ampel, "ampel_why": why,
    }


def weather_ampel(tmax, rain, gust, thunder, spread, has_data):
    if not has_data or tmax is None:
        return "gelb", "Keine gesicherten Daten – im Zweifel vorsichtig."
    # ROT
    if thunder:
        return "rot", "Gewittergefahr – auf dem Wasser gefährlich."
    if rain is not None and rain >= 70:
        return "rot", f"Hohe Regenwahrscheinlichkeit ({rain}%)."
    if gust is not None and gust >= 50:
        return "rot", f"Kräftige Böen bis {gust} km/h."
    if tmax < 15:
        return "rot", f"Zu kalt (max {tmax}°C)."
    # GRÜN nur wenn alles passt und Modelle einig
    if (rain is not None and rain < 30 and gust is not None and gust < 35
            and tmax >= 22 and spread <= 5):
        return "gruen", f"Passt: ~{round(tmax)}°C, wenig Regen, mäßiger Wind."
    # sonst GELB
    reasons = []
    if rain is not None and rain >= 30:
        reasons.append(f"Regenrisiko {rain}%")
    if gust is not None and gust >= 35:
        reasons.append(f"Böen bis {gust} km/h")
    if tmax < 22:
        reasons.append(f"nur ~{round(tmax)}°C")
    if spread > 5:
        reasons.append(f"Modelle uneinig (±{spread}°)")
    return "gelb", "Grenzwertig: " + (", ".join(reasons) if reasons else "Lage unsicher") + "."


# ---------------------------------------------------------------- ALGEN

def algae_status(query, official_url):
    news, status, ampel, summary = [], "unklar", "gelb", ""
    last_checked = datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y, %H:%M")
    try:
        url = ("https://news.google.com/rss/search?q="
               + urllib.parse.quote(query) + "&hl=de&gl=DE&ceid=DE:de")
        data = fetch(url)
        for it in re.findall(r"<item>(.*?)</item>", data, re.S)[:12]:
            t = re.search(r"<title>(.*?)</title>", it, re.S)
            l = re.search(r"<link>(.*?)</link>", it, re.S)
            p = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
            s = re.search(r"<source[^>]*>(.*?)</source>", it, re.S)
            if not t:
                continue
            title = html.unescape(re.sub(r"<.*?>", "", t.group(1))).strip()
            news.append({
                "title": title,
                "link": (l.group(1).strip() if l else ""),
                "date": (p.group(1).strip() if p else ""),
                "source": (html.unescape(s.group(1)).strip() if s else ""),
            })
    except Exception as e:
        print("  news failed:", e)

    joined = " ".join(n["title"].lower() for n in news[:6])
    warn_kw = ["warnt", "warnung", "abgeraten", "abraten", "blaualg", "gestorben",
               "stirbt", "erkrankt", "breitet sich aus", "gefahr", "verdacht", "belastung"]
    clear_kw = ["entwarnung", "aufgehoben", "warnung aufgehoben", "keine gefahr",
                "wieder baden", "unbedenklich"]
    has_warn = any(k in joined for k in warn_kw)
    has_clear = any(k in joined for k in clear_kw)

    if has_clear and not has_warn:
        status, ampel = "Entwarnung gemeldet", "gruen"
        summary = "Aktuelle Meldungen deuten auf eine Entwarnung hin. Trotzdem vor Ort prüfen."
    elif has_warn:
        # konservativ: bei Todesfall/Ausbreitung Rot, sonst Gelb
        if any(k in joined for k in ["gestorben", "stirbt", "breitet sich aus"]):
            status, ampel = "Warnung aktiv", "rot"
        else:
            status, ampel = "Warnung aktiv", "gelb"
        summary = ("Es wird weiterhin vor dem Baden in der Donau abgeraten "
                   "(Blaualgen/Cyanobakterien). Nicht schwimmen, nichts schlucken, "
                   "Hände nicht im Flusswasser abspülen.")
    else:
        status, ampel = "Status unklar", "gelb"
        summary = ("Keine eindeutigen aktuellen Meldungen gefunden. Im Zweifel kein "
                   "Baden – amtliche Seite prüfen (Link unten).")

    return {
        "status_label": status, "ampel": ampel, "summary": summary,
        "last_checked": last_checked, "official_url": official_url,
        "news": news[:6],
    }


# ---------------------------------------------------------------- AMPEL-MIX

RANK = {"gruen": 0, "gelb": 1, "rot": 2}
INV = {0: "gruen", 1: "gelb", 2: "rot"}


def worst(*amps):
    return INV[max(RANK.get(a, 1) for a in amps)]


# ---------------------------------------------------------------- MAIN

def main():
    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    trip_day = cfg["trip_date"]
    today = date.today()
    days_until = (date.fromisoformat(trip_day) - today).days

    print("Trip:", trip_day, "in", days_until, "Tagen")

    locations = [build_location(l, trip_day) for l in cfg["locations"]]
    weather_ampel_overall = worst(*[l["ampel"] for l in locations]) if locations else "gelb"

    algae = algae_status(cfg["algae_news_query"], cfg["official_url"])
    trip_ampel = worst(weather_ampel_overall, algae["ampel"])

    # Vorheriger Stand -> Trends
    prev = {}
    dpath = os.path.join(ROOT, "data.json")
    if os.path.exists(dpath):
        try:
            old = json.load(open(dpath, encoding="utf-8"))
            prev = {
                "generated_at": old.get("generated_at"),
                "locations": {l["id"]: {"tmax_median": l.get("tmax_median"),
                                        "rain_prob": l.get("rain_prob"),
                                        "ampel": l.get("ampel")}
                              for l in old.get("locations", [])},
                "algae_ampel": old.get("algae", {}).get("ampel"),
                "weather_ampel": old.get("weather_ampel_overall"),
            }
        except Exception:
            prev = {}

    def trend(new, old):
        if new is None or old is None:
            return "flat"
        if new > old + 0.4:
            return "up"
        if new < old - 0.4:
            return "down"
        return "flat"

    for l in locations:
        po = prev.get("locations", {}).get(l["id"], {})
        l["trend_tmax"] = trend(l["tmax_median"], po.get("tmax_median"))
        l["prev_tmax"] = po.get("tmax_median")

    data = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "generated_label": datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y, %H:%M"),
        "title": cfg["title"], "trip_date": trip_day,
        "trip_date_label": date.fromisoformat(trip_day).strftime("%d.%m.%Y"),
        "trip_start_time": cfg.get("trip_start_time", ""),
        "days_until": days_until,
        "locations": locations,
        "weather_ampel_overall": weather_ampel_overall,
        "algae": algae,
        "trip_ampel": trip_ampel,
        "previous": prev,
    }

    json.dump(data, open(dpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("data.json geschrieben. Wetter:", weather_ampel_overall,
          "| Algen:", algae["ampel"], "| Trip:", trip_ampel)

    # history.json
    hpath = os.path.join(ROOT, "history.json")
    hist = []
    if os.path.exists(hpath):
        try:
            hist = json.load(open(hpath, encoding="utf-8"))
        except Exception:
            hist = []
    hist.append({
        "ts": data["generated_at"], "label": data["generated_label"],
        "tmax": {l["id"]: l["tmax_median"] for l in locations},
        "rain": {l["id"]: l["rain_prob"] for l in locations},
        "weather_ampel": weather_ampel_overall, "algae_ampel": algae["ampel"],
    })
    hist = hist[-120:]
    json.dump(hist, open(hpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("history.json:", len(hist), "Einträge")


if __name__ == "__main__":
    main()
