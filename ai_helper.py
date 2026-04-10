import os
import json
import base64
from datetime import date
from groq import Groq

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

GROQ_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "llama-3.2-90b-vision-preview"

SYSTEM_PROMPT = (
    "Sos un asistente personal inteligente que habla en espanol argentino. "
    "Sos conciso, util y amigable. Usas 'vos' en vez de 'tu'. "
    "Ayudas con estudio, organizacion, tareas y lo que el usuario necesite."
)

TODAY = date.today().isoformat()


class AIHelper:

    # ── Chat general ─────────────────────────────────────

    def chat(self, message: str, history: list | None = None) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-18:])
        messages.append({"role": "user", "content": message})
        return self._groq_ask_chat(messages)

    # ── Clasificacion de intento ─────────────────────────

    def classify_intent(self, text: str) -> dict:
        messages = [
            {"role": "system", "content": (
                f"Hoy es {TODAY}. "
                "Sos un clasificador de intenciones. El usuario te habla en lenguaje natural "
                "y vos tenes que entender que quiere hacer. "
                "Responde UNICAMENTE con un JSON valido, sin texto adicional.\n\n"
                "Tipos posibles y sus campos:\n\n"
                '1. Agregar clase: {"type":"clase","materia":"nombre parcial o completo",'
                '"tema":"tema de la clase","fecha":"YYYY-MM-DD o null","link":"url o null"}\n'
                '   Ej: "tuve clase de analisis sobre limites" -> materia=analisi, tema=Limites\n\n'
                '2. Ver clases: {"type":"ver_clases","estado":"estado o null"}\n'
                '   Ej: "que clases tengo pendientes" -> estado=Clase Pendiente\n'
                '   "que clases me quedan por ver" -> estado=Clase pendiente a ver\n\n'
                '3. Cambiar estado clase: {"type":"estado_clase","tema":"busqueda parcial",'
                '"estado":"Clase Pendiente|Estudiando|Aprendido|Visto en clase|Clase pendiente a ver"}\n\n'
                '4. Ver materias: {"type":"ver_materias"}\n\n'
                '5. Ver examenes (en Notion): {"type":"ver_examenes"}\n\n'
                '6. Gasto: {"type":"gasto","amount":0,"description":"","category":"Comida|Transporte|'
                'Entretenimiento|Salud|Educacion|Alquiler|Servicios|Ropa|Otros"}\n\n'
                '7. Ingreso: {"type":"ingreso","amount":0,"description":"","category":"Sueldo|Freelance|Regalo|Otros"}\n\n'
                '8. Gasto fijo: {"type":"fijo","amount":0,"description":"","tipo_fijo":"Gasto|Ingreso",'
                '"category":"","dia_mes":1}\n\n'
                '9. Ver finanzas: {"type":"ver_finanzas","periodo":"today|month"}\n\n'
                '10. Ver fijos: {"type":"ver_fijos"}\n\n'
                '11. Eliminar gasto: {"type":"eliminar_gasto","descripcion":"texto a buscar"}\n'
                '    Ej: "borra el gasto del almuerzo" "elimina el gasto de netflix"\n\n'
                '12. Eliminar ingreso: {"type":"eliminar_ingreso","descripcion":"texto a buscar"}\n'
                '    Ej: "elimina el ingreso de ayer" "borra el sueldo"\n\n'
                '13. Nota: {"type":"nota","content":"texto de la nota"}\n\n'
                '14. Tarea: {"type":"tarea","content":"descripcion de la tarea"}\n\n'
                '15. Ver tareas: {"type":"ver_tareas"}\n\n'
                '16. Habito: {"type":"habito","content":"nombre del habito"}\n\n'
                '17. Ver habitos: {"type":"ver_habitos"}\n\n'
                '18. Rutina: {"type":"ver_rutina","dia":"Lunes|...|null"}\n\n'
                '19. Agregar ejercicio: {"type":"ejercicio","ejercicio":"nombre",'
                '"dia":"Lunes|...","series":0,"reps":"","musculo":""}\n\n'
                '20. Flashcards: {"type":"flashcards","tema":"tema"}\n\n'
                '21. Quiz: {"type":"quiz","tema":"tema"}\n\n'
                '22. Resumir: {"type":"resumir","content":"texto"}\n\n'
                '23. Explicar: {"type":"explicar","content":"concepto"}\n\n'
                '24. Balance: {"type":"balance"}\n'
                '    Ej: "cuanta plata tengo" "cual es mi balance" "como estoy de plata"\n\n'
                '25. Busqueda/noticias/datos: {"type":"busqueda","query":"lo que quiere buscar"}\n'
                '    USA ESTE TIPO para: noticias, resultados deportivos, clima, precio del dolar, '
                '    cualquier hecho del mundo real que pueda haber cambiado recientemente.\n'
                '    Ej: "quien gano el partido de ayer" "como esta el dolar" "que noticias hay"\n'
                '    "resultado real madrid" "precio del bitcoin" "que paso con X"\n\n'
                '26. Horario/calendario (del iCal de la universidad): {"type":"horario",'
                '"periodo":"hoy|manana|semana|semana_siguiente|examenes|proxima_clase",'
                '"materia":"nombre o null","pregunta":"pregunta original o null"}\n'
                '    Ej: "que clases tengo hoy" -> periodo=hoy\n'
                '    "horario de la semana que viene" -> periodo=semana_siguiente\n'
                '    "cuando es el proximo parcial" -> periodo=examenes\n\n'
                '27. Agregar evento a Apple Calendar: {"type":"apple_evento","titulo":"...",'
                '"fecha":"YYYY-MM-DD","hora":"HH:MM o null","duracion_min":60,'
                '"calendario":"nombre del calendario o null","descripcion":""}\n'
                '    IMPORTANTE: "fecha" SIEMPRE debe ser YYYY-MM-DD. '
                f'    Hoy es {TODAY}. Convierte dias relativos: '
                '    "martes" -> proximo martes en YYYY-MM-DD, "manana" -> manana en YYYY-MM-DD, etc.\n'
                '    Ej: "reunion el martes a las 10" -> fecha=YYYY-MM-DD del proximo martes\n\n'
                '28. Agregar recordatorio a Apple Reminders: {"type":"apple_recordatorio",'
                '"titulo":"...","lista":"nombre de lista o null","fecha":"YYYY-MM-DD o null"}\n'
                '    Ej: "agrega a recordatorios llamar al medico" '
                '    "agrega en da fare comprar leche" "recordatorio en universidad examen fisica"\n\n'
                '29. Preguntar sobre PDF cargado: {"type":"pdf_pregunta","content":"la pregunta"}\n'
                '    Ej: "resumi el pdf" "haceme flashcards del pdf" "que dice sobre X en el pdf"\n\n'
                '30. Briefing: {"type":"briefing"}\n'
                '    Ej: "como viene el dia" "que tengo para hoy"\n\n'
                '31. Chat general: {"type":"chat"}\n'
                '    Cuando no encaja en ninguna otra categoria.\n\n'
                "IMPORTANTE: Se flexible con el lenguaje. El usuario habla en argentino. "
                "No necesita usar palabras exactas. Interpreta la intencion."
            )},
            {"role": "user", "content": text},
        ]
        try:
            r = groq_client.chat.completions.create(
                model=GROQ_MODEL, messages=messages,
                max_tokens=400, temperature=0,
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
        b64 = base64.b64encode(image_data).decode("utf-8")
        prompt = (
            "Analiza esta imagen de un recibo, ticket o comprobante de pago. "
            "Extrae TODA la informacion visible y responde SOLO con JSON valido:\n"
            '{"tipo": "Gasto|Ingreso", "amount": 0, '
            '"description": "descripcion detallada de que se compro", '
            '"category": "categoria", '
            '"store": "nombre del local o null", '
            '"date": "YYYY-MM-DD o null", '
            '"items": [{"name": "producto", "qty": 1, "price": 0}]}\n\n'
            "Categorias: Comida, Transporte, Entretenimiento, Salud, Educacion, "
            "Alquiler, Servicios, Ropa, Sueldo, Freelance, Regalo, Otros\n\n"
            "En 'description' incluye el nombre del local y los principales productos comprados. "
            "En 'items' lista cada producto/servicio visible con su precio. "
            "Si no podes leer el monto total, suma los items. "
            "Si no podes determinar si es gasto o ingreso, asumi Gasto."
        )
        if caption:
            prompt += f"\n\nEl usuario agrego este texto: {caption}"

        try:
            r = groq_client.chat.completions.create(
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
                max_tokens=600,
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
            r = groq_client.chat.completions.create(
                model=GROQ_MODEL, messages=messages,
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

    # ── Busqueda web ───────────────────────────────────────

    def web_search(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS
            # Include today's date for time-sensitive queries
            search_query = query
            with DDGS() as ddgs:
                results = list(ddgs.text(search_query, max_results=6))

            # Retry with simplified query if no results
            if not results:
                simplified = " ".join(query.split()[:4])
                with DDGS() as ddgs:
                    results = list(ddgs.text(simplified, max_results=6))

            if not results:
                return self._groq_ask(
                    f"Responde esta pregunta con tu conocimiento. "
                    f"Hoy es {TODAY}. Espanol argentino. Da la respuesta directamente.",
                    query,
                )

            context = "\n\n".join(
                f"**{r['title']}**\n{r['body']}" for r in results
            )
            system = (
                f"Hoy es {TODAY}. "
                "Usa los resultados de busqueda para responder la pregunta del usuario. "
                "Da la respuesta directamente y de forma concisa en espanol argentino. "
                "NUNCA le digas al usuario que busque el mismo. "
                "NUNCA digas 'no tengo acceso a internet' o similar. "
                "Si los resultados tienen la informacion, usala. "
                "Si los resultados no son relevantes, responde con tu conocimiento."
            )
            return self._groq_ask(system, f"Pregunta: {query}\n\nResultados:\n{context}", max_tokens=1500)
        except ImportError:
            return self._groq_ask(
                f"Responde esta pregunta con tu conocimiento. Hoy es {TODAY}. Espanol argentino.",
                query,
            )
        except Exception:
            return self._groq_ask(
                f"Responde esta pregunta con tu conocimiento. Hoy es {TODAY}. Espanol argentino.",
                query,
            )

    # ── Calendario ────────────────────────────────────────

    def answer_calendar_question(self, question: str, calendar_context: str) -> str:
        return self._groq_ask(
            f"Hoy es {TODAY}. Sos un asistente que responde preguntas sobre el horario universitario. "
            "Tenes el calendario completo del estudiante. Responde de forma clara y "
            "concisa en espanol argentino. Si preguntan por un aula o ubicacion, incluila.\n\n"
            f"CALENDARIO (formato: fecha hora | tipo | materia | aula):\n{calendar_context}",
            question,
            max_tokens=800,
        )

    # ── Estudio (usa Claude si disponible) ───────────────

    def generate_flashcards(self, topic: str) -> str:
        return self._groq_ask(
            "Genera 5 flashcards sobre el tema. Formato:\n\n"
            "*Flashcard 1*\n*Pregunta:* ...\n*Respuesta:* ...\n\n"
            "Usa espanol argentino. Se preciso y util para estudiar.",
            f"Tema: {topic}", max_tokens=1800,
        )

    def generate_quiz(self, topic: str) -> str:
        return self._groq_ask(
            "Genera un quiz de 5 preguntas de opcion multiple.\nFormato:\n"
            "*Pregunta 1:* ...\nA) ...\nB) ...\nC) ...\nD) ...\n"
            "*Respuesta correcta:* ...\n*Explicacion:* ...\n\nUsa espanol argentino.",
            f"Tema: {topic}", max_tokens=2500,
        )

    def summarize(self, text: str) -> str:
        return self._groq_ask(
            "Resumi el siguiente texto de forma clara y concisa en espanol "
            "argentino. Usa bullet points. Captura los puntos clave.",
            text, max_tokens=1200, temperature=0.3,
        )

    def explain(self, concept: str) -> str:
        return self._groq_ask(
            "Explica el concepto de forma clara y simple, como si le explicaras "
            "a un estudiante universitario. Usa ejemplos practicos y analogias. "
            "Espanol argentino.",
            f"Explicame: {concept}", max_tokens=2000,
        )

    def answer_pdf_question(self, question: str, pdf_text: str) -> str:
        context = pdf_text[:12000]
        return self._groq_ask(
            "El usuario te envio el contenido de un PDF. Responde su pregunta "
            "basandote en el contenido del documento. Se preciso y cita partes "
            "relevantes cuando sea util. Espanol argentino.",
            f"CONTENIDO DEL PDF:\n{context}\n\nPREGUNTA: {question}",
            max_tokens=2500,
        )

    def generate_pdf_apunte(self, topic: str, pdf_text: str | None = None) -> str:
        if pdf_text:
            context = f"\n\nBASATE EN ESTE DOCUMENTO:\n{pdf_text[:10000]}"
        else:
            context = ""
        return self._groq_ask(
            "Genera un apunte de estudio completo y bien estructurado sobre el tema. "
            "Incluye: definiciones clave, conceptos importantes, formulas si aplica, "
            "ejemplos, y un resumen final. Usa formato con titulos y bullet points. "
            "Espanol argentino.",
            f"Tema: {topic}{context}",
            max_tokens=3000,
        )

    # ── Briefing ─────────────────────────────────────────

    def generate_briefing(self, tasks: list, habits: list, expenses: list,
                          clases: list | None = None,
                          schedule_today: list | None = None,
                          upcoming_exams: list | None = None) -> str:
        schedule_str = ""
        if schedule_today:
            schedule_lines = []
            for s in schedule_today:
                line = f"  {s['hora_inicio']}-{s['hora_fin']}  {s['materia']}"
                if s.get("aula"):
                    line += f"  ({s['aula']})"
                schedule_lines.append(line)
            schedule_str = "\n".join(schedule_lines)

        exams_str = ""
        if upcoming_exams:
            exams_str = "\n".join(
                f"  {e['materia']} - {e['fecha']} {e['hora']} (en {e['dias_restantes']} dias)"
                for e in upcoming_exams
            )

        ctx = json.dumps(
            {
                "clases_hoy_universidad": schedule_str or "Sin clases hoy",
                "examenes_proximos_20_dias": exams_str or "Ninguno",
                "tareas_pendientes": tasks,
                "clases_pendientes_notion": clases or [],
                "habitos_hoy": habits,
                "movimientos_hoy": expenses,
            },
            ensure_ascii=False,
        )
        return self._groq_ask(
            "Genera un briefing matutino amigable y motivador en espanol argentino. "
            "PRIMERO las clases de hoy (materia, hora, aula). "
            "Si hay examenes proximos en menos de 20 dias, mencionalos con urgencia. "
            "Luego tareas pendientes, habitos y movimientos de hoy. Se conciso.",
            ctx, max_tokens=900,
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
            r = groq_client.chat.completions.create(
                model=GROQ_MODEL, messages=messages,
                max_tokens=100, temperature=0,
            )
            result = json.loads(r.choices[0].message.content.strip())
            return result.get("amount"), result.get("description", ""), result.get("category", "Otros")
        except Exception:
            return None, None, None

    # ── Transcripcion de audio ───────────────────────────

    def transcribe(self, audio_data: bytes) -> str | None:
        try:
            transcription = groq_client.audio.transcriptions.create(
                file=("audio.ogg", audio_data),
                model="whisper-large-v3",
                language="es",
            )
            return transcription.text
        except Exception as e:
            print(f"Transcription error: {e}")
            return None

    # ── Utilidades internas ──────────────────────────────

    def _groq_ask(self, system: str, user: str, **kwargs) -> str:
        try:
            r = groq_client.chat.completions.create(
                model=GROQ_MODEL,
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

    def _groq_ask_chat(self, messages: list) -> str:
        try:
            r = groq_client.chat.completions.create(
                model=GROQ_MODEL, messages=messages,
                max_tokens=1024, temperature=0.7,
            )
            return r.choices[0].message.content
        except Exception as e:
            return f"Error: {e}"
