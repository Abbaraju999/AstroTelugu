import streamlit as st
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import swisseph as swe

# -------------------- EPHEMERIS SETUP --------------------
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

MONTHS = [
    "చైత్రం", "వైశాఖం", "జ్యేష్ఠం", "ఆషాఢం",
    "శ్రావణం", "భాద్రపదం", "ఆశ్వయుజం", "కార్తీకం",
    "మార్గశిరం", "పుష్యం", "మాఘం", "ఫాల్గుణం"
]

TITHIS = [
    "పాడ్యమి", "విదియ", "తదియ", "చవితి", "పంచమి",
    "షష్ఠి", "సప్తమి", "అష్టమి", "నవమి", "దశమి",
    "ఏకాదశి", "ద్వాదశి", "త్రయోదశి", "చతుర్దశి", "పౌర్ణమి"
]

NAKSHATRAS = [
    "అశ్విని", "భరణి", "కృత్తిక", "రోహిణి", "మృగశిర",
    "ఆరుద్ర", "పునర్వసు", "పుష్యమి", "ఆశ్లేష", "మఖ",
    "పుబ్బ", "ఉత్తర", "హస్త", "చిత్త", "స్వాతి",
    "విశాఖ", "అనూరాధ", "జ్యేష్ఠ", "మూల", "పూర్వాషాఢ",
    "ఉత్తరాషాఢ", "శ్రవణం", "ధనిష్ఠ", "శతభిషం",
    "పూర్వాభాద్ర", "ఉత్తరాభాద్ర", "రేవతి"
]

YOGAS = [
    "విష్కంభం", "ప్రీతి", "ఆయుష్మాన్", "సౌభాగ్యం", "శోభనం",
    "అతిగండం", "సుకర్మ", "ధృతి", "శూలం", "గండం",
    "వృద్ధి", "ధ్రువం", "వ్యాఘాతం", "హర్షణం", "వజ్రం",
    "సిద్ధి", "వ్యతీపాతం", "వరీయాన్", "పరిఘం", "శివం",
    "సిద్ధం", "సాధ్యం", "శుభం", "శుక్లం", "బ్రహ్మం",
    "ఇంద్రం", "వైధృతి"
]

MOVING_KARANAS = ["బవ", "బాలవ", "కౌలవ", "తైతుల", "గరజ", "వణిజ", "విష్టి (భద్ర)"]
FIXED_KARANAS = ["శకుని", "చతుష్పాత్", "నాగ"]
WEEKDAYS = ["సోమవారం", "మంగళవారం", "బుధవారం", "గురువారం", "శుక్రవారం", "శనివారం", "ఆదివారం"]

RAHU_SEGMENT = [2, 7, 5, 6, 4, 3, 8]
YAMA_SEGMENT = [4, 3, 2, 1, 7, 6, 5]
GULIKA_SEGMENT = [6, 5, 4, 3, 2, 1, 7]

# -------------------- HELPER FUNCTIONS --------------------

@st.cache_data
def get_location_details(location_name):
    geolocator = Nominatim(user_agent="telugu_panchangam_web_app")
    location = geolocator.geocode(location_name)
    if not location:
        raise ValueError(f"'{location_name}' కనుగొనబడలేదు. దయచేసి సరైన నగరం పేరు ఇవ్వండి.")
    lat, lon = location.latitude, location.longitude
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon) or "Asia/Kolkata"
    return lat, lon, tz_name

def to_julian_day(dt_local):
    dt_utc = dt_local.astimezone(timezone.utc)
    decimal_hour = dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600 + dt_utc.microsecond / 3_600_000_000
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, decimal_hour)

def from_julian_day(jd, tz):
    seconds = (jd - 2440587.5) * 86400.0
    return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)).astimezone(tz)

def format_time(dt):
    return dt.strftime("%d-%m-%Y %I:%M:%S %p") if dt else "లభ్యం కాలేదు"

def planet_longitude(jd, planet, sidereal=False):
    flags = swe.FLG_SWIEPH | (swe.FLG_SIDEREAL if sidereal else 0)
    values, _ = swe.calc_ut(jd, planet, flags)
    return values[0] % 360.0

def phase_angle(jd):
    return (planet_longitude(jd, swe.MOON) - planet_longitude(jd, swe.SUN)) % 360.0

def yoga_angle(jd):
    return (planet_longitude(jd, swe.SUN, True) + planet_longitude(jd, swe.MOON, True)) % 360.0

def next_angular_boundary(jd, angle_function, segment_size):
    angle_now = angle_function(jd)
    distance = segment_size - (angle_now % segment_size)
    if distance < 1e-8:
        distance = segment_size
    low, high = jd, jd + 2.0
    progress = lambda at_jd: (angle_function(at_jd) - angle_now) % 360.0
    while progress(high) < distance:
        high += 1.0
    for _ in range(55):
        mid = (low + high) / 2.0
        if progress(mid) >= distance:
            high = mid
        else:
            low = mid
    return (low + high) / 2.0

def signed_lunar_phase(jd):
    return (phase_angle(jd) + 180.0) % 360.0 - 180.0

def find_new_moons(jd):
    start, end, step = jd - 40.0, jd + 40.0, 0.25
    roots, t1, f1 = [], start, signed_lunar_phase(start)
    while t1 < end:
        t2 = min(t1 + step, end)
        f2 = signed_lunar_phase(t2)
        if f1 <= 0.0 < f2:
            low, high = t1, t2
            for _ in range(55):
                mid = (low + high) / 2.0
                if signed_lunar_phase(mid) >= 0:
                    high = mid
                else:
                    low = mid
            roots.append((low + high) / 2.0)
        t1, f1 = t2, f2
    return max([x for x in roots if x <= jd]), min([x for x in roots if x > jd])

def get_amanta_masam(prev_nm, next_nm):
    t, prev_sign, ingresses = prev_nm, int(planet_longitude(prev_nm, swe.SUN, True) // 30), []
    while t < next_nm:
        t2 = min(t + 0.20, next_nm)
        curr_sign = int(planet_longitude(t2, swe.SUN, True) // 30)
        if curr_sign != prev_sign:
            ingresses.append(curr_sign)
        prev_sign, t = curr_sign, t2
    if not ingresses:
        return "అధిక " + MONTHS[(int(planet_longitude(next_nm, swe.SUN, True) // 30) + 1) % 12]
    if len(ingresses) > 1:
        return "క్షయ మాసం"
    return MONTHS[ingresses[0]]

def get_tithi(jd, tz):
    angle = phase_angle(jd)
    idx = int(angle // 12.0)
    paksha = "శుక్ల పక్షం" if idx < 15 else "కృష్ణ పక్షం"
    tithi = TITHIS[idx] if idx < 15 else ("అమావాస్య" if idx == 29 else TITHIS[idx - 15])
    return paksha, tithi, from_julian_day(next_angular_boundary(jd, phase_angle, 12.0), tz)

def get_nakshatra(jd, tz):
    moon_sid = planet_longitude(jd, swe.MOON, True)
    span = 360.0 / 27.0
    idx = int(moon_sid // span)
    pada = int((moon_sid % span) // (span / 4.0)) + 1
    end_jd = next_angular_boundary(jd, lambda x: planet_longitude(x, swe.MOON, True), span)
    return NAKSHATRAS[idx], pada, from_julian_day(end_jd, tz)

def get_yoga(jd, tz):
    span = 360.0 / 27.0
    idx = int(yoga_angle(jd) // span)
    return YOGAS[idx], from_julian_day(next_angular_boundary(jd, yoga_angle, span), tz)

def get_karana(jd, tz):
    idx = int(phase_angle(jd) // 6.0)
    name = "కింస్తుఘ్న" if idx == 0 else (MOVING_KARANAS[(idx - 1) % 7] if idx <= 56 else FIXED_KARANAS[idx - 57])
    return name, from_julian_day(next_angular_boundary(jd, phase_angle, 6.0), tz)

def solar_event(local_date, tz, lat, lon, flag):
    jd_start = to_julian_day(datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0, tzinfo=tz))
    res, times = swe.rise_trans(jd_start, swe.SUN, flag, (lon, lat, 0.0), 0.0, 0.0, swe.FLG_SWIEPH)
    return from_julian_day(times[0], tz) if res >= 0 else None

def calculate_day_periods(local_date, tz, lat, lon):
    sr = solar_event(local_date, tz, lat, lon, swe.CALC_RISE)
    ss = solar_event(local_date, tz, lat, lon, swe.CALC_SET)
    if not sr or not ss or ss <= sr:
        return sr, ss, None, None, None
    dur, wd = (ss - sr) / 8, local_date.weekday()
    p = lambda seg: f"{(sr + dur*(seg-1)).strftime('%I:%M %p')} – {(sr + dur*seg).strftime('%I:%M %p')}"
    return sr, ss, p(RAHU_SEGMENT[wd]), p(YAMA_SEGMENT[wd]), p(GULIKA_SEGMENT[wd])

# -------------------- STREAMLIT WEB UI --------------------

st.set_page_config(page_title="తెలుగు పంచాంగం", page_icon="🕉️", layout="centered")

st.title("🕉️ తెలుగు పంచాంగం (Telugu Panchangam)")
st.caption("తేదీ, సమయం మరియు నగరం ఆధారంగా కచ్చితమైన పంచాంగ వివరాలు")

with st.form("panchangam_form"):
    col1, col2 = st.columns(2)
    with col1:
        selected_date = st.date_input("తేదీ (Date)", value=date.today())
    with col2:
        selected_time = st.time_input("సమయం (Time)", value=datetime.now().time())
    
    location_input = st.text_input("నగరం / దేశం (City / Country)", value="Hyderabad, India", help="ఉదా: Vijayawada, Singapore, New York, USA")
    submitted = st.form_submit_button("పంచాంగం లెక్కించు", use_container_width=True, type="primary")

if submitted:
    try:
        with st.spinner("లెక్కిస్తోంది..."):
            lat, lon, tz_name = get_location_details(location_input.strip())
            try:
                tz = ZoneInfo(tz_name)
            except ZoneInfoNotFoundError:
                tz = ZoneInfo("Asia/Kolkata")
            
            local_dt = datetime.combine(selected_date, selected_time).replace(tzinfo=tz)
            jd = to_julian_day(local_dt)
            
            paksha, tithi, tithi_end = get_tithi(jd, tz)
            nakshatra, pada, nakshatra_end = get_nakshatra(jd, tz)
            yoga, yoga_end = get_yoga(jd, tz)
            karana, karana_end = get_karana(jd, tz)
            prev_nm, next_nm = find_new_moons(jd)
            masam = get_amanta_masam(prev_nm, next_nm)
            sr, ss, rahu, yama, gulika = calculate_day_periods(selected_date, tz, lat, lon)

        st.success(f"📍 **{location_input}** ({lat:.2f}°, {lon:.2f}°) | టైమ్ జోన్: `{tz_name}`")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("తెలుగు మాసం", masam)
        c2.metric("పక్షం", paksha)
        c3.metric("వారం", WEEKDAYS[local_dt.weekday()])

        st.divider()
        
        st.subheader("పంచాంగ అంశాలు")
        st.markdown(f"""
- **తిథి:** {tithi} *(ముగింపు: {format_time(tithi_end)})*
- **నక్షత్రం:** {nakshatra} – పాదం {pada} *(ముగింపు: {format_time(nakshatra_end)})*
- **యోగం:** {yoga} *(ముగింపు: {format_time(yoga_end)})*
- **కరణం:** {karana} *(ముగింపు: {format_time(karana_end)})*
""")

        st.divider()

        st.subheader("సూర్యోదయం & కాలాలు")
        col_a, col_b = st.columns(2)
        with col_a:
            st.info(f"🌅 **సూర్యోదయం:** {format_time(sr)}\n\n🌇 **సూర్యాస్తమయం:** {format_time(ss)}")
        with col_b:
            st.warning(f"⏳ **రాహుకాలం:** {rahu}\n\n⏳ **యమగండం:** {yama}\n\n⏳ **గుళిక కాలం:** {gulika}")

    except Exception as e:
        st.error(f"లోపం (Error): {e}")
