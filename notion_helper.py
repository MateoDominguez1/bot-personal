import os
from datetime import date
from notion_client import Client

notion = Client(auth=os.environ.get("NOTION_TOKEN"))

# ── Paginas principales ──────────────────────────────────
LIFE_PAGE_ID = "2a2c41af-d85a-8020-b2a9-fae9a0d21271"
POLIMI_PAGE_ID = "295c41af-d85a-8015-842c-d23a11302460"

# ── IDs de bases de datos de la facultad (ya existen) ────
FACULTY_DBS = {
    "materie": "295c41af-d85a-80a5-8f87-c1fe893d93ba",
    "lezioni": "296c41af-d85a-8010-8721-c450a1993d5e",
    "esami": "295c41af-d85a-80c1-89ad-c9860e116b0f",
}


LIFE_DBS = {
    "finanzas": "9714bf74-5e96-47d0-83f2-c779768a8c2d",
    "gastos_fijos": "aab98c2c-ff67-476e-8183-85f14ae5d8c8",
    "notas": "2571581b-1f36-4b4f-9efc-b5e5ae34d481",
    "tareas": "336c9e65-dad2-46dd-9668-1c3292741714",
    "habitos": "7c7d53cf-168c-4eec-88d1-cb352d42da67",
    "rutina": "1971262a-849f-4b40-b3f9-cdfdd65d9685",
}


class NotionHelper:
    def __init__(self):
        self.faculty = FACULTY_DBS.copy()
        self.life: dict[str, str | None] = LIFE_DBS.copy()
        self._materie_cache: dict[str, str] = {}

    # ══════════════════════════════════════════════════════
    #  SETUP - Crear DBs en pagina Life
    # ══════════════════════════════════════════════════════

    def setup_databases(self) -> str:
        try:
            created = []

            # ── Finanzas (gastos + ingresos) ─────────────
            if not self.life.get("finanzas"):
                db = notion.databases.create(
                    parent={"type": "page_id", "page_id": LIFE_PAGE_ID},
                    title=[{"type": "text", "text": {"content": "\U0001f4b0 Finanzas"}}],
                    properties={
                        "Concepto": {"title": {}},
                        "Monto": {"number": {"format": "dollar"}},
                        "Tipo": {"select": {"options": [
                            {"name": "Gasto", "color": "red"},
                            {"name": "Ingreso", "color": "green"},
                        ]}},
                        "Categoria": {"select": {"options": [
                            {"name": "Comida", "color": "orange"},
                            {"name": "Transporte", "color": "blue"},
                            {"name": "Entretenimiento", "color": "purple"},
                            {"name": "Salud", "color": "green"},
                            {"name": "Educacion", "color": "yellow"},
                            {"name": "Alquiler", "color": "brown"},
                            {"name": "Servicios", "color": "pink"},
                            {"name": "Ropa", "color": "default"},
                            {"name": "Sueldo", "color": "green"},
                            {"name": "Freelance", "color": "blue"},
                            {"name": "Regalo", "color": "purple"},
                            {"name": "Otros", "color": "gray"},
                        ]}},
                        "Fecha": {"date": {}},
                        "Es fijo": {"checkbox": {}},
                        "Notas": {"rich_text": {}},
                    },
                )
                self.life["finanzas"] = db["id"]
                created.append("Finanzas")

            # ── Gastos Fijos (mensuales) ─────────────────
            if not self.life.get("gastos_fijos"):
                db = notion.databases.create(
                    parent={"type": "page_id", "page_id": LIFE_PAGE_ID},
                    title=[{"type": "text", "text": {"content": "\U0001f4c5 Gastos Fijos"}}],
                    properties={
                        "Concepto": {"title": {}},
                        "Monto": {"number": {"format": "dollar"}},
                        "Tipo": {"select": {"options": [
                            {"name": "Gasto", "color": "red"},
                            {"name": "Ingreso", "color": "green"},
                        ]}},
                        "Categoria": {"select": {"options": [
                            {"name": "Alquiler", "color": "brown"},
                            {"name": "Servicios", "color": "pink"},
                            {"name": "Transporte", "color": "blue"},
                            {"name": "Suscripciones", "color": "purple"},
                            {"name": "Seguro", "color": "yellow"},
                            {"name": "Sueldo", "color": "green"},
                            {"name": "Otros", "color": "gray"},
                        ]}},
                        "Dia del mes": {"number": {}},
                        "Activo": {"checkbox": {}},
                    },
                )
                self.life["gastos_fijos"] = db["id"]
                created.append("Gastos Fijos")

            # ── Notas ────────────────────────────────────
            if not self.life.get("notas"):
                db = notion.databases.create(
                    parent={"type": "page_id", "page_id": LIFE_PAGE_ID},
                    title=[{"type": "text", "text": {"content": "\U0001f4dd Notas"}}],
                    properties={
                        "Nombre": {"title": {}},
                        "Contenido": {"rich_text": {}},
                        "Fecha": {"date": {}},
                        "Tags": {"multi_select": {"options": []}},
                    },
                )
                self.life["notas"] = db["id"]
                created.append("Notas")

            # ── Tareas ───────────────────────────────────
            if not self.life.get("tareas"):
                db = notion.databases.create(
                    parent={"type": "page_id", "page_id": LIFE_PAGE_ID},
                    title=[{"type": "text", "text": {"content": "\u2705 Tareas"}}],
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
                self.life["tareas"] = db["id"]
                created.append("Tareas")

            # ── Habitos ──────────────────────────────────
            if not self.life.get("habitos"):
                db = notion.databases.create(
                    parent={"type": "page_id", "page_id": LIFE_PAGE_ID},
                    title=[{"type": "text", "text": {"content": "\U0001f3c3 Habitos"}}],
                    properties={
                        "Habito": {"title": {}},
                        "Fecha": {"date": {}},
                        "Completado": {"checkbox": {}},
                    },
                )
                self.life["habitos"] = db["id"]
                created.append("Habitos")

            # ── Rutina ───────────────────────────────────
            if not self.life.get("rutina"):
                db = notion.databases.create(
                    parent={"type": "page_id", "page_id": LIFE_PAGE_ID},
                    title=[{"type": "text", "text": {"content": "\U0001f4aa Rutina"}}],
                    properties={
                        "Ejercicio": {"title": {}},
                        "Dia": {"select": {"options": [
                            {"name": "Lunes", "color": "red"},
                            {"name": "Martes", "color": "orange"},
                            {"name": "Miercoles", "color": "yellow"},
                            {"name": "Jueves", "color": "green"},
                            {"name": "Viernes", "color": "blue"},
                            {"name": "Sabado", "color": "purple"},
                            {"name": "Domingo", "color": "gray"},
                        ]}},
                        "Series": {"number": {}},
                        "Repeticiones": {"rich_text": {}},
                        "Musculo": {"select": {"options": [
                            {"name": "Pecho", "color": "red"},
                            {"name": "Espalda", "color": "blue"},
                            {"name": "Hombros", "color": "orange"},
                            {"name": "Biceps", "color": "yellow"},
                            {"name": "Triceps", "color": "green"},
                            {"name": "Piernas", "color": "purple"},
                            {"name": "Abdominales", "color": "pink"},
                            {"name": "Gluteos", "color": "brown"},
                            {"name": "Cardio", "color": "gray"},
                            {"name": "Full body", "color": "default"},
                        ]}},
                        "Notas": {"rich_text": {}},
                    },
                )
                self.life["rutina"] = db["id"]
                created.append("Rutina")

            if created:
                msg = "*Setup completo!*\n\nCreado en pagina Life:\n"
                msg += "\n".join(f"- {name}" for name in created)
                msg += "\n\nFacultad: usa tus DBs existentes."
                return msg
            return (
                "Todo configurado!\n\n"
                "Life: Finanzas, Gastos Fijos, Notas, Tareas, Habitos, Rutina\n"
                "Facultad: Materie, Lezioni, Esami"
            )
        except Exception as e:
            return f"Error en setup: {e}"

    # ══════════════════════════════════════════════════════
    #  FINANZAS - Gastos, Ingresos, Fijos
    # ══════════════════════════════════════════════════════

    def add_transaction(self, amount: float, description: str,
                        tipo: str = "Gasto", category: str = "Otros",
                        notes: str = "") -> str:
        db_id = self.life.get("finanzas")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            properties = {
                "Concepto": {"title": [{"text": {"content": description}}]},
                "Monto": {"number": amount},
                "Tipo": {"select": {"name": tipo}},
                "Categoria": {"select": {"name": category}},
                "Fecha": {"date": {"start": date.today().isoformat()}},
                "Es fijo": {"checkbox": False},
            }
            if notes:
                properties["Notas"] = {"rich_text": [{"text": {"content": notes[:2000]}}]}

            notion.pages.create(parent={"database_id": db_id}, properties=properties)
            emoji = "\U0001f534" if tipo == "Gasto" else "\U0001f7e2"
            self.update_balance_notion()
            return f"{emoji} {tipo} registrado: ${amount} - {description} [{category}]"
        except Exception as e:
            return f"Error: {e}"

    def add_fixed(self, amount: float, description: str,
                  tipo: str = "Gasto", category: str = "Otros",
                  dia_mes: int = 1) -> str:
        db_id = self.life.get("gastos_fijos")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            notion.pages.create(
                parent={"database_id": db_id},
                properties={
                    "Concepto": {"title": [{"text": {"content": description}}]},
                    "Monto": {"number": amount},
                    "Tipo": {"select": {"name": tipo}},
                    "Categoria": {"select": {"name": category}},
                    "Dia del mes": {"number": dia_mes},
                    "Activo": {"checkbox": True},
                },
            )
            return f"Fijo registrado: ${amount} - {description} (dia {dia_mes} de cada mes)"
        except Exception as e:
            return f"Error: {e}"

    def list_finances(self, period: str = "today") -> str:
        db_id = self.life.get("finanzas")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            today = date.today().isoformat()
            if period == "today":
                query_filter = {"property": "Fecha", "date": {"equals": today}}
                period_label = "hoy"
            elif period == "month":
                first_of_month = date.today().replace(day=1).isoformat()
                query_filter = {"property": "Fecha", "date": {"on_or_after": first_of_month}}
                period_label = "este mes"
            else:
                query_filter = {"property": "Fecha", "date": {"equals": today}}
                period_label = "hoy"

            results = notion.databases.query(
                database_id=db_id, filter=query_filter,
                sorts=[{"property": "Fecha", "direction": "descending"}],
            )
            items = results.get("results", [])
            if not items:
                return f"No hay movimientos {period_label}."

            gastos_total = 0.0
            ingresos_total = 0.0
            msg = f"*Finanzas {period_label}:*\n\n"

            for item in items:
                props = item["properties"]
                desc = props["Concepto"]["title"][0]["plain_text"] if props["Concepto"]["title"] else "?"
                amt = props["Monto"]["number"] or 0
                tipo = props["Tipo"]["select"]["name"] if props["Tipo"].get("select") else "?"
                cat = props["Categoria"]["select"]["name"] if props["Categoria"].get("select") else ""

                if tipo == "Gasto":
                    gastos_total += amt
                    msg += f"\U0001f534 ${amt} - {desc} [{cat}]\n"
                else:
                    ingresos_total += amt
                    msg += f"\U0001f7e2 ${amt} - {desc} [{cat}]\n"

            balance = ingresos_total - gastos_total
            msg += f"\n*Ingresos:* ${ingresos_total}"
            msg += f"\n*Gastos:* ${gastos_total}"
            msg += f"\n*Balance:* ${balance}"
            return msg
        except Exception as e:
            return f"Error: {e}"

    def list_fixed(self) -> str:
        db_id = self.life.get("gastos_fijos")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            results = notion.databases.query(
                database_id=db_id,
                filter={"property": "Activo", "checkbox": {"equals": True}},
                sorts=[{"property": "Dia del mes", "direction": "ascending"}],
            )
            items = results.get("results", [])
            if not items:
                return "No hay gastos/ingresos fijos registrados."

            gastos = 0.0
            ingresos = 0.0
            msg = "*Fijos mensuales:*\n\n"
            for item in items:
                props = item["properties"]
                desc = props["Concepto"]["title"][0]["plain_text"] if props["Concepto"]["title"] else "?"
                amt = props["Monto"]["number"] or 0
                tipo = props["Tipo"]["select"]["name"] if props["Tipo"].get("select") else "?"
                dia = int(props["Dia del mes"]["number"] or 1)

                if tipo == "Gasto":
                    gastos += amt
                    msg += f"\U0001f534 Dia {dia}: ${amt} - {desc}\n"
                else:
                    ingresos += amt
                    msg += f"\U0001f7e2 Dia {dia}: ${amt} - {desc}\n"

            msg += f"\n*Total fijo gastos:* ${gastos}/mes"
            msg += f"\n*Total fijo ingresos:* ${ingresos}/mes"
            msg += f"\n*Balance fijo:* ${ingresos - gastos}/mes"
            return msg
        except Exception as e:
            return f"Error: {e}"

    def get_balance(self) -> str:
        """Calcula balance total: todos los ingresos - todos los gastos + fijos del mes."""
        try:
            # Movimientos del mes actual
            first_of_month = date.today().replace(day=1).isoformat()
            fin_db = self.life.get("finanzas")
            fijos_db = self.life.get("gastos_fijos")

            ingresos = 0.0
            gastos = 0.0

            if fin_db:
                results = notion.databases.query(
                    database_id=fin_db,
                    filter={"property": "Fecha", "date": {"on_or_after": first_of_month}},
                )
                for item in results.get("results", []):
                    props = item["properties"]
                    amt = props["Monto"]["number"] or 0
                    tipo = props["Tipo"]["select"]["name"] if props["Tipo"].get("select") else ""
                    if tipo == "Ingreso":
                        ingresos += amt
                    else:
                        gastos += amt

            # Fijos mensuales
            fijos_gastos = 0.0
            fijos_ingresos = 0.0
            if fijos_db:
                results = notion.databases.query(
                    database_id=fijos_db,
                    filter={"property": "Activo", "checkbox": {"equals": True}},
                )
                for item in results.get("results", []):
                    props = item["properties"]
                    amt = props["Monto"]["number"] or 0
                    tipo = props["Tipo"]["select"]["name"] if props["Tipo"].get("select") else ""
                    if tipo == "Ingreso":
                        fijos_ingresos += amt
                    else:
                        fijos_gastos += amt

            balance = (ingresos + fijos_ingresos) - (gastos + fijos_gastos)

            msg = "*💰 Balance del mes*\n\n"
            msg += f"*Ingresos registrados:* ${ingresos}\n"
            msg += f"*Gastos registrados:* ${gastos}\n"
            msg += f"*Fijos ingresos:* ${fijos_ingresos}/mes\n"
            msg += f"*Fijos gastos:* ${fijos_gastos}/mes\n"
            msg += f"\n*💵 Balance estimado: ${balance}*"

            if balance > 0:
                msg += "\n\nVas bien este mes!"
            elif balance < 0:
                msg += f"\n\nEstas ${abs(balance)} en rojo. Cuidado con los gastos!"
            else:
                msg += "\n\nEstas justo, sin excedente."
            return msg
        except Exception as e:
            return f"Error al calcular balance: {e}"

    def delete_transaction(self, search_term: str, tipo: str | None = None) -> str:
        """Busca y elimina un gasto o ingreso por descripcion."""
        db_id = self.life.get("finanzas")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            results = notion.databases.query(database_id=db_id)
            matches = []
            for item in results.get("results", []):
                props = item["properties"]
                desc = props["Concepto"]["title"][0]["plain_text"] if props["Concepto"]["title"] else ""
                t = props["Tipo"]["select"]["name"] if props["Tipo"].get("select") else ""
                amt = props["Monto"]["number"] or 0
                fecha = props["Fecha"]["date"]["start"] if props.get("Fecha", {}).get("date") else ""
                if search_term.lower() in desc.lower():
                    if tipo and t.lower() != tipo.lower():
                        continue
                    matches.append({"id": item["id"], "desc": desc, "tipo": t, "amount": amt, "fecha": fecha})

            if not matches:
                return f"No encontre '{search_term}' en tus movimientos."
            if len(matches) == 1:
                m = matches[0]
                notion.pages.update(page_id=m["id"], archived=True)
                emoji = "\U0001f534" if m["tipo"] == "Gasto" else "\U0001f7e2"
                return f"{emoji} Eliminado: ${m['amount']} - {m['desc']} ({m['fecha']})"
            # Multiple matches — list them and ask
            msg = f"Encontre {len(matches)} movimientos con '{search_term}':\n\n"
            for i, m in enumerate(matches[:8], 1):
                emoji = "\U0001f534" if m["tipo"] == "Gasto" else "\U0001f7e2"
                msg += f"{i}. {emoji} ${m['amount']} - {m['desc']} ({m['fecha']})\n"
            msg += "\nSe mas especifico: dime el monto o la fecha para eliminar el correcto."
            return msg
        except Exception as e:
            return f"Error: {e}"

    def update_balance_notion(self) -> None:
        """Actualiza el bloque de balance en la pagina Life de Notion."""
        try:
            balance_data = self._compute_balance_raw()
            balance = balance_data["balance"]
            # Find the callout block with 💰 on the Life page
            blocks = notion.blocks.children.list(block_id=LIFE_PAGE_ID)
            for block in blocks.get("results", []):
                if block["type"] == "callout":
                    rich = block["callout"].get("rich_text", [])
                    text = rich[0]["plain_text"] if rich else ""
                    if "balance" in text.lower() or "💰" in text or "Balance" in text:
                        notion.blocks.update(
                            block_id=block["id"],
                            callout={
                                "rich_text": [{"type": "text", "text": {
                                    "content": f"💰 Balance actual: ${balance:,.2f}\n"
                                               f"Ingresos: ${balance_data['ingresos']:,.2f} | "
                                               f"Gastos: ${balance_data['gastos']:,.2f}"
                                }}],
                                "icon": {"emoji": "💰"},
                            },
                        )
                        return
        except Exception as e:
            print(f"update_balance_notion error: {e}")

    def _compute_balance_raw(self) -> dict:
        """Devuelve dict con ingresos, gastos, balance del mes."""
        first_of_month = date.today().replace(day=1).isoformat()
        fin_db = self.life.get("finanzas")
        fijos_db = self.life.get("gastos_fijos")
        ingresos = gastos = fijos_ingresos = fijos_gastos = 0.0

        if fin_db:
            for item in notion.databases.query(
                database_id=fin_db,
                filter={"property": "Fecha", "date": {"on_or_after": first_of_month}},
            ).get("results", []):
                props = item["properties"]
                amt = props["Monto"]["number"] or 0
                tipo = props["Tipo"]["select"]["name"] if props["Tipo"].get("select") else ""
                if tipo == "Ingreso":
                    ingresos += amt
                else:
                    gastos += amt

        if fijos_db:
            for item in notion.databases.query(
                database_id=fijos_db,
                filter={"property": "Activo", "checkbox": {"equals": True}},
            ).get("results", []):
                props = item["properties"]
                amt = props["Monto"]["number"] or 0
                tipo = props["Tipo"]["select"]["name"] if props["Tipo"].get("select") else ""
                if tipo == "Ingreso":
                    fijos_ingresos += amt
                else:
                    fijos_gastos += amt

        return {
            "ingresos": ingresos + fijos_ingresos,
            "gastos": gastos + fijos_gastos,
            "balance": (ingresos + fijos_ingresos) - (gastos + fijos_gastos),
        }

    # ══════════════════════════════════════════════════════
    #  RUTINA
    # ══════════════════════════════════════════════════════

    def add_exercise(self, ejercicio: str, dia: str, series: int = 0,
                     reps: str = "", musculo: str = "", notas: str = "") -> str:
        db_id = self.life.get("rutina")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            properties = {
                "Ejercicio": {"title": [{"text": {"content": ejercicio}}]},
                "Dia": {"select": {"name": dia}},
            }
            if series:
                properties["Series"] = {"number": series}
            if reps:
                properties["Repeticiones"] = {"rich_text": [{"text": {"content": reps}}]}
            if musculo:
                properties["Musculo"] = {"select": {"name": musculo}}
            if notas:
                properties["Notas"] = {"rich_text": [{"text": {"content": notas}}]}

            notion.pages.create(parent={"database_id": db_id}, properties=properties)
            return f"Ejercicio agregado: *{ejercicio}* ({dia})"
        except Exception as e:
            return f"Error: {e}"

    def add_routine_bulk(self, exercises: list[dict]) -> str:
        """Agrega multiples ejercicios de una vez (para importar rutina)."""
        db_id = self.life.get("rutina")
        if not db_id:
            return "Primero ejecuta /setup."
        added = 0
        errors = 0
        for ex in exercises:
            try:
                properties = {
                    "Ejercicio": {"title": [{"text": {"content": ex.get("ejercicio", "?")}}]},
                    "Dia": {"select": {"name": ex.get("dia", "Lunes")}},
                }
                if ex.get("series"):
                    properties["Series"] = {"number": ex["series"]}
                if ex.get("reps"):
                    properties["Repeticiones"] = {"rich_text": [{"text": {"content": ex["reps"]}}]}
                if ex.get("musculo"):
                    properties["Musculo"] = {"select": {"name": ex["musculo"]}}
                if ex.get("notas"):
                    properties["Notas"] = {"rich_text": [{"text": {"content": ex["notas"]}}]}

                notion.pages.create(parent={"database_id": db_id}, properties=properties)
                added += 1
            except Exception:
                errors += 1
        msg = f"Rutina importada: {added} ejercicios agregados."
        if errors:
            msg += f" ({errors} errores)"
        return msg

    def list_routine(self, dia: str | None = None) -> str:
        db_id = self.life.get("rutina")
        if not db_id:
            return "Primero ejecuta /setup."
        try:
            query_filter = None
            if dia:
                query_filter = {"property": "Dia", "select": {"equals": dia}}
            results = notion.databases.query(
                database_id=db_id,
                filter=query_filter,
            )
            items = results.get("results", [])
            if not items:
                return f"No hay ejercicios{'para ' + dia if dia else ''} en la rutina."

            # Agrupar por dia
            by_day: dict[str, list] = {}
            for item in items:
                props = item["properties"]
                name = props["Ejercicio"]["title"][0]["plain_text"] if props["Ejercicio"]["title"] else "?"
                d = props["Dia"]["select"]["name"] if props["Dia"].get("select") else "?"
                series = int(props["Series"]["number"] or 0) if props.get("Series", {}).get("number") else 0
                reps_parts = props.get("Repeticiones", {}).get("rich_text", [])
                reps = reps_parts[0]["plain_text"] if reps_parts else ""
                musculo_sel = props.get("Musculo", {}).get("select")
                musculo = musculo_sel["name"] if musculo_sel else ""

                detail = f"  - {name}"
                if series and reps:
                    detail += f" ({series}x{reps})"
                elif series:
                    detail += f" ({series} series)"
                if musculo:
                    detail += f" [{musculo}]"
                by_day.setdefault(d, []).append(detail)

            day_order = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
            msg = "*Rutina:*\n\n"
            for d in day_order:
                if d in by_day:
                    msg += f"*{d}:*\n" + "\n".join(by_day[d]) + "\n\n"
            return msg.strip()
        except Exception as e:
            return f"Error: {e}"

    # ══════════════════════════════════════════════════════
    #  FACULTAD - Materias, Lecciones, Examenes
    # ══════════════════════════════════════════════════════

    def _get_materia_id(self, nombre: str) -> str | None:
        nombre_lower = nombre.lower().strip()
        # Rebuild cache every call (small DB, safe to do)
        try:
            results = notion.databases.query(database_id=self.faculty["materie"])
            for page in results.get("results", []):
                title_parts = page["properties"]["Nombre"]["title"]
                if not title_parts:
                    continue
                materia_name = title_parts[0]["plain_text"]
                self._materie_cache[materia_name.lower().strip()] = page["id"]
        except Exception:
            pass

        # Exact match first
        if nombre_lower in self._materie_cache:
            return self._materie_cache[nombre_lower]

        # Substring match: user input is substring of materia name OR vice versa
        for cached_name, cached_id in self._materie_cache.items():
            if nombre_lower in cached_name or cached_name in nombre_lower:
                return cached_id

        # Word-level partial match: any word of the query appears in the materia name
        nombre_words = nombre_lower.split()
        for cached_name, cached_id in self._materie_cache.items():
            for word in nombre_words:
                if len(word) >= 3 and word in cached_name:
                    return cached_id

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
                year = props.get("Ano universitario", {}).get("status", {})
                year_name = year.get("name", "?") if year else "?"
                msg += f"- *{nombre}* - {prof_name} ({year_name})\n"
            return msg
        except Exception as e:
            return f"Error: {e}"

    def add_clase(self, materia: str, tema: str, fecha: str | None = None,
                  link: str | None = None) -> str:
        try:
            materia_id = self._get_materia_id(materia)
            if not materia_id:
                materias_list = ", ".join(self._materie_cache.keys()) or "ninguna encontrada"
                return f"No encontre la materia '{materia}'.\nDisponibles: {materias_list}"
            properties = {
                "Tema": {"title": [{"text": {"content": tema}}]},
                "Materia": {"relation": [{"id": materia_id}]},
                "Estado": {"select": {"name": "Visto en clase"}},
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
        try:
            if estado:
                query_filter = {"property": "Estado", "select": {"equals": estado}}
            else:
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
                "Clase Pendiente": "\U0001f534", "Estudiando": "\U0001f535",
                "Aprendido": "\U0001f7e2", "Visto en clase": "\U0001f7e1",
                "Clase pendiente a ver": "\U0001f7e4",
            }
            msg = "*Clases:*\n\n"
            for c in clases[:20]:
                props = c["properties"]
                tema = props["Tema"]["title"][0]["plain_text"] if props["Tema"]["title"] else "?"
                est = props["Estado"]["select"]["name"] if props["Estado"].get("select") else "?"
                emoji = estado_emoji.get(est, "\u26aa")
                fecha = ""
                if props.get("Fecha clase", {}).get("date"):
                    fecha = f" ({props['Fecha clase']['date']['start']})"
                msg += f"{emoji} {tema}{fecha} [{est}]\n"
            return msg
        except Exception as e:
            return f"Error: {e}"

    def update_clase_estado(self, tema_query: str, nuevo_estado: str) -> str:
        estados_validos = [
            "Clase Pendiente", "Estudiando", "Aprendido",
            "Visto en clase", "Clase pendiente a ver",
        ]
        estado_match = None
        for est in estados_validos:
            if nuevo_estado.lower() in est.lower():
                estado_match = est
                break
        if not estado_match:
            return "Estado no valido. Opciones:\n" + "\n".join(f"- {e}" for e in estados_validos)
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
            return f"No encontre clase con '{tema_query}' en el tema."
        except Exception as e:
            return f"Error: {e}"

    def list_examenes(self) -> str:
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
    #  NOTAS, TAREAS, HABITOS (en Life)
    # ══════════════════════════════════════════════════════

    def add_note(self, content: str) -> str:
        db_id = self.life.get("notas")
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
            return f"Error: {e}"

    def add_task(self, content: str) -> str:
        db_id = self.life.get("tareas")
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
        db_id = self.life.get("tareas")
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
                priority = props["Prioridad"]["select"]["name"] if props["Prioridad"].get("select") else "?"
                emoji = {"Alta": "\U0001f534", "Media": "\U0001f7e1", "Baja": "\U0001f535"}.get(priority, "\u26aa")
                msg += f"{emoji} {title}\n"
            return msg
        except Exception as e:
            return f"Error: {e}"

    def track_habit(self, habit_name: str) -> str:
        db_id = self.life.get("habitos")
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
        db_id = self.life.get("habitos")
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
                msg += f"{'\u2705' if done else '\u2b1c'} {name}\n"
            return msg
        except Exception as e:
            return f"Error: {e}"

    # ══════════════════════════════════════════════════════
    #  DATOS CRUDOS PARA BRIEFING
    # ══════════════════════════════════════════════════════

    def get_pending_tasks_raw(self) -> list:
        db_id = self.life.get("tareas")
        if not db_id:
            return []
        try:
            results = notion.databases.query(
                database_id=db_id,
                filter={"property": "Estado", "select": {"does_not_equal": "Completada"}},
            )
            return [t["properties"]["Tarea"]["title"][0]["plain_text"]
                    for t in results.get("results", []) if t["properties"]["Tarea"]["title"]]
        except Exception:
            return []

    def get_pending_clases_raw(self) -> list:
        try:
            results = notion.databases.query(
                database_id=self.faculty["lezioni"],
                filter={"property": "Terminado", "checkbox": {"equals": False}},
            )
            return [t["properties"]["Tema"]["title"][0]["plain_text"]
                    for t in results.get("results", []) if t["properties"]["Tema"]["title"]]
        except Exception:
            return []

    def get_today_habits_raw(self) -> list:
        db_id = self.life.get("habitos")
        if not db_id:
            return []
        try:
            today = date.today().isoformat()
            results = notion.databases.query(
                database_id=db_id, filter={"property": "Fecha", "date": {"equals": today}},
            )
            return [h["properties"]["Habito"]["title"][0]["plain_text"]
                    for h in results.get("results", []) if h["properties"]["Habito"]["title"]]
        except Exception:
            return []

    def get_today_expenses_raw(self) -> list:
        db_id = self.life.get("finanzas")
        if not db_id:
            return []
        try:
            today = date.today().isoformat()
            results = notion.databases.query(
                database_id=db_id, filter={"property": "Fecha", "date": {"equals": today}},
            )
            return [
                {"desc": e["properties"]["Concepto"]["title"][0]["plain_text"],
                 "amount": e["properties"]["Monto"]["number"],
                 "tipo": e["properties"]["Tipo"]["select"]["name"]}
                for e in results.get("results", []) if e["properties"]["Concepto"]["title"]
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
        return "Sin titulo"
