import os
import unicodedata
from datetime import datetime, timedelta, date
from dateutil import tz, parser as dateutil_parser

try:
    import caldav
    from caldav.elements import dav
    CALDAV_AVAILABLE = True
except ImportError:
    CALDAV_AVAILABLE = False

ICLOUD_URL = "https://caldav.icloud.com/"
APPLE_ID = os.environ.get("APPLE_ID")
APPLE_APP_PASSWORD = os.environ.get("APPLE_APP_PASSWORD")

MILAN_TZ = tz.gettz("Europe/Rome")


def _is_configured() -> bool:
    return bool(APPLE_ID and APPLE_APP_PASSWORD and CALDAV_AVAILABLE)


def _get_client():
    return caldav.DAVClient(
        url=ICLOUD_URL,
        username=APPLE_ID,
        password=APPLE_APP_PASSWORD,
    )


def _get_calendars(principal, cal_type="VEVENT"):
    """Returns all calendars matching the component type."""
    calendars = []
    for cal in principal.calendars():
        try:
            info = cal.get_properties([dav.DisplayName()])
            name = info.get("{DAV:}displayname", "")
            # Check which component types are supported
            comp_types = cal.get_supported_components()
            if cal_type in comp_types:
                calendars.append({"name": name, "cal": cal})
        except Exception:
            continue
    return calendars


DAY_NAMES_ES = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "domingo": 6,
}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _resolve_date(fecha: str) -> str:
    """Convierte cualquier string de fecha a YYYY-MM-DD."""
    if not fecha:
        return date.today().isoformat()

    # Already ISO format YYYY-MM-DD
    try:
        datetime.fromisoformat(fecha)
        return fecha
    except (ValueError, TypeError):
        pass

    # Normalize: lowercase + strip accents
    fecha_norm = _strip_accents(fecha.lower().strip())

    # Spanish day name
    if fecha_norm in DAY_NAMES_ES:
        today = date.today()
        target_weekday = DAY_NAMES_ES[fecha_norm]
        days_ahead = (target_weekday - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return (today + timedelta(days=days_ahead)).isoformat()

    # Relative
    if fecha_norm in ("manana", "tomorrow"):
        return (date.today() + timedelta(days=1)).isoformat()
    if fecha_norm in ("hoy", "today"):
        return date.today().isoformat()

    # Try dateutil as fallback
    try:
        return dateutil_parser.parse(fecha, dayfirst=True).date().isoformat()
    except Exception:
        return date.today().isoformat()


def _fuzzy_match(query: str, options: list[str]) -> str | None:
    """Returns best matching option name or None."""
    q = query.lower().strip()
    # Exact match
    for opt in options:
        if opt.lower() == q:
            return opt
    # Substring match
    for opt in options:
        if q in opt.lower() or opt.lower() in q:
            return opt
    # Word match
    for word in q.split():
        if len(word) >= 3:
            for opt in options:
                if word in opt.lower():
                    return opt
    return None


class AppleHelper:

    def list_calendars(self) -> list[str]:
        """Returns names of all event calendars."""
        if not _is_configured():
            return []
        try:
            with _get_client() as client:
                principal = client.principal()
                cals = _get_calendars(principal, "VEVENT")
                return [c["name"] for c in cals if c["name"]]
        except Exception as e:
            print(f"Apple list_calendars error: {e}")
            return []

    def list_reminder_lists(self) -> list[str]:
        """Returns names of all reminder lists (VTODO calendars)."""
        if not _is_configured():
            return []
        try:
            with _get_client() as client:
                principal = client.principal()
                cals = _get_calendars(principal, "VTODO")
                return [c["name"] for c in cals if c["name"]]
        except Exception as e:
            print(f"Apple list_reminder_lists error: {e}")
            return []

    def add_calendar_event(self, titulo: str, fecha: str, hora: str | None,
                           duracion_min: int, calendario: str | None,
                           descripcion: str = "") -> dict:
        """
        Returns:
          {"ok": True, "msg": "..."} on success
          {"needs_selection": True, "options": [...]} if calendar not specified or not found
          {"error": "..."} on failure
        """
        if not _is_configured():
            return {"error": "Apple Calendar no configurado. Necesito APPLE_ID y APPLE_APP_PASSWORD."}

        try:
            with _get_client() as client:
                principal = client.principal()
                cals = _get_calendars(principal, "VEVENT")
                cal_names = [c["name"] for c in cals]

                # Find the calendar
                target = None
                if calendario:
                    matched_name = _fuzzy_match(calendario, cal_names)
                    if matched_name:
                        for c in cals:
                            if c["name"] == matched_name:
                                target = c["cal"]
                                break

                if not target:
                    return {"needs_selection": True, "options": cal_names,
                            "message": f"¿A qué calendario agrego *{titulo}*?"}

                # Build the event datetime
                tz_milan = MILAN_TZ
                fecha_iso = _resolve_date(fecha)
                if hora:
                    h, m = map(int, hora.split(":"))
                    dt_start = datetime.fromisoformat(fecha_iso).replace(
                        hour=h, minute=m, tzinfo=tz_milan)
                else:
                    dt_start = datetime.fromisoformat(fecha_iso).replace(
                        hour=9, minute=0, tzinfo=tz_milan)
                dt_end = dt_start + timedelta(minutes=duracion_min)

                from icalendar import Calendar as iCal, Event
                cal = iCal()
                event = Event()
                event.add("summary", titulo)
                event.add("dtstart", dt_start)
                event.add("dtend", dt_end)
                if descripcion:
                    event.add("description", descripcion)
                cal.add_component(event)

                target.save_event(cal.to_ical())
                return {"ok": True, "msg": f"Evento *{titulo}* agregado al calendario *{target.name}* para el {fecha_iso}" + (f" a las {hora}" if hora else "")}
        except Exception as e:
            print(f"Apple add_event error: {e}")
            return {"error": f"Error al agregar evento: {e}"}

    def add_reminder(self, titulo: str, lista: str | None,
                     fecha: str | None = None) -> dict:
        """
        Returns:
          {"ok": True, "msg": "..."} on success
          {"needs_selection": True, "options": [...]} if list not specified or not found
          {"error": "..."} on failure
        """
        if not _is_configured():
            return {"error": "Apple Reminders no configurado. Necesito APPLE_ID y APPLE_APP_PASSWORD."}

        try:
            with _get_client() as client:
                principal = client.principal()
                cals = _get_calendars(principal, "VTODO")
                list_names = [c["name"] for c in cals]

                target = None
                if lista:
                    matched_name = _fuzzy_match(lista, list_names)
                    if matched_name:
                        for c in cals:
                            if c["name"] == matched_name:
                                target = c["cal"]
                                break

                if not target:
                    return {"needs_selection": True, "options": list_names,
                            "message": f"¿En qué lista agrego *{titulo}*?"}

                from icalendar import Calendar as iCal, Todo
                cal = iCal()
                todo = Todo()
                todo.add("summary", titulo)
                todo.add("status", "NEEDS-ACTION")
                if fecha:
                    fecha_iso = _resolve_date(fecha)
                    due = datetime.fromisoformat(fecha_iso).replace(tzinfo=MILAN_TZ)
                    todo.add("due", due)
                cal.add_component(todo)

                target.save_todo(cal.to_ical())
                return {"ok": True, "msg": f"Recordatorio *{titulo}* agregado a *{target.name}*" + (f" para el {fecha}" if fecha else "")}
        except Exception as e:
            print(f"Apple add_reminder error: {e}")
            return {"error": f"Error al agregar recordatorio: {e}"}
