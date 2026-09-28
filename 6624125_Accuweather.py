"""
Thailand Weather (AccuWeather) - Streamlit app

Features
1. Choose city
2. Map with temperature colour labels
3. Weather emoji
4. Relative humidity and wind speed
5. UV index
+ 7-day forecast

Run:
    pip install -r requirements.txt
    export ACCUWEATHER_API_KEY="your_key"      (Windows: set ACCUWEATHER_API_KEY=your_key)
    streamlit run app.py
"""
import os
from datetime import datetime

import folium
import requests
import streamlit as st
from streamlit_folium import st_folium

BASE = "https://dataservice.accuweather.com"

# name: (lat, lon)
CITIES = {
    "Bangkok": (13.7563, 100.5018),
    "Chiang Mai": (18.7883, 98.9853),
    "Chiang Rai": (19.9105, 99.8406),
    "Khon Kaen": (16.4322, 102.8236),
    "Nakhon Ratchasima": (14.9799, 102.0978),
    "Ubon Ratchathani": (15.2448, 104.8473),
    "Phitsanulok": (16.8211, 100.2659),
    "Kanchanaburi": (14.0228, 99.5328),
    "Pattaya": (12.9236, 100.8825),
    "Hua Hin": (12.5684, 99.9577),
    "Surat Thani": (9.1382, 99.3217),
    "Phuket": (7.8804, 98.3923),
    "Hat Yai": (7.0084, 100.4747),
}


def get_api_key():
    key = os.getenv("ACCUWEATHER_API_KEY")
    if key:
        return key
    try:
        return st.secrets["ACCUWEATHER_API_KEY"]
    except Exception:
        return None


# ---------- AccuWeather calls (cached to save your daily quota) ----------
@st.cache_data(ttl=60 * 60 * 24 * 30, show_spinner=False)
def location_key(lat, lon, api_key):
    r = requests.get(
        f"{BASE}/locations/v1/cities/geoposition/search",
        params={"apikey": api_key, "q": f"{lat},{lon}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["Key"]


@st.cache_data(ttl=60 * 60 * 3, show_spinner=False)
def daily_forecast(key, api_key):
    """Try 10-day (paid plans) and fall back to 5-day (free plan)."""
    for horizon in ("10day", "5day"):
        r = requests.get(
            f"{BASE}/forecasts/v1/daily/{horizon}/{key}",
            params={"apikey": api_key, "metric": "true", "details": "true"},
            timeout=15,
        )
        if r.status_code in (401, 403):
            continue
        r.raise_for_status()
        return r.json()["DailyForecasts"][:7], horizon
    raise RuntimeError("Forecast not allowed for this API key.")


# ---------- helpers ----------
def parse_day(d):
    day = d.get("Day", {})
    uv = next((p for p in d.get("AirAndPollen", []) if p["Name"] == "UVIndex"), {})
    hum = day.get("RelativeHumidity") or {}
    return {
        "date": datetime.fromisoformat(d["Date"]),
        "tmin": d["Temperature"]["Minimum"]["Value"],
        "tmax": d["Temperature"]["Maximum"]["Value"],
        "icon": day.get("Icon", 0),
        "phrase": day.get("IconPhrase", ""),
        "humidity": hum.get("Average"),
        "wind": (day.get("Wind", {}).get("Speed", {}) or {}).get("Value"),
        "uv": uv.get("Value"),
        "uv_cat": uv.get("Category", ""),
    }


def emoji(icon):
    if icon in (1, 2, 30):
        return "☀️"
    if icon in (3, 4, 5):
        return "🌤️"
    if icon in (6, 7, 8):
        return "☁️"
    if icon == 11:
        return "🌫️"
    if icon in (12, 18, 26, 29):
        return "🌧️"
    if icon in (13, 14):
        return "🌦️"
    if icon in (15, 16, 17, 41, 42):
        return "⛈️"
    if icon in (19, 20, 21, 22, 23, 24, 25):
        return "❄️"
    if icon == 31:
        return "🥶"
    if icon == 32:
        return "💨"
    return "🌡️"


def temp_color(t):
    if t < 25:
        return "#3b82f6"  # blue
    if t < 30:
        return "#22c55e"  # green
    if t < 34:
        return "#f59e0b"  # orange
    if t < 38:
        return "#ef4444"  # red
    return "#991b1b"      # dark red


def uv_label(v):
    if v is None:
        return "-"
    if v <= 2:
        return "🟢 Low"
    if v <= 5:
        return "🟡 Moderate"
    if v <= 7:
        return "🟠 High"
    if v <= 10:
        return "🔴 Very high"
    return "🟣 Extreme"


def build_map(today_by_city, selected):
    m = folium.Map(location=[13.0, 101.0], zoom_start=6, tiles="cartodbpositron")
    for name, (lat, lon) in CITIES.items():
        info = today_by_city.get(name)
        if info:
            color = temp_color(info["tmax"])
            label = f'{emoji(info["icon"])} {info["tmax"]:.0f}°'
            popup = f"{name}: {info['phrase']}, {info['tmin']:.0f} to {info['tmax']:.0f} °C"
        else:
            color, label, popup = "#9ca3af", "?", name
        border = "3px solid black" if name == selected else "2px solid white"
        html = (
            f'<div style="background:{color};color:white;border:{border};'
            "border-radius:14px;padding:2px 6px;font-size:12px;font-weight:600;"
            f'white-space:nowrap;text-align:center;">{label}</div>'
        )
        folium.Marker(
            [lat, lon],
            tooltip=name,
            popup=popup,
            icon=folium.DivIcon(html=html, icon_size=(70, 24), icon_anchor=(35, 12)),
        ).add_to(m)
    return m


# ---------- UI ----------
st.set_page_config(page_title="Thailand Weather", page_icon="🌦️", layout="wide")
st.title("🌦️ Thailand Weather")
st.caption("Data from AccuWeather")

api_key = get_api_key()
if not api_key:
    st.error("Set your key first: export ACCUWEATHER_API_KEY=your_key")
    st.stop()

# Feature 1: choose city
city = st.sidebar.selectbox("Choose city", list(CITIES.keys()))
show_all = st.sidebar.checkbox(
    "Load all cities on map",
    help="Uses about 2 API calls per city the first time (location key + forecast). "
    "Results are cached.",
)

try:
    lat, lon = CITIES[city]
    key = location_key(lat, lon, api_key)
    raw, horizon = daily_forecast(key, api_key)
    days = [parse_day(d) for d in raw]
except Exception as e:
    st.error(f"Could not load forecast: {e}")
    st.stop()

if horizon == "5day":
    st.info("Your API plan only returns 5 days. A plan with the 10-day endpoint gives the full 7 days.")

# data for the map
today_by_city = {city: days[0]}
if show_all:
    with st.spinner("Loading all cities..."):
        for name, (la, lo) in CITIES.items():
            if name in today_by_city:
                continue
            try:
                k = location_key(la, lo, api_key)
                r, _ = daily_forecast(k, api_key)
                today_by_city[name] = parse_day(r[0])
            except Exception:
                pass

# Today summary (features 3, 4, 5)
t = days[0]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(f"{emoji(t['icon'])} {city}", f"{t['tmax']:.0f}°C", t["phrase"])
c2.metric("Low", f"{t['tmin']:.0f}°C")
c3.metric("💧 Humidity", f"{t['humidity']:.0f}%" if t["humidity"] is not None else "-")
c4.metric("🌬️ Wind", f"{t['wind']:.0f} km/h" if t["wind"] is not None else "-")
c5.metric("☀️ UV index", f"{t['uv']}" if t["uv"] is not None else "-", uv_label(t["uv"]))

# Feature 2: map with temperature colours
st.subheader("Map")
st.markdown(
    "🔵 &lt;25°C &nbsp; 🟢 25-29 &nbsp; 🟠 30-33 &nbsp; 🔴 34-37 &nbsp; 🟤 38+ &nbsp; (daily high)",
    unsafe_allow_html=True,
)
st_folium(build_map(today_by_city, city), height=480, use_container_width=True, returned_objects=[])

# 7-day forecast
st.subheader(f"{len(days)}-day forecast for {city}")
cols = st.columns(len(days))
for col, d in zip(cols, days):
    with col:
        st.markdown(f"**{d['date']:%a}**  \n{d['date']:%d %b}")
        st.markdown(f"<div style='font-size:36px'>{emoji(d['icon'])}</div>", unsafe_allow_html=True)
        st.markdown(
            f"<span style='color:{temp_color(d['tmax'])};font-weight:700'>{d['tmax']:.0f}°</span>"
            f" / {d['tmin']:.0f}°",
            unsafe_allow_html=True,
        )
        st.caption(d["phrase"])
        st.write(f"💧 {d['humidity']:.0f}%" if d["humidity"] is not None else "💧 -")
        st.write(f"🌬️ {d['wind']:.0f} km/h" if d["wind"] is not None else "🌬️ -")
        st.write(f"UV {d['uv'] if d['uv'] is not None else '-'}  \n{uv_label(d['uv'])}")
