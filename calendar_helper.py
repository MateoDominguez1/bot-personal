import requests
from datetime import datetime, timedelta
from icalendar import Calendar
from dateutil import tz

ICAL_URL = "https://ical-polimiapp.polimi.it/11102152/zPIWhFDdIK4a5lrroUcbZm44rfBGzbjl"
MILAN_TZ = tz.gettz("Europe/Rome")

_cache = {"data": None, "fetched": None}
CACHE_TTL = timedelta(hours=1)

DAY_NAMES = {
    "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miercoles",
    "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sabado", "Sunday": "Domingo",
}


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


def _extract_aula(location: str) -> str:
    """Extrae numero/nombre del aula de la cadena de ubicacion."""
    if not location:
        return ""
    # Formato tipico: "Aula X.Y.Z - Edificio, Direccion, Ciudad"
    parts = location.split(",")
    first = parts[0].strip()
    # Remove common prefixes
    for prefix in ["Aula ", "Room ", "Sala "]:
        if first.startswith(prefix):
            return first
    return first


def _is_esame(event: dict) -> bool:
    cat = event.get("category", "").lower()
    summary = event.get("summary", "").lower()
    return "esame" in cat or "esame" in summary or "exam" in cat


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

        # categories field can be a list or string
        cat_raw = comp.get("categories")
        if cat_raw is None:
            cat = ""
        elif hasattr(cat_raw, "cats"):
            cat = ",".join(str(c) for c in cat_raw.cats)
        else:
            cat = str(cat_raw)

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


def _fmt_event(e: dict) -> str:
    start = e["start"].strftime("%H:%M")
    end = e["end"].strftime("%H:%M") if e["end"] else "?"
    aula = _extract_aula(e["location"])

    # Extract just the course name (remove prefix like "Lezione: Didattica - ")
    summary = e["summary"]
    for prefix in ["Lezione: Didattica - ", "Lezione: ", "Esame: "]:
        if summary.startswith(prefix):
            summary = summary[len(prefix):]
            break

    if _is_esame(e):
        icon = "📝"
        label = f"EXAMEN: {summary}"
    else:
        icon = "📚"
        label = summary

    line = f"  {icon} {start}-{end}  {label}"
    if aula:
        line += f"  ({aula})"
    return line


def get_today_schedule() -> str:
    today = datetime.now(MILAN_TZ).date()
    events = [e for e in _get_events(start_date=today, end_date=today) if not _is_esame(e)]
    if not events:
        return "No tenes clases hoy."
    header = f"*Clases de hoy ({today.strftime('%d/%m/%Y')}):*\n"
    return header + "\n".join(_fmt_event(e) for e in events)


def get_tomorrow_schedule() -> str:
    tomorrow = (datetime.now(MILAN_TZ) + timedelta(days=1)).date()
    events = [e for e in _get_events(start_date=tomorrow, end_date=tomorrow) if not _is_esame(e)]
    if not events:
        return "No tenes clases manana."
    header = f"*Clases de manana ({tomorrow.strftime('%d/%m/%Y')}):*\n"
    return header + "\n".join(_fmt_event(e) for e in events)


def _build_week_message(monday, title: str) -> str:
    friday = monday + timedelta(days=6)
    events = [e for e in _get_events(start_date=monday, end_date=friday) if not _is_esame(e)]
    if not events:
        return f"No tenes clases {title}."

    days = {}
    for e in events:
        day_key = e["start"].strftime("%A %d/%m")
        days.setdefault(day_key, []).append(e)

    lines = [f"*Horario {title}:*\n"]
    for day_key, evts in days.items():
        day_esp = day_key
        for eng, esp in DAY_NAMES.items():
            day_esp = day_esp.replace(eng, esp)
        lines.append(f"\n*{day_esp}*")
        for e in evts:
            lines.append(_fmt_event(e))
    return "\n".join(lines)


def get_week_schedule() -> str:
    today = datetime.now(MILAN_TZ).date()
    monday = today - timedelta(days=today.weekday())
    return _build_week_message(monday, "de esta semana")


def get_next_week_schedule() -> str:
    today = datetime.now(MILAN_TZ).date()
    monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
    return _build_week_message(monday, "de la semana que viene")


def get_next_exams() -> str:
    today = datetime.now(MILAN_TZ).date()
    events = _get_events(start_date=today, category="Esame")
    if not events:
        return "No hay examenes proximos en tu calendario."

    lines = ["*Proximos examenes:*\n"]
    for e in events:
        date_str = e["start"].strftime("%d/%m/%Y %H:%M")
        summary = e["summary"]
        if summary.startswith("Esame: "):
            summary = summary[7:]
        aula = _extract_aula(e["location"])
        lines.append(f"📝 *{summary}*\n  {date_str}" + (f"  ({aula})" if aula else ""))
    return "\n\n".join(lines)


def get_next_class(materia=None) -> str:
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
    aula = _extract_aula(e["location"])
    summary = e["summary"]
    for prefix in ["Lezione: Didattica - ", "Lezione: "]:
        if summary.startswith(prefix):
            summary = summary[len(prefix):]
            break
    return f"*Proxima clase{' de ' + materia if materia else ''}:*\n{summary}\n{date_str}" + (f"  ({aula})" if aula else "")


def get_upcoming_exams_for_briefing(days: int = 20) -> list:
    """Devuelve examenes en los proximos N dias para el briefing."""
    today = datetime.now(MILAN_TZ).date()
    end = today + timedelta(days=days)
    events = [e for e in _get_events(start_date=today, end_date=end) if _is_esame(e)]
    result = []
    for e in events:
        summary = e["summary"]
        if summary.startswith("Esame: "):
            summary = summary[7:]
        days_left = (e["start"].date() - today).days
        result.append({
            "materia": summary,
            "fecha": e["start"].strftime("%d/%m"),
            "hora": e["start"].strftime("%H:%M"),
            "dias_restantes": days_left,
        })
    return result


def get_today_schedule_for_briefing() -> list:
    """Devuelve lista compacta de clases de hoy para el briefing: [{materia, hora_inicio, hora_fin, aula, tipo}]"""
    today = datetime.now(MILAN_TZ).date()
    events = [e for e in _get_events(start_date=today, end_date=today) if not _is_esame(e)]
    result = []
    for e in events:
        summary = e["summary"]
        for prefix in ["Lezione: Didattica - ", "Lezione: ", "Esame: "]:
            if summary.startswith(prefix):
                summary = summary[len(prefix):]
                break
        result.append({
            "materia": summary,
            "hora_inicio": e["start"].strftime("%H:%M"),
            "hora_fin": e["end"].strftime("%H:%M") if e["end"] else "?",
            "aula": _extract_aula(e["location"]),
            "tipo": "Examen" if _is_esame(e) else "Clase",
        })
    return result


def get_schedule_context() -> str:
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
        aula = _extract_aula(e["location"]) or "sin aula"
        tipo = "Examen" if _is_esame(e) else "Clase"
        summary = e["summary"]
        for prefix in ["Lezione: Didattica - ", "Lezione: ", "Esame: "]:
            if summary.startswith(prefix):
                summary = summary[len(prefix):]
                break
        lines.append(f"{start}-{end_t} | {tipo} | {summary} | {aula}")

    return "\n".join(lines)
