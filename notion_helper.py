import os
from datetime import date
from notion_client import Client

notion = Client(auth=os.environ.get("NOTION_TOKEN"))

# Nombres de las bases de datos (para auto-descubrimiento)
DB_NAMES = {
    "notas": "Notas",
    "tareas": "Tareas",
    "gastos": "Gastos",
    "habitos": "Habitos",
}


class NotionHelper:
    def __init__(self):
        self.db_ids: dict[str, str | None] = {
            "notas": os.environ.get("NOTION_DB_NOTAS"),
            "tareas": os.environ.get("NOTION_DB_TAREAS"),
            "gastos": os.environ.get("NOTION_DB_GASTOS"),
            "habitos": os.environ.get("NOTION_DB_HABITOS"),
        }
        # Intentar auto-descubrir bases de datos existentes
        self._discover_databases()

    def _discover_databases(self):
        """Busca bases de datos ya creadas por el bot en Notion."""
        try:
            results = notion.search(
                filter={"property": "object", "value": "database"}
            ).get("results", [])

            for db in results:
                title_parts = db.get("title", [])
                if not title_parts:
                    continue
                title = title_parts[0].get("plain_text", "").strip()
                # Quitar emojis del titulo para comparar
                clean = title.replace("📝 ", "").replace("✅ ", "") \
                             .replace("💰 ", "").replace("🏃 ", "").strip()

                for key, name in DB_NAMES.items():
                    if clean == name and not self.db_ids.get(key):
                        self.db_ids[key] = db["id"]
        except Exception:
            pass  # Si falla el descubrimiento, el usuario puede usar /setup

    # ── Setup ────────────────────────────────────────────

    def setup_databases(self) -> str:
        try:
            pages = notion.search(
                filter={"property": "object", "value": "page"}
            ).get("results", [])

            if not pages:
                return (
                    "No encontre ninguna pagina compartida con la integracion.\n\n"
                    "1. Crea una pagina en Notion (ej: 'Bot Personal')\n"
                    "2. Click en '...' > 'Connections' > busca tu integracion\n"
                    "3. Volve a mandar /setup"
                )

            parent_id = pages[0]["id"]
            parent_title = self._get_page_title(pages[0])
            created = []

            if not self.db_ids.get("notas"):
                db = notion.databases.create(
                    parent={"type": "page_id", "page_id": parent_id},
                    title=[{"type": "text", "text": {"content": "📝 Notas"}}],
                    properties={
                        "Nombre": {"title": {}},
                        "Contenido": {"rich_text": {}},
                        "Fecha": {"date": {}},
                        "Tags": {"multi_select": {"options": []}},
                    },
                )
                self.db_ids["notas"] = db["id"]
                created.append("Notas")

            if not self.db_ids.get("tareas"):
                db = notion.databases.create(
                    parent={"type": "page_id", "page_id": parent_id},
                    title=[{"type": "text", "text": {"content": "✅ Tareas"}}],
                    properties={
                        "Tarea": {"title": {}},
                        "Estado": {"select": {"options": [
                            {"name": "Pendiente", "color": "red"},
                            {"name": "En progreso", "color": "yellow"},
                            {"name": "Completada", "color": "green"},
                        ]}},
                        "Prioridad": {"select": {"options": [
                            {"name": "Alta", "color": "red"},
                            {"name": "Media", "color": "yellow"},
                            {"name": "Baja", "color": "blue"},
                        ]}},
                        "Fecha": {"date": {}},
                    },
                )
                self.db_ids["tareas"] = db["id"]
                created.append("Tareas")

            if not self.db_ids.get("gastos"):
                db = notion.databases.create(
                    parent={"type": "page_id", "page_id": parent_id},
                    title=[{"type": "text", "text": {"content": "💰 Gastos"}}],
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
                self.db_ids["gastos"] = db["id"]
                created.append("Gastos")

            if not self.db_ids.get("habitos"):
                db = notion.databases.create(
                    parent={"type": "page_id", "page_id": parent_id},
                    title=[{"type": "text", "text": {"content": "🏃 Habitos"}}],
                    properties={
                        "Habito": {"title": {}},
                        "Fecha": {"date": {}},
                        "Completado": {"checkbox": {}},
                    },
                )
                self.db_ids["habitos"] = db["id"]
                created.append("Habitos")

            if created:
                msg = f"*Setup completo!*\n\nBases de datos creadas en '{parent_title}':\n"
                msg += "\n".join(f"- {name}" for name in created)
                msg += "\n\nYa podes usar todos los comandos."
                return msg
            return "Las bases de datos ya estan configuradas."

        except Exception as e:
            return f"Error en setup: {e}"

    # ── Notas ────────────────────────────────────────────

    def add_note(self, content: str) -> str:
        db_id = self.db_ids.get("notas")
        if not db_id:
            return "Primero ejecuta /setup para configurar Notion."
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
        db_id = self.db_ids.get("tareas")
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
        db_id = self.db_ids.get("tareas")
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
                title = props["Tarea"]["title"][0]["plain_text"] if props["Tarea"]["title"] else "Sin titulo"
                status = props["Estado"]["select"]["name"] if props["Estado"].get("select") else "?"
                priority = props["Prioridad"]["select"]["name"] if props["Prioridad"].get("select") else "?"
                emoji = {"Alta": "🔴", "Media": "🟡", "Baja": "🔵"}.get(priority, "⚪")
                msg += f"{emoji} {title} [{status}]\n"
            return msg
        except Exception as e:
            return f"Error: {e}"

    # ── Gastos ───────────────────────────────────────────

    def add_expense(self, amount: float, description: str, category: str = "Otros") -> str:
        db_id = self.db_ids.get("gastos")
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
        db_id = self.db_ids.get("gastos")
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
            for e in expenses:
                props = e["properties"]
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
        db_id = self.db_ids.get("habitos")
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
        db_id = self.db_ids.get("habitos")
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
        db_id = self.db_ids.get("tareas")
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

    def get_today_habits_raw(self) -> list:
        db_id = self.db_ids.get("habitos")
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
        db_id = self.db_ids.get("gastos")
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

    # ── Utilidades ───────────────────────────────────────

    @staticmethod
    def _get_page_title(page: dict) -> str:
        try:
            title_prop = page.get("properties", {}).get("title", {})
            if title_prop and title_prop.get("title"):
                return title_prop["title"][0]["plain_text"]
        except Exception:
            pass
        return "Pagina sin titulo"
