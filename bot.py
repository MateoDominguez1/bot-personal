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

# Historial de conversaciones en memoria (se reinicia con el server)
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

    if "voice" in message:
        handle_voice(chat_id, message["voice"])
        return

    if "text" not in message:
        send_message(chat_id, "Por ahora solo puedo procesar texto y audio.")
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
                "Usa: /clase [materia] | [tema]\n"
                "Ej: /clase analisi | Limites de funciones\n\n"
                "Opciones extra:\n"
                "/clase analisi | Limites | 2026-04-15\n"
                "/clase analisi | Limites | 2026-04-15 | https://link.com"
            ))
            return
        send_action(chat_id)
        clase_parts = [p.strip() for p in args.split("|")]
        if len(clase_parts) < 2:
            send_message(chat_id, "Separa materia y tema con |\nEj: /clase analisi | Limites")
            return
        materia = clase_parts[0]
        tema = clase_parts[1]
        fecha = clase_parts[2] if len(clase_parts) > 2 else None
        link = clase_parts[3] if len(clase_parts) > 3 else None
        send_message(chat_id, notion.add_clase(materia, tema, fecha, link))

    elif command == "/clases":
        send_action(chat_id)
        send_message(chat_id, notion.list_clases(args if args else None))

    elif command == "/estado":
        if not args or "|" not in args:
            send_message(chat_id, (
                "Usa: /estado [tema] | [nuevo estado]\n"
                "Ej: /estado Limites | Aprendido\n\n"
                "Estados: Clase Pendiente, Estudiando, Aprendido, "
                "Visto en clase, Clase pendiente a ver"
            ))
            return
        send_action(chat_id)
        estado_parts = [p.strip() for p in args.split("|")]
        send_message(chat_id, notion.update_clase_estado(estado_parts[0], estado_parts[1]))

    elif command == "/examenes":
        send_action(chat_id)
        send_message(chat_id, notion.list_examenes())

    # ── Personal ─────────────────────────────────────

    elif command == "/nota":
        if not args:
            send_message(chat_id, "Usa: /nota [tu nota]")
            return
        send_action(chat_id)
        send_message(chat_id, notion.add_note(args))

    elif command == "/tarea":
        if not args:
            send_message(chat_id, "Usa: /tarea [descripcion]")
            return
        send_action(chat_id)
        send_message(chat_id, notion.add_task(args))

    elif command == "/tareas":
        send_action(chat_id)
        send_message(chat_id, notion.list_tasks())

    elif command == "/gasto":
        if not args:
            send_message(chat_id, "Usa: /gasto [monto] [descripcion]\nEj: /gasto 500 almuerzo")
            return
        send_action(chat_id)
        gasto_parts = args.split(maxsplit=1)
        try:
            amount = float(gasto_parts[0].replace("$", "").replace(",", "."))
            desc = gasto_parts[1] if len(gasto_parts) > 1 else "Sin descripcion"
            category = "Otros"
        except ValueError:
            amount, desc, category = ai.parse_expense(args)
            if amount is None:
                send_message(chat_id, "No pude entender el monto. Usa: /gasto 500 almuerzo")
                return
        send_message(chat_id, notion.add_expense(amount, desc, category))

    elif command == "/gastos":
        send_action(chat_id)
        send_message(chat_id, notion.list_expenses())

    elif command == "/habito":
        if not args:
            send_message(chat_id, "Usa: /habito [nombre]\nEj: /habito ejercicio")
            return
        send_action(chat_id)
        send_message(chat_id, notion.track_habit(args))

    elif command == "/habitos":
        send_action(chat_id)
        send_message(chat_id, notion.list_habits())

    # ── Estudio ──────────────────────────────────────

    elif command == "/flashcards":
        if not args:
            send_message(chat_id, "Usa: /flashcards [tema]\nEj: /flashcards fotosintesis")
            return
        send_action(chat_id)
        send_message(chat_id, ai.generate_flashcards(args))

    elif command == "/quiz":
        if not args:
            send_message(chat_id, "Usa: /quiz [tema]\nEj: /quiz historia argentina")
            return
        send_action(chat_id)
        send_message(chat_id, ai.generate_quiz(args))

    elif command == "/resumir":
        if not args:
            send_message(chat_id, "Usa: /resumir [texto largo]")
            return
        send_action(chat_id)
        send_message(chat_id, ai.summarize(args))

    elif command == "/explicar":
        if not args:
            send_message(chat_id, "Usa: /explicar [concepto]\nEj: /explicar derivadas")
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


def handle_text(chat_id, text):
    send_action(chat_id)
    intent = ai.classify_intent(text)

    if intent["type"] == "nota":
        send_message(chat_id, notion.add_note(intent.get("content", text)))
    elif intent["type"] == "tarea":
        send_message(chat_id, notion.add_task(intent.get("content", text)))
    elif intent["type"] == "gasto":
        amt = intent.get("amount", 0)
        desc = intent.get("description", text)
        send_message(chat_id, notion.add_expense(amt, desc))
    elif intent["type"] == "habito":
        send_message(chat_id, notion.track_habit(intent.get("content", text)))
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
        send_message(chat_id, "No pude entender el audio. Intenta de nuevo.")
        return

    send_message(chat_id, f"_Transcripcion:_ {transcription}")
    handle_text(chat_id, transcription)


# ── Mensaje de bienvenida ────────────────────────────────

WELCOME_MSG = """*Hola! Soy tu asistente personal*

Esto es lo que puedo hacer:

*Facultad (Politecnico di Milano)*
/materias - Ver tus materias
/clase [materia] | [tema] - Agregar clase
/clases - Ver clases pendientes
/estado [tema] | [estado] - Cambiar estado de clase
/examenes - Ver proximos examenes

*Notas y Tareas personales*
/nota [texto] - Guardar una nota
/tarea [texto] - Agregar tarea
/tareas - Ver tareas pendientes

*Estudio*
/flashcards [tema] - Generar flashcards
/quiz [tema] - Hacerte un quiz
/resumir [texto] - Resumir un texto
/explicar [concepto] - Explicar algo

*Gastos*
/gasto [monto] [descripcion]
/gastos - Ver gastos del dia

*Habitos*
/habito [nombre] - Registrar habito
/habitos - Ver habitos de hoy

*Otros*
/briefing - Resumen del dia
/setup - Configurar Notion

Tambien podes hablarme normal o mandarme audios!"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
