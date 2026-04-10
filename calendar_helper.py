import requests
from datetime import datetime, timedelta
from icalendar import Calendar
from dateutil import tz

ICAL_URL = "https://ical-polimiapp.polimi.it/11102152/zPIWhFDdIK4a5lrroUcbZm44rfBGzbjl"
MILAN_TZ = tz.gettz("Europe/Rome")

_cache = {"data": None, "fetched": None}
CACHE_TTL = timedelta(hours=1)


def _fetch_calendar():
    now = datetime.now()
    if _cache["data"] and _cache["fetched"] and (now - _cache["fetched"]) < CACHE_TTL:
        return _cache["data"]
    try:
        r = requests.get(ICAL_URL, timeout=15)
        r.raise_for_status()
        cal = Calendar.from_ical(r.content)
        _cache["data"] = cal
        _cache["fetched"] = now
        return cal
    except Exception as e:
        print(f"Calendar fetch error: {e}")
        return _cache["data"]


def _parse_dt(dt_prop):
    if dt_prop is None:
        return None
    dt = dt_prop.dt
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=MILAN_TZ)
        return dt.astimezone(MILAN_TZ)
    return datetime.combine(dt, datetime.min.time()).replace(tzinfo=MILAN_TZ)


def _get_events(start_date=None, end_date=None, category=None):
    cal = _fetch_calendar()
    if not cal:
        return []

    events = []
    for comp in cal.walk():
        if comp.name != "VEVENT":
            continue

        dt_start = _parse_dt(comp.get("dtstart"))
        dt_end = _parse_dt(comp.get("dtend"))
        if not dt_start:
            continue

        if start_date and dt_start.date() < start_date:
            continue
        if end_date and dt_start.date() > end_date:
            continue

        cat = str(comp.get("categories", ""))
        if category and category.lower() not in cat.lower():
            continue

        summary = str(comp.get("summary", ""))
        location = str(comp.get("location", ""))
        description = str(comp.get("description", ""))

        events.append({
            "summary": summary,
            "start": dt_start,
            "end": dt_end,
            "location": location,
            "description": description,
            "category": cat,
        })

    events.sort(key=lambda e: e["start"])
    return events


def _fmt_event(e):
    start = e["start"].strftime("%H:%M")
    end = e["end"].strftime("%H:%M") if e["end"] else "?"
    loc = e["location"]
    loc_short = loc.split(",")[0] if loc else ""
    return f"  {start}-{end}  {e['summary']}" + (f"\n  {loc_short}" if loc_short else "")


def get_today_schedule():
    today = datetime.now(MILAN_TZ).date()
    events = _get_events(start_date=today, end_date=today)
    if not events:
        return "No tenes clases ni examenes hoy."
    header = f"*Horario de hoy ({today.strftime('%d/%m/%Y')}):*\n"
    return header + "\n\n".join(_fmt_event(e) for e in events)


def get_tomorrow_schedule():
    tomorrow = (datetime.now(MILAN_TZ) + timedelta(days=1)).date()
    events = _get_events(start_date=tomorrow, end_date=tomorrow)
    if not events:
        return "No tenes clases ni examenes manana."
    header = f"*Horario de manana ({tomorrow.strftime('%d/%m/%Y')}):*\n"
    return header + "\n\n".join(_fmt_event(e) for e in events)


def get_week_schedule():
    today = datetime.now(MILAN_TZ).date()
    # Lunes de esta semana
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    events = _get_events(start_date=monday, end_date=friday)
    if not events:
        return "No tenes clases esta semana."

    days = {}
    for e in events:
        day_name = e["start"].strftime("%A %d/%m")
        days.setdefault(day_name, []).append(e)

    DAY_NAMES = {
        "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miercoles",
        "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sabado", "Sunday": "Domingo",
    }

    lines = ["*Horario de la semana:*\n"]
    for day, evts in days.items():
        for eng, esp in DAY_NAMES.items():
            day = day.replace(eng, esp)
        lines.append(f"\n*{day}*")
        for e in evts:
            lines.append(_fmt_event(e))
    return "\n".join(lines)


def get_next_exams():
    today = datetime.now(MILAN_TZ).date()
    events = _get_events(start_date=today, category="Esame")
    if not events:
        return "No hay examenes proximos en tu calendario."

    lines = ["*Proximos examenes:*\n"]
    for e in events:
        date_str = e["start"].strftime("%d/%m/%Y %H:%M")
        lines.append(f"  {e['summary']}\n  {date_str}")
        if e["location"]:
            lines.append(f"  {e['location'].split(',')[0]}")
        lines.append("")
    return "\n".join(lines)


def get_next_class(materia=None):
    today = datetime.now(MILAN_TZ).date()
    events = _get_events(start_date=today, category="Lezione")

    if materia:
        materia_lower = materia.lower()
        events = [e for e in events if materia_lower in e["summary"].lower()]

    now = datetime.now(MILAN_TZ)
    future = [e for e in events if e["start"] > now]

    if not future:
        q = f" de {materia}" if materia else ""
        return f"No hay proximas clases{q} en tu calendario."

    e = future[0]
    date_str = e["start"].strftime("%d/%m %H:%M")
    loc = e["location"].split(",")[0] if e["location"] else ""
    return f"*Proxima clase{' de ' + materia if materia else ''}:*\n{e['summary']}\n{date_str}" + (f"\n{loc}" if loc else "")


def get_schedule_context():
    """Devuelve contexto completo del calendario para que la IA responda preguntas."""
    today = datetime.now(MILAN_TZ).date()
    end = today + timedelta(days=30)
    events = _get_events(start_date=today, end_date=end)

    if not events:
        return "No hay eventos en los proximos 30 dias."

    lines = []
    for e in events:
        start = e["start"].strftime("%Y-%m-%d %H:%M")
        end_t = e["end"].strftime("%H:%M") if e["end"] else "?"
        loc = e["location"].split(",")[0] if e["location"] else "sin aula"
        lines.append(f"{start}-{end_t} | {e['summary']} | {loc} | {e['category']}")

    return "\n".join(lines)
