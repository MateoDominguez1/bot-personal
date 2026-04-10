import os
import json
import tempfile
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "Sos un asistente personal inteligente que habla en espanol argentino. "
    "Sos conciso, util y amigable. Usas 'vos' en vez de 'tu'. "
    "Ayudas con estudio, organizacion, tareas y lo que el usuario necesite."
)


class AIHelper:
    # ── Conversacion general ─────────────────────────────

    def chat(self, message: str, history: list | None = None) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-18:])
        messages.append({"role": "user", "content": message})

        try:
            r = client.chat.completions.create(
                model=MODEL, messages=messages,
                max_tokens=1024, temperature=0.7,
            )
            return r.choices[0].message.content
        except Exception as e:
            return f"Error al procesar: {e}"

    # ── Clasificacion de intento ─────────────────────────

    def classify_intent(self, text: str) -> dict:
        messages = [
            {"role": "system", "content": (
                "Clasifica el mensaje del usuario en una categoria. "
                "Responde SOLO con JSON valido:\n"
                '{"type": "nota|tarea|gasto|habito|chat", '
                '"content": "texto relevante", "amount": 0, "description": ""}\n\n'
                "- nota: quiere guardar/anotar algo\n"
                "- tarea: menciona algo que tiene que hacer\n"
                "- gasto: menciona un gasto o compra con monto\n"
                "- habito: dice que hizo/completo un habito\n"
                "- chat: conversacion general\n\n"
                "Para gastos extrae monto en 'amount' y descripcion en 'description'."
            )},
            {"role": "user", "content": text},
        ]
        try:
            r = client.chat.completions.create(
                model=MODEL, messages=messages,
                max_tokens=200, temperature=0,
            )
            raw = r.choices[0].message.content.strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(raw[start:end])
        except Exception:
            pass
        return {"type": "chat"}

    # ── Estudio ──────────────────────────────────────────

    def generate_flashcards(self, topic: str) -> str:
        return self._ask(
            "Genera 5 flashcards sobre el tema. Formato:\n\n"
            "*Flashcard 1*\n*Pregunta:* ...\n*Respuesta:* ...\n\n"
            "Usa espanol argentino.",
            f"Tema: {topic}", max_tokens=1500,
        )

    def generate_quiz(self, topic: str) -> str:
        return self._ask(
            "Genera un quiz de 5 preguntas de opcion multiple.\nFormato:\n"
            "*Pregunta 1:* ...\nA) ...\nB) ...\nC) ...\nD) ...\n"
            "*Respuesta:* ...\n\nUsa espanol argentino.",
            f"Tema: {topic}", max_tokens=2000,
        )

    def summarize(self, text: str) -> str:
        return self._ask(
            "Resumi el siguiente texto de forma clara y concisa en espanol "
            "argentino. Usa bullet points.",
            text, max_tokens=1000, temperature=0.3,
        )

    def explain(self, concept: str) -> str:
        return self._ask(
            "Explica el concepto de forma clara y simple, como si le explicaras "
            "a un estudiante. Usa ejemplos practicos. Espanol argentino.",
            f"Explicame: {concept}", max_tokens=1500,
        )

    # ── Briefing ─────────────────────────────────────────

    def generate_briefing(self, tasks: list, habits: list, expenses: list) -> str:
        ctx = json.dumps(
            {"tareas_pendientes": tasks, "habitos_hoy": habits, "gastos_hoy": expenses},
            ensure_ascii=False,
        )
        return self._ask(
            "Genera un briefing matutino amigable y motivador en espanol argentino. "
            "Resumi tareas pendientes, habitos y gastos del dia. Se conciso.",
            ctx, max_tokens=800,
        )

    # ── Gastos ───────────────────────────────────────────

    def parse_expense(self, text: str):
        messages = [
            {"role": "system", "content": (
                'Extrae monto y descripcion del gasto. Responde SOLO con JSON:\n'
                '{"amount": 0, "description": "", "category": ""}\n'
                "Categorias: Comida, Transporte, Entretenimiento, Salud, Educacion, Otros"
            )},
            {"role": "user", "content": text},
        ]
        try:
            r = client.chat.completions.create(
                model=MODEL, messages=messages,
                max_tokens=100, temperature=0,
            )
            result = json.loads(r.choices[0].message.content.strip())
            return result.get("amount"), result.get("description", ""), result.get("category", "Otros")
        except Exception:
            return None, None, None

    # ── Transcripcion de audio ───────────────────────────

    def transcribe(self, audio_data: bytes) -> str | None:
        try:
            transcription = client.audio.transcriptions.create(
                file=("audio.ogg", audio_data),
                model="whisper-large-v3",
                language="es",
            )
            return transcription.text
        except Exception as e:
            print(f"Transcription error: {e}")
            return None

    # ── Utilidad interna ─────────────────────────────────

    def _ask(self, system: str, user: str, **kwargs) -> str:
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=kwargs.get("max_tokens", 1024),
                temperature=kwargs.get("temperature", 0.7),
            )
            return r.choices[0].message.content
        except Exception as e:
            return f"Error: {e}"
