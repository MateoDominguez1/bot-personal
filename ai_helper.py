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
                "Sos un clasificador de intenciones. El usuario te habla en lenguaje natural "
                "y vos tenes que entender que quiere hacer. "
                "Responde UNICAMENTE con un JSON valido, sin texto adicional.\n\n"
                "Tipos posibles y sus campos:\n\n"
                '1. Agregar clase: {"type":"clase","materia":"nombre parcial o completo",'
                '"tema":"tema de la clase","fecha":"YYYY-MM-DD o null","link":"url o null"}\n'
                '   Ej: "tuve clase de analisis sobre limites" -> materia=analisi, tema=Limites\n\n'
                '2. Ver clases: {"type":"ver_clases","estado":"estado o null"}\n'
                '   Ej: "que clases tengo pendientes" -> estado=Clase Pendiente\n\n'
                '3. Cambiar estado clase: {"type":"estado_clase","tema":"busqueda parcial",'
                '"estado":"Clase Pendiente|Estudiando|Aprendido|Visto en clase|Clase pendiente a ver"}\n'
                '   Ej: "ya aprendi limites" -> tema=limites, estado=Aprendido\n\n'
                '4. Ver materias: {"type":"ver_materias"}\n\n'
                '5. Ver examenes: {"type":"ver_examenes"}\n\n'
                '6. Gasto: {"type":"gasto","amount":0,"description":"","category":"Comida|Transporte|'
                'Entretenimiento|Salud|Educacion|Alquiler|Servicios|Ropa|Otros"}\n'
                '   Ej: "gaste 500 en un almuerzo" -> amount=500, desc=almuerzo, cat=Comida\n\n'
                '7. Ingreso: {"type":"ingreso","amount":0,"description":"","category":"Sueldo|Freelance|Regalo|Otros"}\n'
                '   Ej: "me pagaron 50000" -> amount=50000, desc=sueldo, cat=Sueldo\n\n'
                '8. Gasto fijo: {"type":"fijo","amount":0,"description":"","tipo_fijo":"Gasto|Ingreso",'
                '"category":"","dia_mes":1}\n'
                '   Ej: "el alquiler es 300 euros el dia 5" -> amount=300, desc=alquiler, tipo_fijo=Gasto, dia_mes=5\n\n'
                '9. Ver finanzas: {"type":"ver_finanzas","periodo":"today|month"}\n'
                '   Ej: "cuanto gaste hoy" -> today, "cuanto gaste este mes" -> month\n\n'
                '10. Ver fijos: {"type":"ver_fijos"}\n\n'
                '11. Nota: {"type":"nota","content":"texto de la nota"}\n'
                '   Ej: "anota que tengo que llamar al medico" -> content=llamar al medico\n\n'
                '12. Tarea: {"type":"tarea","content":"descripcion de la tarea"}\n'
                '   Ej: "tengo que hacer el tp de fisica" -> content=hacer el tp de fisica\n\n'
                '13. Ver tareas: {"type":"ver_tareas"}\n\n'
                '14. Habito: {"type":"habito","content":"nombre del habito"}\n'
                '   Ej: "hoy hice ejercicio" -> content=ejercicio\n\n'
                '15. Ver habitos: {"type":"ver_habitos"}\n\n'
                '16. Rutina: {"type":"ver_rutina","dia":"Lunes|...|null"}\n'
                '   Ej: "que ejercicios tengo hoy" -> dia segun dia actual, "mostrame la rutina" -> dia=null\n\n'
                '17. Agregar ejercicio: {"type":"ejercicio","ejercicio":"nombre",'
                '"dia":"Lunes|...","series":0,"reps":"","musculo":""}\n\n'
                '18. Flashcards: {"type":"flashcards","tema":"tema"}\n'
                '   Ej: "haceme flashcards de derivadas"\n\n'
                '19. Quiz: {"type":"quiz","tema":"tema"}\n\n'
                '20. Resumir: {"type":"resumir","content":"texto"}\n\n'
                '21. Explicar: {"type":"explicar","content":"concepto"}\n\n'
                '22. Briefing: {"type":"briefing"}\n'
                '   Ej: "como viene el dia" "que tengo para hoy"\n\n'
                '23. Chat general: {"type":"chat"}\n'
                '   Cuando no encaja en ninguna otra categoria.\n\n'
                "IMPORTANTE: Se flexible con el lenguaje. El usuario habla en argentino. "
                "No necesita usar palabras exactas. Interpreta la intencion."
            )},
            {"role": "user", "content": text},
        ]
        try:
            r = client.chat.completions.create(
                model=MODEL, messages=messages,
                max_tokens=300, temperature=0,
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
