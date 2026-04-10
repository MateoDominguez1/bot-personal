import os
import requests
from flask import Flask, request
from ai_helper import AIHelper
from notion_helper import NotionHelper

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

ai = AIHelper()
notion = NotionHelper()

conversations = {}


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

    # Fotos (recibos/tickets)
    if "photo" in message:
        handle_photo(chat_id, message)
        return

    # Documentos/archivos (para importar rutina)
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
            send_message(chat_id, (
                "Usa: /clase materia | tema\n"
                "Ej: /clase analisi | Limites de funciones\n"
                "Extra: /clase analisi | Limites | 2026-04-15 | https://link"
            ))
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
            send_message(chat_id, (
                "Usa: /estado tema | nuevo estado\n"
                "Ej: /estado Limites | Aprendido"
            ))
            return
        send_action(chat_id)
        p = [x.strip() for x in args.split("|")]
        send_message(chat_id, notion.update_clase_estado(p[0], p[1]))

    elif command == "/examenes":
        send_action(chat_id)
        send_message(chat_id, notion.list_examenes())

    # ── Finanzas ─────────────────────────────────────

    elif command == "/gasto":
        if not args:
            send_message(chat_id, "Usa: /gasto monto descripcion [categoria]\nEj: /gasto 500 almuerzo Comida")
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
            send_message(chat_id, "Usa: /ingreso monto descripcion [categoria]\nEj: /ingreso 50000 sueldo Sueldo")
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
                "Usa: /fijo monto | descripcion | tipo | categoria | dia\n"
                "Ej: /fijo 500 | Netflix | Gasto | Suscripciones | 15\n"
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
            send_message(chat_id, "Usa: /nota tu nota")
            return
        send_action(chat_id)
        send_message(chat_id, notion.add_note(args))

    elif command == "/tarea":
        if not args:
            send_message(chat_id, "Usa: /tarea descripcion")
            return
        send_action(chat_id)
        send_message(chat_id, notion.add_task(args))

    elif command == "/tareas":
        send_action(chat_id)
        send_message(chat_id, notion.list_tasks())

    elif command == "/habito":
        if not args:
            send_message(chat_id, "Usa: /habito nombre\nEj: /habito ejercicio")
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
            send_message(chat_id, (
                "Usa: /ejercicio nombre | dia | series | reps | musculo\n"
                "Ej: /ejercicio Press banca | Lunes | 4 | 10 | Pecho"
            ))
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
            send_message(chat_id, "Usa: /flashcards tema")
            return
        send_action(chat_id)
        send_message(chat_id, ai.generate_flashcards(args))

    elif command == "/quiz":
        if not args:
            send_message(chat_id, "Usa: /quiz tema")
            return
        send_action(chat_id)
        send_message(chat_id, ai.generate_quiz(args))

    elif command == "/resumir":
        if not args:
            send_message(chat_id, "Usa: /resumir texto")
            return
        send_action(chat_id)
        send_message(chat_id, ai.summarize(args))

    elif command == "/explicar":
        if not args:
            send_message(chat_id, "Usa: /explicar concepto")
            return
        send_action(chat_id)
        send_message(chat_id, ai.explain(args))

    elif command == "/briefing":
        send_action(chat_id)
        tasks = notion.get_pending_tasks_raw()
        clases = notion.get_pending_clases_raw()
        habits = notion.get_today_habits_raw()
        expenses = notion.get_today_expenses_raw()
        send_message(chat_id, ai.generate_briefing(tasks, habits, expenses, clases))

    else:
        send_message(chat_id, "Comando no reconocido. Usa /start para ver los comandos.")


def _parse_finance_args(args: str):
    """Parsea: monto descripcion [categoria]"""
    parts = args.split()
    try:
        amount = float(parts[0].replace("$", "").replace(",", "."))
    except (ValueError, IndexError):
        return None, None, None

    # Categorias conocidas
    categories = [
        "Comida", "Transporte", "Entretenimiento", "Salud", "Educacion",
        "Alquiler", "Servicios", "Ropa", "Sueldo", "Freelance", "Regalo", "Otros",
    ]
    cat = "Otros"
    desc_parts = parts[1:]

    # Si la ultima palabra es una categoria
    if desc_parts and desc_parts[-1].capitalize() in categories:
        cat = desc_parts[-1].capitalize()
        desc_parts = desc_parts[:-1]

    desc = " ".join(desc_parts) if desc_parts else "Sin descripcion"
    return amount, desc, cat


# ── Fotos (recibos/tickets) ─────────────────────────────

def handle_photo(chat_id, message):
    """Recibe una foto, la analiza con IA y registra gasto/ingreso."""
    send_action(chat_id)

    # Tomar la foto de mayor resolucion
    photo = message["photo"][-1]
    file_info = requests.get(
        f"{TELEGRAM_API}/getFile", params={"file_id": photo["file_id"]}
    ).json()
    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    image_data = requests.get(file_url).content

    caption = message.get("caption", "")

    # Analizar con IA
    result = ai.analyze_receipt(image_data, caption)

    if not result:
        send_message(chat_id, "No pude analizar la imagen. Intenta con mejor calidad o agrega una descripcion.")
        return

    tipo = result.get("tipo", "Gasto")
    amount = result.get("amount", 0)
    desc = result.get("description", "Sin descripcion")
    cat = result.get("category", "Otros")

    if amount <= 0:
        send_message(chat_id, f"Detecte: {desc}\nPero no pude leer el monto. Usa:\n/gasto [monto] {desc}")
        return

    response = notion.add_transaction(amount, desc, tipo, cat)
    send_message(chat_id, f"Foto analizada:\n{response}")


# ── Documentos (importar rutina) ────────────────────────

def handle_document(chat_id, message):
    """Recibe un archivo y lo procesa (rutina, etc)."""
    send_action(chat_id)

    doc = message["document"]
    file_name = doc.get("file_name", "").lower()

    file_info = requests.get(
        f"{TELEGRAM_API}/getFile", params={"file_id": doc["file_id"]}
    ).json()
    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    file_data = requests.get(file_url).content

    caption = message.get("caption", "").lower()

    # Detectar si es una rutina
    if "rutina" in caption or "gym" in caption or "ejercicio" in caption or "rutina" in file_name:
        text_content = file_data.decode("utf-8", errors="replace")
        exercises = ai.parse_routine(text_content)
        if exercises:
            result = notion.add_routine_bulk(exercises)
            send_message(chat_id, result)
        else:
            send_message(chat_id, "No pude extraer ejercicios del archivo. Verifica el formato.")
    else:
        # Intentar leer como texto y resumir
        try:
            text_content = file_data.decode("utf-8", errors="replace")
            if len(text_content) > 100:
                summary = ai.summarize(text_content[:5000])
                send_message(chat_id, f"*Resumen del archivo:*\n\n{summary}")
            else:
                send_message(chat_id, "Archivo recibido pero no pude procesarlo. Agrega un caption como 'rutina' si es tu rutina de gym.")
        except Exception:
            send_message(chat_id, "No pude leer el archivo. Si es tu rutina, agrega 'rutina' como caption.")


def handle_text(chat_id, text):
    send_action(chat_id)
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
        tasks = notion.get_pending_tasks_raw()
        clases = notion.get_pending_clases_raw()
        habits = notion.get_today_habits_raw()
        expenses = notion.get_today_expenses_raw()
        send_message(chat_id, ai.generate_briefing(tasks, habits, expenses, clases))

    # ── Balance ───────────────────────────────────────
    elif t == "balance":
        send_message(chat_id, notion.get_balance())

    # ── Busqueda web / noticias ──────────────────────
    elif t == "busqueda":
        send_message(chat_id, ai.web_search(intent.get("query", text)))

    # ── Chat general ─────────────────────────────────
    else:
        if chat_id not in conversations:
            conversations[chat_id] = []
        history = conversations[chat_id]
        response = ai.chat(text, history)
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": response})
        conversations[chat_id] = history[-20:]
        send_message(chat_id, response)


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
        send_message(chat_id, "No pude entender el audio.")
        return

    send_message(chat_id, f"_Transcripcion:_ {transcription}")
    handle_text(chat_id, transcription)


# ── Mensaje de bienvenida ────────────────────────────────

WELCOME_MSG = """*Hola! Soy tu asistente personal*

*Facultad*
/materias - Ver materias
/clase materia | tema - Agregar clase
/clases - Ver clases pendientes
/estado tema | estado - Cambiar estado
/examenes - Proximos examenes

*Finanzas*
/gasto monto descripcion - Registrar gasto
/ingreso monto descripcion - Registrar ingreso
/fijo monto | desc | tipo | cat | dia - Gasto/ingreso fijo
/fijos - Ver fijos mensuales
/finanzas - Resumen de hoy
/finanzas mes - Resumen del mes
/balance - Cuanta plata tenes
Tambien podes mandar una FOTO de un ticket!

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

*Habitos*
/habito nombre - Registrar
/habitos - Ver hoy

*Otros*
/briefing - Resumen del dia
Preguntame lo que quieras, busco en internet!

Hablame normal o mandame audios!"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
