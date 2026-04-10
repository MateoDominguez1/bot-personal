import os
import json
import base64
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "llama-3.2-90b-vision-preview"

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
                '{"type": "nota|tarea|gasto|ingreso|habito|chat", '
                '"content": "texto relevante", "amount": 0, '
                '"description": "", "category": "Otros"}\n\n'
                "- nota: quiere guardar/anotar algo\n"
                "- tarea: menciona algo que tiene que hacer\n"
                "- gasto: menciona un gasto o compra con monto\n"
                "- ingreso: menciona dinero que recibio/cobro\n"
                "- habito: dice que hizo/completo un habito\n"
                "- chat: conversacion general\n\n"
                "Para gastos/ingresos extrae amount, description y category.\n"
                "Categorias: Comida, Transporte, Entretenimiento, Salud, Educacion, "
                "Alquiler, Servicios, Ropa, Sueldo, Freelance, Regalo, Otros"
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

    # ── Analisis de fotos (recibos/tickets) ──────────────

    def analyze_receipt(self, image_data: bytes, caption: str = "") -> dict | None:
        """Analiza foto de recibo/ticket y extrae tipo, monto, descripcion, categoria."""
        b64 = base64.b64encode(image_data).decode("utf-8")
        prompt = (
            "Analiza esta imagen de un recibo, ticket o comprobante. "
            "Extrae la informacion y responde SOLO con JSON valido:\n"
            '{"tipo": "Gasto|Ingreso", "amount": 0, '
            '"description": "que es", "category": "categoria"}\n\n'
            "Categorias: Comida, Transporte, Entretenimiento, Salud, Educacion, "
            "Alquiler, Servicios, Ropa, Sueldo, Freelance, Regalo, Otros\n\n"
            "Si no podes leer el monto, pon amount: 0.\n"
            "Si no podes determinar si es gasto o ingreso, asumi Gasto."
        )
        if caption:
            prompt += f"\n\nEl usuario agrego este texto: {caption}"

        try:
            r = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}",
                        }},
                    ],
                }],
                max_tokens=300,
                temperature=0,
            )
            raw = r.choices[0].message.content.strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(raw[start:end])
        except Exception as e:
            print(f"Receipt analysis error: {e}")
        return None

    # ── Parseo de rutina desde archivo ───────────────────

    def parse_routine(self, text: str) -> list[dict] | None:
        """Parsea un archivo de texto con rutina de gym y devuelve lista de ejercicios."""
        messages = [
            {"role": "system", "content": (
                "Extrae los ejercicios de esta rutina de gimnasio. "
                "Responde SOLO con un JSON array. Cada elemento debe tener:\n"
                '{"ejercicio": "nombre", "dia": "Lunes|Martes|...|Domingo", '
                '"series": 4, "reps": "10-12", "musculo": "Pecho|Espalda|Hombros|'
                'Biceps|Triceps|Piernas|Abdominales|Gluteos|Cardio|Full body", '
                '"notas": ""}\n\n'
                "Si no hay dia especificado, deducilo del contexto (ej: 'Push day' = Lunes). "
                "Si dice algo como 3x10, series=3 y reps='10'. "
                "Responde SOLO el JSON array, nada mas."
            )},
            {"role": "user", "content": text[:5000]},
        ]
        try:
            r = client.chat.completions.create(
                model=MODEL, messages=messages,
                max_tokens=3000, temperature=0,
            )
            raw = r.choices[0].message.content.strip()
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start != -1 and end > start:
                return json.loads(raw[start:end])
        except Exception as e:
            print(f"Routine parse error: {e}")
        return None

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

    def generate_briefing(self, tasks: list, habits: list, expenses: list,
                          clases: list | None = None) -> str:
        ctx = json.dumps(
            {
                "tareas_pendientes": tasks,
                "clases_pendientes": clases or [],
                "habitos_hoy": habits,
                "movimientos_hoy": expenses,
            },
            ensure_ascii=False,
        )
        return self._ask(
            "Genera un briefing matutino amigable y motivador en espanol argentino. "
            "Resumi clases pendientes de la facultad, tareas, habitos y "
            "movimientos financieros del dia (gastos e ingresos). Se conciso.",
            ctx, max_tokens=800,
        )

    # ── Gastos ───────────────────────────────────────────

    def parse_expense(self, text: str):
        messages = [
            {"role": "system", "content": (
                'Extrae monto y descripcion. Responde SOLO con JSON:\n'
                '{"amount": 0, "description": "", "category": ""}\n'
                "Categorias: Comida, Transporte, Entretenimiento, Salud, "
                "Educacion, Alquiler, Servicios, Ropa, Sueldo, Freelance, Regalo, Otros"
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
