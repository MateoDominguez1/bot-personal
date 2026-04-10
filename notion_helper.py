import os
from datetime import date
from notion_client import Client

notion = Client(auth=os.environ.get("NOTION_TOKEN"))

# ── IDs de bases de datos existentes (Politecnico di Milano) ─────
FACULTY_DBS = {
    "materie": "295c41af-d85a-80a5-8f87-c1fe893d93ba",
    "lezioni": "296c41af-d85a-8010-8721-c450a1993d5e",
    "esami": "295c41af-d85a-80c1-89ad-c9860e116b0f",
}

# Nombres para auto-descubrimiento de DBs personales
PERSONAL_DB_NAMES = {
    "notas": "Notas",
    "tareas": "Tareas",
    "gastos": "Gastos",
    "habitos": "Habitos",
}


class NotionHelper:
    def __init__(self):
        self.faculty = FACULTY_DBS.copy()
        self.personal: dict[str, str | None] = {
            "notas": os.environ.get("NOTION_DB_NOTAS"),
            "tareas": os.environ.get("NOTION_DB_TAREAS"),
            "gastos": os.environ.get("NOTION_DB_GASTOS"),
            "habitos": os.environ.get("NOTION_DB_HABITOS"),
        }
        self._discover_personal_dbs()
        # Cache de materias: nombre -> page_id
        self._materie_cache: dict[str, str] = {}

    def _discover_personal_dbs(self):
        try:
            results = notion.search(
                filter={"property": "object", "value": "database"}
            ).get("results", [])
            for db in results:
                title_parts = db.get("title", [])
                if not title_parts:
                    continue
                title = title_parts[0].get("plain_text", "").strip()
                clean = title.replace("\U0001f4dd ", "").replace("\u2705 ", "") \
                             .replace("\U0001f4b0 ", "").replace("\U0001f3c3 ", "").strip()
                for key, name in PERSONAL_DB_NAMES.items():
                    if clean == name and not self.personal.get(key):
                        self.personal[key] = db["id"]
        except Exception:
            pass

    # ══════════════════════════════════════════════════════
    #  FACULTAD - Materias, Lecciones, Examenes
    # ══════════════════════════════════════════════════════

    def _get_materia_id(self, nombre: str) -> str | None:
        """Busca una materia por nombre y devuelve su page ID."""
        nombre_lower = nombre.lower().strip()

        # Buscar en cache
        if nombre_lower in self._materie_cache:
            return self._materie_cache[nombre_lower]

        try:
            results = notion.databases.query(database_id=self.faculty["materie"])
            for page in results.get("results", []):
                title_parts = page["properties"]["Nombre"]["title"]
                if not title_parts:
                    continue
                materia_name = title_parts[0]["plain_text"]
                # Guardar en cache
                self._materie_cache[materia_name.lower().strip()] = page["id"]

            # Buscar coincidencia parcial
            for cached_name, cached_id in self._materie_cache.items():
                if nombre_lower in cached_name or cached_name in nombre_lower:
                    return cached_id
            return self._materie_cache.get(nombre_lower)
        except Exception:
            return None

    def list_materias(self) -> str:
        try:
            results = notion.databases.query(database_id=self.faculty["materie"])
            materias = results.get("results", [])
            if not materias:
                return "No hay materias cargadas."

            msg = "*Materias:*\n\n"
            for m in materias:
                props = m["properties"]
                nombre = props["Nombre"]["title"][0]["plain_text"] if props["Nombre"]["title"] else "?"
                profesor = props.get("Profesor", {}).get("rich_text", [])
                prof_name = profesor[0]["plain_text"] if profesor else "?"
                year = props.get("Año universitario", {}).get("status", {})
                year_name = year.get("name", "?") if year else "?"
                msg += f"- *{nombre}* - {prof_name} ({year_name})\n"
            return msg
        except Exception as e:
            return f"Error: {e}"

    def add_clase(self, materia: str, tema: str, fecha: str | None = None,
                  link: str | None = None) -> str:
        """Agrega una leccion a la DB de Lezioni del semestre."""
        try:
            materia_id = self._get_materia_id(materia)
            if not materia_id:
                materias_list = ", ".join(self._materie_cache.keys()) or "ninguna encontrada"
                return (
                    f"No encontre la materia '{materia}'.\n"
                    f"Materias disponibles: {materias_list}"
                )

            properties = {
                "Tema": {"title": [{"text": {"content": tema}}]},
                "Materia": {"relation": [{"id": materia_id}]},
                "Estado": {"select": {"name": "Clase Pendiente"}},
                "Fecha clase": {"date": {"start": fecha or date.today().isoformat()}},
            }
            if link:
                properties["Link"] = {"url": link}

            notion.pages.create(
                parent={"database_id": self.faculty["lezioni"]},
                properties=properties,
            )
            return f"Clase agregada: *{tema}* ({materia})"
        except Exception as e:
            return f"Error al agregar clase: {e}"

    def list_clases(self, estado: str | None = None) -> str:
        """Lista las clases, opcionalmente filtradas por estado."""
        try:
            query_filter = None
            if estado:
                query_filter = {"property": "Estado", "select": {"equals": estado}}
            else:
                # Mostrar solo no terminadas
                query_filter = {"property": "Terminado", "checkbox": {"equals": False}}

            results = notion.databases.query(
                database_id=self.faculty["lezioni"],
                filter=query_filter,
                sorts=[{"property": "Fecha clase", "direction": "ascending"}],
            )
            clases = results.get("results", [])
            if not clases:
                return "No hay clases pendientes."

            estado_emoji = {
                "Clase Pendiente": "🔴",
                "Estudiando": "🔵",
                "Aprendido": "🟢",
                "Visto en clase": "🟡",
                "Clase pendiente a ver": "🟤",
            }

            msg = "*Clases:*\n\n"
            for c in clases[:20]:  # Limitar a 20
                props = c["properties"]
                tema = props["Tema"]["title"][0]["plain_text"] if props["Tema"]["title"] else "?"
                est = props["Estado"]["select"]["name"] if props["Estado"].get("select") else "?"
                emoji = estado_emoji.get(est, "⚪")
                fecha = ""
                if props.get("Fecha clase", {}).get("date"):
                    fecha = f" ({props['Fecha clase']['date']['start']})"
                msg += f"{emoji} {tema}{fecha} [{est}]\n"
            return msg
        except Exception as e:
            return f"Error: {e}"

    def update_clase_estado(self, tema_query: str, nuevo_estado: str) -> str:
        """Actualiza el estado de una clase buscandola por tema."""
        estados_validos = [
            "Clase Pendiente", "Estudiando", "Aprendido",
            "Visto en clase", "Clase pendiente a ver",
        ]
        # Buscar coincidencia parcial en estados
        estado_match = None
        for est in estados_validos:
            if nuevo_estado.lower() in est.lower():
                estado_match = est
                break
        if not estado_match:
            return (
                f"Estado no valido. Opciones:\n"
                + "\n".join(f"- {e}" for e in estados_validos)
            )

        try:
            results = notion.databases.query(database_id=self.faculty["lezioni"])
            for page in results.get("results", []):
                tema = page["properties"]["Tema"]["title"]
                if not tema:
                    continue
                if tema_query.lower() in tema[0]["plain_text"].lower():
                    notion.pages.update(
                        page_id=page["id"],
                        properties={"Estado": {"select": {"name": estado_match}}},
                    )
                    return f"Estado actualizado: *{tema[0]['plain_text']}* -> {estado_match}"
            return f"No encontre ninguna clase con '{tema_query}' en el tema."
        except Exception as e:
            return f"Error: {e}"

    def list_examenes(self) -> str:
        """Lista los proximos examenes."""
        try:
            results = notion.databases.query(
                database_id=self.faculty["esami"],
                sorts=[{"property": "Fecha de examen", "direction": "ascending"}],
            )
            exams = results.get("results", [])
            if not exams:
                return "No hay examenes cargados."

            msg = "*Examenes:*\n\n"
            for ex in exams:
                props = ex["properties"]
                nombre = props["Nombre"]["title"][0]["plain_text"] if props["Nombre"]["title"] else "?"
                fecha = ""
                if props.get("Fecha de examen", {}).get("date"):
                    fecha = props["Fecha de examen"]["date"]["start"]
                msg += f"- *{nombre}* - {fecha or 'Sin fecha'}\n"
            return msg
        except Exception as e:
            return f"Error: {e}"

    # ══════════════════════════════════════════════════════
    #  PERSONAL - Notas, Tareas, Gastos, Habitos
    # ══════════════════════════════════════════════════════

    def setup_databases(self) -> str:
        """Crea las bases de datos personales (no de la facultad)."""
        try:
            # Buscar una pagina que NO sea del Politecnico para crear las DBs
            pages = notion.search(
                filter={"property": "object", "value": "page"}
            ).get("results", [])

            if not pages:
                return (
                    "No encontre paginas compartidas con la integracion.\n\n"
                    "1. Crea una pagina en Notion llamada 'Bot Personal'\n"
                    "2. Click en '...' > 'Connections' > busca tu integracion\n"
                    "3. Volve a mandar /setup"
                )

            # Usar la primera pagina disponible
            parent_id = pages[0]["id"]
            parent_title = self._get_page_title(pages[0])
            created = []

            if not self.personal.get("gastos"):
                db = notion.databases.create(
                    parent={"type": "page_id", "page_id": parent_id},
                    title=[{"type": "text", "text": {"content": "\U0001f4b0 Gastos"}}],
                    properties={
                        "Descripcion": {"title": {}},
                        "Monto": {"number": {"format": "dollar"}},
                        "Categoria": {"select": {"options": [
                            {"name": "Comida", "color": "orange"},
                            {"name": "Transporte", "color": "blue"},
                            {"name": "Entretenimiento", "color": "purple"},
                            {"name": "Salud", "color": "green"},
                            {"name": "Educacion", "color": "yellow"},
                            {"name": "Otros", "color": "gray"},
                        ]}},
                        "Fecha": {"date": {}},
                    },
                )
                self.personal["gastos"] = db["id"]
                created.append("Gastos")

            if not self.personal.get("habitos"):
                db = notion.databases.create(
                    parent={"type": "page_id", "page_id": parent_id},
                    title=[{"type": "text", "text": {"content": "\U0001f3c3 Habitos"}}],
                    properties={
                        "Habito": {"title": {}},
                        "Fecha": {"date": {}},
                        "Completado": {"checkbox": {}},
                    },
                )
                self.personal["habitos"] = db["id"]
                created.append("Habitos")

            if created:
                msg = "*Setup completo!*\n\nBases de datos creadas:\n"
                msg += "\n".join(f"- {name}" for name in created)
                msg += "\n\nBases de datos de la facultad detectadas automaticamente."
                return msg
            return (
                "Todo configurado!\n\n"
                "Facultad: Materie, Lezioni, Esami\n"
                "Personal: Notas, Tareas, Gastos, Habitos"
            )
        except Exception as e:
            return f"Error en setup: {e}"

    # ── Notas ────────────────────────────────────────────

    def add_note(self, content: str) -> str:
        db_id = self.personal.get("notas")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            parts = content.split("\n", 1)
            title = parts[0][:100]
            body = parts[1] if len(parts) > 1 else content
            notion.pages.create(
                parent={"database_id": db_id},
                properties={
                    "Nombre": {"title": [{"text": {"content": title}}]},
                    "Contenido": {"rich_text": [{"text": {"content": body[:2000]}}]},
                    "Fecha": {"date": {"start": date.today().isoformat()}},
                },
            )
            return f"Nota guardada: *{title}*"
        except Exception as e:
            return f"Error al guardar nota: {e}"

    # ── Tareas ───────────────────────────────────────────

    def add_task(self, content: str) -> str:
        db_id = self.personal.get("tareas")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            notion.pages.create(
                parent={"database_id": db_id},
                properties={
                    "Tarea": {"title": [{"text": {"content": content}}]},
                    "Estado": {"select": {"name": "Pendiente"}},
                    "Prioridad": {"select": {"name": "Media"}},
                    "Fecha": {"date": {"start": date.today().isoformat()}},
                },
            )
            return f"Tarea agregada: *{content}*"
        except Exception as e:
            return f"Error: {e}"

    def list_tasks(self) -> str:
        db_id = self.personal.get("tareas")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            results = notion.databases.query(
                database_id=db_id,
                filter={"property": "Estado", "select": {"does_not_equal": "Completada"}},
            )
            tasks = results.get("results", [])
            if not tasks:
                return "No tenes tareas pendientes!"
            msg = "*Tareas pendientes:*\n\n"
            for t in tasks:
                props = t["properties"]
                title = props["Tarea"]["title"][0]["plain_text"] if props["Tarea"]["title"] else "?"
                status = props["Estado"]["select"]["name"] if props["Estado"].get("select") else "?"
                priority = props["Prioridad"]["select"]["name"] if props["Prioridad"].get("select") else "?"
                emoji = {"Alta": "🔴", "Media": "🟡", "Baja": "🔵"}.get(priority, "⚪")
                msg += f"{emoji} {title} [{status}]\n"
            return msg
        except Exception as e:
            return f"Error: {e}"

    # ── Gastos ───────────────────────────────────────────

    def add_expense(self, amount: float, description: str, category: str = "Otros") -> str:
        db_id = self.personal.get("gastos")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            notion.pages.create(
                parent={"database_id": db_id},
                properties={
                    "Descripcion": {"title": [{"text": {"content": description}}]},
                    "Monto": {"number": amount},
                    "Categoria": {"select": {"name": category}},
                    "Fecha": {"date": {"start": date.today().isoformat()}},
                },
            )
            return f"Gasto registrado: ${amount} - {description}"
        except Exception as e:
            return f"Error: {e}"

    def list_expenses(self) -> str:
        db_id = self.personal.get("gastos")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            today = date.today().isoformat()
            results = notion.databases.query(
                database_id=db_id,
                filter={"property": "Fecha", "date": {"equals": today}},
            )
            expenses = results.get("results", [])
            if not expenses:
                return "No registraste gastos hoy."
            total = 0.0
            msg = "*Gastos de hoy:*\n\n"
            for exp in expenses:
                props = exp["properties"]
                desc = props["Descripcion"]["title"][0]["plain_text"] if props["Descripcion"]["title"] else "?"
                amt = props["Monto"]["number"] or 0
                total += amt
                msg += f"- ${amt} - {desc}\n"
            msg += f"\n*Total: ${total}*"
            return msg
        except Exception as e:
            return f"Error: {e}"

    # ── Habitos ──────────────────────────────────────────

    def track_habit(self, habit_name: str) -> str:
        db_id = self.personal.get("habitos")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            notion.pages.create(
                parent={"database_id": db_id},
                properties={
                    "Habito": {"title": [{"text": {"content": habit_name}}]},
                    "Fecha": {"date": {"start": date.today().isoformat()}},
                    "Completado": {"checkbox": True},
                },
            )
            return f"Habito registrado: *{habit_name}*"
        except Exception as e:
            return f"Error: {e}"

    def list_habits(self) -> str:
        db_id = self.personal.get("habitos")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            today = date.today().isoformat()
            results = notion.databases.query(
                database_id=db_id,
                filter={"property": "Fecha", "date": {"equals": today}},
            )
            habits = results.get("results", [])
            if not habits:
                return "No registraste habitos hoy. Arranca con /habito [nombre]!"
            msg = "*Habitos de hoy:*\n\n"
            for h in habits:
                props = h["properties"]
                name = props["Habito"]["title"][0]["plain_text"] if props["Habito"]["title"] else "?"
                done = props["Completado"]["checkbox"]
                msg += f"{'✅' if done else '⬜'} {name}\n"
            return msg
        except Exception as e:
            return f"Error: {e}"

    # ── Datos crudos para briefing ───────────────────────

    def get_pending_tasks_raw(self) -> list:
        db_id = self.personal.get("tareas")
        if not db_id:
            return []
        try:
            results = notion.databases.query(
                database_id=db_id,
                filter={"property": "Estado", "select": {"does_not_equal": "Completada"}},
            )
            return [
                t["properties"]["Tarea"]["title"][0]["plain_text"]
                for t in results.get("results", [])
                if t["properties"]["Tarea"]["title"]
            ]
        except Exception:
            return []

    def get_pending_clases_raw(self) -> list:
        try:
            results = notion.databases.query(
                database_id=self.faculty["lezioni"],
                filter={"property": "Terminado", "checkbox": {"equals": False}},
            )
            return [
                t["properties"]["Tema"]["title"][0]["plain_text"]
                for t in results.get("results", [])
                if t["properties"]["Tema"]["title"]
            ]
        except Exception:
            return []

    def get_today_habits_raw(self) -> list:
        db_id = self.personal.get("habitos")
        if not db_id:
            return []
        try:
            today = date.today().isoformat()
            results = notion.databases.query(
                database_id=db_id,
                filter={"property": "Fecha", "date": {"equals": today}},
            )
            return [
                h["properties"]["Habito"]["title"][0]["plain_text"]
                for h in results.get("results", [])
                if h["properties"]["Habito"]["title"]
            ]
        except Exception:
            return []

    def get_today_expenses_raw(self) -> list:
        db_id = self.personal.get("gastos")
        if not db_id:
            return []
        try:
            today = date.today().isoformat()
            results = notion.databases.query(
                database_id=db_id,
                filter={"property": "Fecha", "date": {"equals": today}},
            )
            return [
                {
                    "desc": e["properties"]["Descripcion"]["title"][0]["plain_text"],
                    "amount": e["properties"]["Monto"]["number"],
                }
                for e in results.get("results", [])
                if e["properties"]["Descripcion"]["title"]
            ]
        except Exception:
            return []

    @staticmethod
    def _get_page_title(page: dict) -> str:
        try:
            title_prop = page.get("properties", {}).get("title", {})
            if title_prop and title_prop.get("title"):
                return title_prop["title"][0]["plain_text"]
        except Exception:
            pass
        return "Pagina sin titulo"
