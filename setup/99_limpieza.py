# Databricks notebook source
# MAGIC %md
# MAGIC # Laboratorio de Agentes – La Tinka · Limpieza
# MAGIC
# MAGIC Borra lo que crearon los participantes durante el lab. Primero corre en modo **simular** para ver la lista; después cambia a **borrar**.
# MAGIC
# MAGIC | Se borra | Cómo se reconoce |
# MAGIC |---|---|
# MAGIC | Apps de MCP | `mcp-<usuario>` de cada participante del grupo |
# MAGIC | Apps de agentes | `agent-bricks-ag-<usuario>` |
# MAGIC | Stores de memoria y sesiones | los que empiezan con `ag-<usuario>-` |
# MAGIC | Schemas de participantes | `ag_<usuario>` (con sus funciones y model services) |
# MAGIC | Carpetas de notebooks | `/Workspace/Users/<correo>/Lab Agentes La Tinka`, `.../lab-agentes` y `/Workspace/Shared/Lab Agentes La Tinka` |
# MAGIC
# MAGIC **No** borra los datos de `mesa_servicio`, el Genie ni el warehouse: los comparte el taller de iniciación.

# COMMAND ----------

dbutils.widgets.text("catalogo", "la_tinka_taller", "1. Catálogo")
dbutils.widgets.text("grupo_participantes", "lab_agentes", "2. Grupo de participantes")
dbutils.widgets.dropdown("modo", "simular", ["simular", "borrar"], "3. Modo")

# COMMAND ----------

import re
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
CATALOGO = dbutils.widgets.get("catalogo").strip()
GRUPO = dbutils.widgets.get("grupo_participantes").strip()
BORRAR = dbutils.widgets.get("modo") == "borrar"
CARPETA_LAB = "Lab Agentes La Tinka"


def slug(usuario):
    return re.sub(r"[^a-z0-9]+", "_", usuario.split("@")[0].lower()).strip("_")[:40]


grupo = next(iter(w.groups.list(filter=f'displayName eq "{GRUPO}"', attributes="id")), None)
assert grupo, f"No encuentro el grupo {GRUPO}"
usuarios = [w.users.get(m.value).user_name for m in (w.groups.get(grupo.id).members or []) if m.ref and m.ref.startswith("Users/")]
print(f"{len(usuarios)} participantes en {GRUPO}")


def accion(texto, funcion):
    print(("🗑  " if BORRAR else "•  ") + texto)
    if BORRAR:
        try:
            funcion()
        except Exception as e:
            print(f"   ⚠ {str(e)[:160]}")

# COMMAND ----------

apps = {a.name for a in w.apps.list()}
stores = w.api_client.do("GET", "/api/2.0/agents/memory-stores", query={"page_size": 500}).get("memory_stores", [])
try:
    sesiones = w.api_client.do("GET", "/api/2.0/agents/session-stores", query={"page_size": 500}).get("session_stores", [])
except Exception:
    sesiones = []

for u in usuarios:
    s = slug(u)
    app_mcp = f"mcp-{s.replace('_', '-')}"[:30].rstrip("-")
    agente = f"ag-{s.replace('_', '-')}"[:17].rstrip("-")
    print(f"\n── {u}")
    for app in (app_mcp, f"agent-bricks-{agente}"):
        if app in apps:
            accion(f"app {app}", lambda app=app: w.apps.delete(app))
    for st in stores + sesiones:
        if st["name"].split("/", 1)[1].startswith(f"{agente}-"):
            accion(f"store {st['name']}", lambda st=st: w.api_client.do("DELETE", f"/api/2.0/agents/{st['name']}"))
    accion(f"schema {CATALOGO}.ag_{s} (CASCADE)", lambda s=s: spark.sql(f"DROP SCHEMA IF EXISTS `{CATALOGO}`.`ag_{s}` CASCADE"))
    for carpeta in (f"/Workspace/Users/{u}/{CARPETA_LAB}", f"/Workspace/Users/{u}/lab-agentes"):
        accion(f"carpeta {carpeta}", lambda c=carpeta: w.workspace.delete(c, recursive=True))

accion(f"\ncarpeta /Workspace/Shared/{CARPETA_LAB}", lambda: w.workspace.delete(f"/Workspace/Shared/{CARPETA_LAB}", recursive=True))
print("\n✓ Listo" if BORRAR else "\nModo simular: cambia 'modo' a 'borrar' y vuelve a correr para borrar.")
