import os
import requests
from flask import Flask, request
from ai_helper import AIHelper
from notion_helper import NotionHelper
from calendar_helper import (
    get_today_schedule, get_tomorrow_schedule, get_week_schedule,
    get_next_week_schedule, get_next_exams, get_next_class,
    get_schedule_context, get_today_schedule_for_briefing,
)
from apple_helper import AppleHelper
import pdf_helper

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

ai = AIHelper()
notion = NotionHelper()
apple = AppleHelper()

# Per-chat state
conversations = {}       # chat_id -> message history
pdf_sessions = {}        # chat_id -> extracted PDF text
pending_actions = {}     # chat_id -> {"action": ..., "intent": ...}


def send_message(chat_id, text, parse_mode="Markdown"):
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            requests.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": chat_id,
                "text": text[i:i+4000],
                "parse_mode": parse_mode,
            })
    else:
        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        })


def send_document(chat_id, file_bytes: bytes, filename: str, caption: str = ""):
    requests.post(
        f"{TELEGRAM_API}/sendDocument",
        data={"chat_id": chat_id, "caption": caption},
        files={"document": (filename, file_bytes, "application/pdf")},
    )


def send_action(chat_id, action="typing"):
    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": action,
    })


# ── Webhook ──────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        handle_message(data["message"])
    return "ok"


@app.route("/")
def health():
    return "Bot is running!"


@app.route("/set_webhook")
def set_webhook():
    url = request.host_url.rstrip("/") + "/webhook"
    r = requests.post(f"{TELEGRAM_API}/setWebhook", json={"url": url})
    return r.json()


# ── Handlers ─────────────────────────────────────────────

def handle_message(message):
    chat_id = message["chat"]["id"]

    if "photo" in message:
        handle_photo(chat_id, message)
        return

    if "document" in message:
        handle_document(chat_id, message)
        return

    if "voice" in message:
        handle_voice(chat_id, message["voice"])
        return

    if "text" not in message:
        send_message(chat_id, "Puedo procesar texto, audio, fotos y archivos.")
        return

    text = message["text"]
    if text.startswith("/"):
        handle_command(chat_id, text)
    else:
        handle_text(chat_id, text)


def handle_command(chat_id, text):
    parts = text.split(maxsplit=1)
    command = parts[0].lower().split("@")[0]
    args = parts[1] if len(parts) > 1 else ""

    if command == "/start":
        send_message(chat_id, WELCOME_MSG)

    elif command == "/setup":
        send_action(chat_id)
        send_message(chat_id, notion.setup_databases())

    # ── Facultad ─────────────────────────────────────

    elif command == "/materias":
        send_action(chat_id)
        send_message(chat_id, notion.list_materias())

    elif command == "/clase":
        if not args:
            send_message(chat_id, "Ej: /clase analisi | Limites de funciones")
            return
        send_action(chat_id)
        p = [x.strip() for x in args.split("|")]
        if len(p) < 2:
            send_message(chat_id, "Separa con |\nEj: /clase analisi | Limites")
            return
        send_message(chat_id, notion.add_clase(
            p[0], p[1], p[2] if len(p) > 2 else None, p[3] if len(p) > 3 else None,
        ))

    elif command == "/clases":
        send_action(chat_id)
        send_message(chat_id, notion.list_clases(args if args else None))

    elif command == "/estado":
        if not args or "|" not in args:
            send_message(chat_id, "Ej: /estado Limites | Aprendido")
            return
        send_action(chat_id)
        p = [x.strip() for x in args.split("|")]
        send_message(chat_id, notion.update_clase_estado(p[0], p[1]))

    elif command == "/examenes":
        send_action(chat_id)
        send_message(chat_id, notion.list_examenes())

    elif command == "/horario":
        send_action(chat_id)
        arg = args.strip().lower() if args else "hoy"
        if arg in ("manana", "mañana", "tomorrow"):
            send_message(chat_id, get_tomorrow_schedule())
        elif arg in ("semana", "week"):
            send_message(chat_id, get_week_schedule())
        elif arg in ("semana siguiente", "proxima semana", "next week"):
            send_message(chat_id, get_next_week_schedule())
        elif arg in ("examenes", "parciales", "exams"):
            send_message(chat_id, get_next_exams())
        else:
            send_message(chat_id, get_today_schedule())

    # ── Finanzas ─────────────────────────────────────

    elif command == "/gasto":
        if not args:
            send_message(chat_id, "Ej: /gasto 500 almuerzo Comida")
            return
        send_action(chat_id)
        amount, desc, cat = _parse_finance_args(args)
        if amount is None:
            amount, desc, cat = ai.parse_expense(args)
            if amount is None:
                send_message(chat_id, "No entendi el monto. Ej: /gasto 500 almuerzo")
                return
        send_message(chat_id, notion.add_transaction(amount, desc, "Gasto", cat))

    elif command == "/ingreso":
        if not args:
            send_message(chat_id, "Ej: /ingreso 50000 sueldo Sueldo")
            return
        send_action(chat_id)
        amount, desc, cat = _parse_finance_args(args)
        if amount is None:
            amount, desc, cat = ai.parse_expense(args)
            if amount is None:
                send_message(chat_id, "No entendi el monto.")
                return
        send_message(chat_id, notion.add_transaction(amount, desc, "Ingreso", cat))

    elif command == "/fijo":
        if not args:
            send_message(chat_id, (
                "Ej: /fijo 500 | Netflix | Gasto | Servicios | 15\n"
                "Ej: /fijo 50000 | Sueldo | Ingreso | Sueldo | 1"
            ))
            return
        send_action(chat_id)
        p = [x.strip() for x in args.split("|")]
        try:
            amount = float(p[0].replace("$", "").replace(",", "."))
            desc = p[1] if len(p) > 1 else "Sin descripcion"
            tipo = p[2] if len(p) > 2 else "Gasto"
            cat = p[3] if len(p) > 3 else "Otros"
            dia = int(p[4]) if len(p) > 4 else 1
        except (ValueError, IndexError):
            send_message(chat_id, "Formato: /fijo monto | descripcion | Gasto/Ingreso | categoria | dia")
            return
        send_message(chat_id, notion.add_fixed(amount, desc, tipo, cat, dia))

    elif command == "/fijos":
        send_action(chat_id)
        send_message(chat_id, notion.list_fixed())

    elif command == "/finanzas":
        send_action(chat_id)
        period = args.strip().lower() if args else "today"
        if period in ("mes", "month", "mensual"):
            period = "month"
        send_message(chat_id, notion.list_finances(period))

    elif command == "/gastos":
        send_action(chat_id)
        send_message(chat_id, notion.list_finances("today"))

    elif command == "/balance":
        send_action(chat_id)
        send_message(chat_id, notion.get_balance())

    # ── Personal ─────────────────────────────────────

    elif command == "/nota":
        if not args:
            send_message(chat_id, "Ej: /nota llamar al medico manana")
            return
        send_action(chat_id)
        send_message(chat_id, notion.add_note(args))

    elif command == "/tarea":
        if not args:
            send_message(chat_id, "Ej: /tarea entregar TP de fisica")
            return
        send_action(chat_id)
        send_message(chat_id, notion.add_task(args))

    elif command == "/tareas":
        send_action(chat_id)
        send_message(chat_id, notion.list_tasks())

    elif command == "/habito":
        if not args:
            send_message(chat_id, "Ej: /habito ejercicio")
            return
        send_action(chat_id)
        send_message(chat_id, notion.track_habit(args))

    elif command == "/habitos":
        send_action(chat_id)
        send_message(chat_id, notion.list_habits())

    # ── Rutina ───────────────────────────────────────

    elif command == "/rutina":
        send_action(chat_id)
        dia = args.strip().capitalize() if args else None
        send_message(chat_id, notion.list_routine(dia))

    elif command == "/ejercicio":
        if not args:
            send_message(chat_id, "Ej: /ejercicio Press banca | Lunes | 4 | 10 | Pecho")
            return
        send_action(chat_id)
        p = [x.strip() for x in args.split("|")]
        send_message(chat_id, notion.add_exercise(
            p[0],
            p[1] if len(p) > 1 else "Lunes",
            int(p[2]) if len(p) > 2 and p[2].isdigit() else 0,
            p[3] if len(p) > 3 else "",
            p[4] if len(p) > 4 else "",
        ))

    # ── Estudio ──────────────────────────────────────

    elif command == "/flashcards":
        if not args:
            send_message(chat_id, "Ej: /flashcards derivadas")
            return
        send_action(chat_id)
        send_message(chat_id, ai.generate_flashcards(args))

    elif command == "/quiz":
        if not args:
            send_message(chat_id, "Ej: /quiz integrales")
            return
        send_action(chat_id)
        send_message(chat_id, ai.generate_quiz(args))

    elif command == "/resumir":
        if not args:
            send_message(chat_id, "Ej: /resumir [texto]")
            return
        send_action(chat_id)
        send_message(chat_id, ai.summarize(args))

    elif command == "/explicar":
        if not args:
            send_message(chat_id, "Ej: /explicar transformada de Fourier")
            return
        send_action(chat_id)
        send_message(chat_id, ai.explain(args))

    elif command == "/briefing":
        send_action(chat_id)
        _send_briefing(chat_id)

    else:
        send_message(chat_id, "Comando no reconocido. Usa /start para ver los comandos.")


def _parse_finance_args(args: str):
    """Parsea: monto descripcion [categoria]"""
    parts = args.split()
    try:
        amount = float(parts[0].replace("$", "").replace(",", "."))
    except (ValueError, IndexError):
        return None, None, None

    categories = [
        "Comida", "Transporte", "Entretenimiento", "Salud", "Educacion",
        "Alquiler", "Servicios", "Ropa", "Sueldo", "Freelance", "Regalo", "Otros",
    ]
    cat = "Otros"
    desc_parts = parts[1:]

    if desc_parts and desc_parts[-1].capitalize() in categories:
        cat = desc_parts[-1].capitalize()
        desc_parts = desc_parts[:-1]

    desc = " ".join(desc_parts) if desc_parts else "Sin descripcion"
    return amount, desc, cat


# ── Fotos (recibos/tickets) ─────────────────────────────

def handle_photo(chat_id, message):
    send_action(chat_id)

    photo = message["photo"][-1]
    file_info = requests.get(
        f"{TELEGRAM_API}/getFile", params={"file_id": photo["file_id"]}
    ).json()
    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    image_data = requests.get(file_url).content
    caption = message.get("caption", "")

    result = ai.analyze_receipt(image_data, caption)

    if not result:
        send_message(chat_id, "No pude analizar la imagen. Intenta con mejor calidad o agrega una descripcion.")
        return

    tipo = result.get("tipo", "Gasto")
    amount = result.get("amount", 0)
    store = result.get("store", "")
    items = result.get("items", [])
    cat = result.get("category", "Otros")

    # Build rich description
    if store and items:
        items_str = ", ".join(f"{it['name']}" + (f" ${it['price']}" if it.get("price") else "")
                               for it in items[:8])
        desc = f"{store}: {items_str}"
    elif store:
        desc = store
    else:
        desc = result.get("description", "Sin descripcion")

    # Notes with full item detail
    notes = ""
    if items:
        notes = "\n".join(
            f"- {it.get('name','?')}: ${it.get('price', '?')}" for it in items
        )

    if amount <= 0:
        send_message(chat_id, f"Detecte: {desc}\nPero no pude leer el monto. Usa:\n/gasto [monto] {desc}")
        return

    response = notion.add_transaction(amount, desc, tipo, cat, notes)
    emoji = "🔴" if tipo == "Gasto" else "🟢"
    detail = f"\n*Detalle:*\n{notes}" if notes else ""
    send_message(chat_id, f"Foto analizada {emoji}\n{response}{detail}")


# ── Documentos (PDF, rutina, etc.) ──────────────────────

def handle_document(chat_id, message):
    send_action(chat_id)

    doc = message["document"]
    file_name = doc.get("file_name", "").lower()
    mime_type = doc.get("mime_type", "")

    file_info = requests.get(
        f"{TELEGRAM_API}/getFile", params={"file_id": doc["file_id"]}
    ).json()
    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    file_data = requests.get(file_url).content
    caption = message.get("caption", "").lower()

    # ── PDF ──────────────────────────────────────────
    if file_name.endswith(".pdf") or mime_type == "application/pdf":
        text, pages = pdf_helper.extract_text(file_data)
        if not text.strip():
            send_message(chat_id, "No pude extraer texto del PDF. Puede ser que sea un PDF escaneado.")
            return
        pdf_sessions[chat_id] = text
        send_message(chat_id, (
            f"PDF recibido ({pages} paginas) 📄\n\n"
            "¿Que querés hacer?\n"
            "- _\"resumi el pdf\"_\n"
            "- _\"haceme flashcards del pdf\"_\n"
            "- _\"haceme un quiz del pdf\"_\n"
            "- _\"haceme un apunte en PDF\"_\n"
            "- O preguntame algo sobre el contenido"
        ))
        return

    # ── Rutina de gym ────────────────────────────────
    if "rutina" in caption or "gym" in caption or "ejercicio" in caption or "rutina" in file_name:
        try:
            text_content = file_data.decode("utf-8", errors="replace")
            exercises = ai.parse_routine(text_content)
            if exercises:
                send_message(chat_id, notion.add_routine_bulk(exercises))
            else:
                send_message(chat_id, "No pude extraer ejercicios del archivo. Verifica el formato.")
        except Exception:
            send_message(chat_id, "No pude leer el archivo.")
        return

    # ── Texto generico ───────────────────────────────
    try:
        text_content = file_data.decode("utf-8", errors="replace")
        if len(text_content) > 100:
            pdf_sessions[chat_id] = text_content
            summary = ai.summarize(text_content[:5000])
            send_message(chat_id, f"*Resumen del archivo:*\n\n{summary}")
        else:
            send_message(chat_id, "Archivo recibido pero muy corto. Agrega 'rutina' como caption si es tu rutina de gym.")
    except Exception:
        send_message(chat_id, "No pude leer el archivo.")


def handle_text(chat_id, text):
    send_action(chat_id)

    # ── Resolver accion pendiente (seleccion de calendario/lista) ──
    if chat_id in pending_actions:
        pending = pending_actions.pop(chat_id)
        _resolve_pending(chat_id, text, pending)
        return

    intent = ai.classify_intent(text)
    t = intent.get("type", "chat")

    # ── Facultad ─────────────────────────────────────
    if t == "clase":
        send_message(chat_id, notion.add_clase(
            intent.get("materia", ""),
            intent.get("tema", text),
            intent.get("fecha"),
            intent.get("link"),
        ))
    elif t == "ver_clases":
        send_message(chat_id, notion.list_clases(intent.get("estado")))
    elif t == "estado_clase":
        send_message(chat_id, notion.update_clase_estado(
            intent.get("tema", ""), intent.get("estado", ""),
        ))
    elif t == "ver_materias":
        send_message(chat_id, notion.list_materias())
    elif t == "ver_examenes":
        send_message(chat_id, notion.list_examenes())

    # ── Finanzas ─────────────────────────────────────
    elif t == "gasto":
        send_message(chat_id, notion.add_transaction(
            intent.get("amount", 0), intent.get("description", text),
            "Gasto", intent.get("category", "Otros"),
        ))
    elif t == "ingreso":
        send_message(chat_id, notion.add_transaction(
            intent.get("amount", 0), intent.get("description", text),
            "Ingreso", intent.get("category", "Otros"),
        ))
    elif t == "fijo":
        send_message(chat_id, notion.add_fixed(
            intent.get("amount", 0), intent.get("description", text),
            intent.get("tipo_fijo", "Gasto"), intent.get("category", "Otros"),
            intent.get("dia_mes", 1),
        ))
    elif t == "ver_finanzas":
        send_message(chat_id, notion.list_finances(intent.get("periodo", "today")))
    elif t == "ver_fijos":
        send_message(chat_id, notion.list_fixed())
    elif t == "balance":
        send_message(chat_id, notion.get_balance())
    elif t == "eliminar_gasto":
        send_message(chat_id, notion.delete_transaction(intent.get("descripcion", text), "Gasto"))
    elif t == "eliminar_ingreso":
        send_message(chat_id, notion.delete_transaction(intent.get("descripcion", text), "Ingreso"))

    # ── Personal ─────────────────────────────────────
    elif t == "nota":
        send_message(chat_id, notion.add_note(intent.get("content", text)))
    elif t == "tarea":
        send_message(chat_id, notion.add_task(intent.get("content", text)))
    elif t == "ver_tareas":
        send_message(chat_id, notion.list_tasks())
    elif t == "habito":
        send_message(chat_id, notion.track_habit(intent.get("content", text)))
    elif t == "ver_habitos":
        send_message(chat_id, notion.list_habits())

    # ── Rutina ───────────────────────────────────────
    elif t == "ver_rutina":
        send_message(chat_id, notion.list_routine(intent.get("dia")))
    elif t == "ejercicio":
        send_message(chat_id, notion.add_exercise(
            intent.get("ejercicio", text),
            intent.get("dia", "Lunes"),
            intent.get("series", 0),
            intent.get("reps", ""),
            intent.get("musculo", ""),
        ))

    # ── Estudio ──────────────────────────────────────
    elif t == "flashcards":
        send_message(chat_id, ai.generate_flashcards(intent.get("tema", text)))
    elif t == "quiz":
        send_message(chat_id, ai.generate_quiz(intent.get("tema", text)))
    elif t == "resumir":
        send_message(chat_id, ai.summarize(intent.get("content", text)))
    elif t == "explicar":
        send_message(chat_id, ai.explain(intent.get("content", text)))
    elif t == "briefing":
        _send_briefing(chat_id)

    # ── PDF ──────────────────────────────────────────
    elif t == "pdf_pregunta":
        pdf_text = pdf_sessions.get(chat_id, "")
        question = intent.get("content", text)
        if not pdf_text:
            # No PDF loaded — treat as study question
            send_message(chat_id, "No tenes ningun PDF cargado. Mandame un PDF primero.")
            return
        q_lower = question.lower()
        if any(w in q_lower for w in ("resumi", "resumen", "resume")):
            send_message(chat_id, ai.summarize(pdf_text[:8000]))
        elif any(w in q_lower for w in ("flashcard", "tarjeta")):
            send_message(chat_id, ai.generate_flashcards(f"el siguiente texto:\n{pdf_text[:4000]}"))
        elif any(w in q_lower for w in ("quiz", "pregunta")):
            send_message(chat_id, ai.generate_quiz(f"el siguiente texto:\n{pdf_text[:4000]}"))
        elif any(w in q_lower for w in ("apunte", "apuntes", "pdf")):
            _send_pdf_apunte(chat_id, question, pdf_text)
        else:
            send_message(chat_id, ai.answer_pdf_question(question, pdf_text))

    # ── Horario / Calendario ─────────────────────────
    elif t == "horario":
        periodo = intent.get("periodo", "hoy")
        materia = intent.get("materia")
        if periodo == "hoy":
            send_message(chat_id, get_today_schedule())
        elif periodo == "manana":
            send_message(chat_id, get_tomorrow_schedule())
        elif periodo == "semana":
            send_message(chat_id, get_week_schedule())
        elif periodo == "semana_siguiente":
            send_message(chat_id, get_next_week_schedule())
        elif periodo == "examenes":
            send_message(chat_id, get_next_exams())
        elif periodo == "proxima_clase":
            send_message(chat_id, get_next_class(materia))
        else:
            ctx = get_schedule_context()
            send_message(chat_id, ai.answer_calendar_question(text, ctx))

    # ── Apple Calendar ───────────────────────────────
    elif t == "apple_evento":
        result = apple.add_calendar_event(
            titulo=intent.get("titulo", text),
            fecha=intent.get("fecha", ""),
            hora=intent.get("hora"),
            duracion_min=intent.get("duracion_min", 60),
            calendario=intent.get("calendario"),
            descripcion=intent.get("descripcion", ""),
        )
        _handle_apple_result(chat_id, result, intent, "apple_evento")

    elif t == "apple_recordatorio":
        result = apple.add_reminder(
            titulo=intent.get("titulo", text),
            lista=intent.get("lista"),
            fecha=intent.get("fecha"),
        )
        _handle_apple_result(chat_id, result, intent, "apple_recordatorio")
        # Also add to Notion tasks
        if result.get("ok"):
            notion.add_task(intent.get("titulo", text))

    # ── Busqueda web / noticias ──────────────────────
    elif t == "busqueda":
        send_message(chat_id, ai.web_search(intent.get("query", text)))

    # ── Chat general ─────────────────────────────────
    else:
        # Check if text is PDF-related and there's a PDF loaded
        pdf_text = pdf_sessions.get(chat_id, "")
        text_lower = text.lower()
        if pdf_text and any(w in text_lower for w in ("pdf", "documento", "archivo", "texto")):
            send_message(chat_id, ai.answer_pdf_question(text, pdf_text))
            return

        if chat_id not in conversations:
            conversations[chat_id] = []
        history = conversations[chat_id]
        response = ai.chat(text, history)
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": response})
        conversations[chat_id] = history[-20:]
        send_message(chat_id, response)


def _handle_apple_result(chat_id, result: dict, intent: dict, action_type: str):
    """Handles Apple Calendar/Reminders result, asking for selection if needed."""
    if result.get("ok"):
        send_message(chat_id, result["msg"])
    elif result.get("needs_selection"):
        options = result["options"]
        msg = result.get("message", "¿Donde lo agrego?") + "\n\n"
        msg += "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
        msg += "\n\nResponde con el numero o el nombre."
        send_message(chat_id, msg)
        pending_actions[chat_id] = {
            "action": action_type,
            "intent": intent,
            "options": options,
        }
    elif result.get("error"):
        send_message(chat_id, f"Error: {result['error']}")


def _resolve_pending(chat_id, text: str, pending: dict):
    """Resolves a pending Apple Calendar/Reminders selection."""
    options = pending["options"]
    intent = pending["intent"]
    action = pending["action"]

    # Try to match by number or name
    selected = None
    text_stripped = text.strip()
    if text_stripped.isdigit():
        idx = int(text_stripped) - 1
        if 0 <= idx < len(options):
            selected = options[idx]
    else:
        # Fuzzy match from apple_helper
        from apple_helper import _fuzzy_match
        selected = _fuzzy_match(text_stripped, options)

    if not selected:
        send_message(chat_id, "No entendi. Responde con el numero de la opcion.")
        pending_actions[chat_id] = pending  # put it back
        return

    if action == "apple_evento":
        intent["calendario"] = selected
        result = apple.add_calendar_event(
            titulo=intent.get("titulo", ""),
            fecha=intent.get("fecha", ""),
            hora=intent.get("hora"),
            duracion_min=intent.get("duracion_min", 60),
            calendario=selected,
            descripcion=intent.get("descripcion", ""),
        )
    else:  # apple_recordatorio
        intent["lista"] = selected
        result = apple.add_reminder(
            titulo=intent.get("titulo", ""),
            lista=selected,
            fecha=intent.get("fecha"),
        )
        if result.get("ok"):
            notion.add_task(intent.get("titulo", ""))

    if result.get("ok"):
        send_message(chat_id, result["msg"])
    elif result.get("error"):
        send_message(chat_id, f"Error: {result['error']}")


def _send_briefing(chat_id):
    tasks = notion.get_pending_tasks_raw()
    clases = notion.get_pending_clases_raw()
    habits = notion.get_today_habits_raw()
    expenses = notion.get_today_expenses_raw()
    schedule = get_today_schedule_for_briefing()
    send_message(chat_id, ai.generate_briefing(tasks, habits, expenses, clases, schedule))


def _send_pdf_apunte(chat_id, topic: str, pdf_text: str | None = None):
    """Genera un apunte en PDF y lo manda como archivo."""
    send_action(chat_id, "upload_document")
    content = ai.generate_pdf_apunte(topic, pdf_text)
    pdf_bytes = pdf_helper.generate_pdf(topic, content)
    if pdf_bytes:
        filename = topic[:40].replace(" ", "_") + ".pdf"
        send_document(chat_id, pdf_bytes, filename, f"Apunte: {topic}")
    else:
        # Fallback: send as text
        send_message(chat_id, content)


# ── Voice ───────────────────────────────────────────────

def handle_voice(chat_id, voice):
    send_action(chat_id)
    file_info = requests.get(
        f"{TELEGRAM_API}/getFile", params={"file_id": voice["file_id"]}
    ).json()
    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    audio_data = requests.get(file_url).content

    transcription = ai.transcribe(audio_data)
    if not transcription:
        send_message(chat_id, "No pude entender el audio. Intenta de nuevo.")
        return

    send_message(chat_id, f"_Transcripcion:_ {transcription}")
    handle_text(chat_id, transcription)


# ── Mensaje de bienvenida ────────────────────────────────

WELCOME_MSG = """*Hola! Soy tu asistente personal*

*Facultad*
/horario - Clases de hoy
/horario manana|semana|semana siguiente|examenes
/materias - Ver materias
/clase materia | tema - Agregar clase
/clases - Ver clases pendientes
/estado tema | estado - Cambiar estado
/examenes - Proximos examenes (Notion)

*Finanzas*
/gasto monto descripcion - Registrar gasto
/ingreso monto descripcion - Registrar ingreso
/fijo monto | desc | tipo | cat | dia - Gasto/ingreso fijo
/fijos - Ver fijos mensuales
/finanzas - Resumen de hoy
/finanzas mes - Resumen del mes
/balance - Balance actual
Podes mandar una FOTO de un ticket!

*Notas y Tareas*
/nota texto - Guardar nota
/tarea descripcion - Agregar tarea
/tareas - Ver pendientes

*Rutina*
/rutina - Ver rutina completa
/rutina Lunes - Ver dia especifico
/ejercicio nombre | dia | series | reps | musculo
Manda un archivo con caption "rutina" para importar!

*Estudio*
/flashcards tema - Flashcards
/quiz tema - Quiz
/resumir texto - Resumir
/explicar concepto - Explicar
Manda un PDF para estudiar desde el!

*Habitos*
/habito nombre - Registrar
/habitos - Ver hoy

*Otros*
/briefing - Resumen del dia

Hablame normal, manda audios, fotos o PDFs!"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
