# Databricks notebook source
# MAGIC %md
# MAGIC # Laboratorio de Agentes en Databricks – La Tinka · Setup
# MAGIC
# MAGIC Este notebook deja listo **todo** lo que necesita el laboratorio técnico. Lo corre **una sola vez** la persona administradora, unos días antes del taller.
# MAGIC
# MAGIC | | Qué hace |
# MAGIC |---|---|
# MAGIC | Validaciones | Grupo, Unity Catalog, Apps, MCP gestionados, modelos de Unity Gateway, tablas de sistema |
# MAGIC | Datos | Reutiliza `mesa_servicio` del taller de iniciación (o lo crea si no existe) y agrega la vista `incidencias_lab` |
# MAGIC | Genie | Reutiliza el espacio **Mesa de servicio** (o lo crea) |
# MAGIC | Cómputo | Reutiliza el SQL Warehouse del taller (o crea uno serverless) |
# MAGIC | Participantes | Un schema `ag_<usuario>` por persona del grupo, con su copia de los notebooks del lab |
# MAGIC | Permisos | Lo mínimo para que cada participante construya sus tools, su MCP y su agente |
# MAGIC
# MAGIC ### Cómo usarlo
# MAGIC 1. Importa la carpeta completa del laboratorio (con `setup/` y `labs/`) a tu workspace.
# MAGIC 2. Llena los campos de arriba. Solo **grupo_participantes** es obligatorio si usas el catálogo del taller de iniciación.
# MAGIC 3. Conecta el notebook a **Serverless** y haz clic en **Run all** (≈ 3–6 min).
# MAGIC 4. Revisa el resumen final: la tabla de verificación indica qué está listo y qué falta activar en **Previews**.
# MAGIC
# MAGIC Puedes correrlo varias veces: no duplica nada. Si llega alguien nuevo al grupo, vuelve a correrlo y se le crea su espacio.
# MAGIC
# MAGIC **Requisitos:** ser administrador del workspace (o tener permisos para crear catálogos, warehouses, espacios de Genie y escribir en carpetas de usuario) y que el grupo de participantes exista.

# COMMAND ----------

dbutils.widgets.text("catalogo", "la_tinka_taller", "1. Catálogo")
dbutils.widgets.text("esquema_datos", "mesa_servicio", "2. Esquema de datos")
dbutils.widgets.text("grupo_participantes", "lab_agentes", "3. Grupo de participantes")
dbutils.widgets.text("genie_space_id", "", "4. ID del Genie (opcional)")
dbutils.widgets.text("fecha_taller", "2026-11-26", "5. Fecha del taller (opcional)")
dbutils.widgets.dropdown("copiar_notebooks", "si", ["si", "no"], "6. Copiar los notebooks a cada participante")

# COMMAND ----------

import os, sys, json, re, time
from datetime import date

sys.path.append(os.path.abspath("recursos"))
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ImportFormat, ObjectType, ExportFormat, Language
import datos, consultas, genie

CATALOGO = dbutils.widgets.get("catalogo").strip()
ESQUEMA = dbutils.widgets.get("esquema_datos").strip()
GRUPO = dbutils.widgets.get("grupo_participantes").strip()
GENIE_WIDGET = dbutils.widgets.get("genie_space_id").strip()
FECHA_TALLER = date.fromisoformat(dbutils.widgets.get("fecha_taller").strip() or "2026-11-26")
COPIAR = dbutils.widgets.get("copiar_notebooks") == "si"

NOMBRE_WAREHOUSE = "Taller La Tinka"
NOMBRE_GENIE = "Mesa de servicio"
CARPETA_LAB = "Lab Agentes La Tinka"
# Modelos candidatos (model services de system.ai en Unity Gateway), en orden de preferencia
MODELOS = ["claude-sonnet-4-5", "claude-sonnet-4-6", "claude-sonnet-5", "claude-haiku-4-5",
           "gpt-oss-120b", "meta-llama-3-3-70b-instruct"]

assert CATALOGO and ESQUEMA and GRUPO, "Llena catalogo, esquema_datos y grupo_participantes."

w = WorkspaceClient()
YO = w.current_user.me().user_name
HOST = w.config.host.rstrip("/")
T = f"`{CATALOGO}`.`{ESQUEMA}`"
RAIZ_REPO = os.path.dirname(os.path.abspath("."))           # carpeta que contiene setup/ y labs/
RAIZ_REPO_WS = os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext()
                               .notebookPath().get().rsplit("/", 1)[0])
VERIFICACION = []  # (componente, estado, detalle)


def api(metodo, ruta, cuerpo=None, query=None):
    return w.api_client.do(metodo, ruta, body=cuerpo, query=query)


def paso(n, texto):
    print(f"\n━━━ Paso {n}: {texto}")


def ok(texto):
    print(f"  ✓ {texto}")


def aviso(texto):
    print(f"  ⚠ {texto}")


def verificar(componente, estado, detalle=""):
    VERIFICACION.append((componente, estado, detalle))
    (ok if estado == "listo" else aviso)(f"{componente}: {detalle}" if detalle else componente)


def slug(usuario):
    """Mismo cálculo que labs/Includes/Setup-Lab: parte local del correo en minúsculas."""
    return re.sub(r"[^a-z0-9]+", "_", usuario.split("@")[0].lower()).strip("_")[:40]


class ErrorSetup(Exception):
    """Error con un mensaje en español que explica qué hacer."""

# COMMAND ----------

# MAGIC %md ## Paso 1 – Validaciones previas

# COMMAND ----------

paso(1, "Validaciones previas")
grupos = list(w.groups.list(filter=f'displayName eq "{GRUPO}"', attributes="id,displayName,members"))
if not grupos:
    raise ErrorSetup(
        f"No encuentro el grupo '{GRUPO}' en este workspace. Pide a un administrador de la cuenta que cree el grupo "
        f"(a nivel de cuenta), agregue a los participantes y lo asigne a este workspace. Después vuelve a correr el notebook.")
grupo = w.groups.get(grupos[0].id)
PARTICIPANTES = []
for m in grupo.members or []:
    if m.ref and m.ref.startswith("Users/"):
        try:
            PARTICIPANTES.append(w.users.get(m.value).user_name)
        except Exception:
            pass
ok(f"Grupo '{GRUPO}' con {len(PARTICIPANTES)} usuarios directos")

metastore = spark.sql("SELECT current_metastore()").first()[0]
ok(f"Unity Catalog activo (metastore {metastore.split(':')[-1]})")
ok(f"Corriendo como {YO}")

try:
    n_apps = len(list(w.apps.list()))
    verificar("Databricks Apps", "listo", f"{n_apps} apps en el workspace; cada participante creará 2 (mcp- y agent-bricks-)")
except Exception as e:
    verificar("Databricks Apps", "falta", f"No pude listar apps: {e}")

# COMMAND ----------

# MAGIC %md ## Paso 2 – Datos de la mesa de servicio

# COMMAND ----------

paso(2, "Datos de la mesa de servicio")
existia_catalogo = CATALOGO in [r.catalog for r in spark.sql("SHOW CATALOGS").collect()]
if not existia_catalogo:
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS `{CATALOGO}` COMMENT 'Talleres de Databricks – La Tinka'")
    except Exception as e:
        raise ErrorSetup(
            f"No pude crear el catálogo '{CATALOGO}'. Si tu metastore no tiene almacenamiento por defecto, crea el catálogo "
            f"desde Catalog Explorer (eligiendo una ubicación de almacenamiento) y vuelve a correr el notebook.\nDetalle: {e}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {T} COMMENT 'Mesa de servicio de TI (datos sintéticos)'")
spark.sql(f"CREATE TABLE IF NOT EXISTS {T}.taller_config (clave STRING, valor STRING) "
          "COMMENT 'Identificadores de los recursos creados por los setups de los talleres'")


def config_leer(clave):
    fila = spark.sql(f"SELECT valor FROM {T}.taller_config WHERE clave = '{clave}'").first()
    return fila[0] if fila else None


def config_guardar(clave, valor):
    spark.sql(f"MERGE INTO {T}.taller_config t USING (SELECT '{clave}' AS clave, '{valor}' AS valor) s "
              "ON t.clave = s.clave WHEN MATCHED THEN UPDATE SET valor = s.valor WHEN NOT MATCHED THEN INSERT *")


if not existia_catalogo:
    config_guardar("catalogo_creado_por_setup", "si")

tablas_existentes = {r.tableName for r in spark.sql(f"SHOW TABLES IN {T}").collect()}
if {"incidencias", "equipos", "proyectos", "encuestas_satisfaccion"} <= tablas_existentes:
    ok("Reutilizo las tablas del taller de iniciación")
else:
    from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType, DateType
    tablas = datos.generar(FECHA_TALLER)
    ESQUEMAS = {
        "equipos": ("Equipos de la mesa de servicio, con su gerente y área.",
                    [("equipo", StringType(), "Nombre del equipo resolutor"),
                     ("gerente", StringType(), "Gerente responsable del equipo"),
                     ("area", StringType(), "Área de la empresa a la que pertenece el equipo")]),
        "incidencias": ("Tickets de la mesa de servicio de TI: reclamos de jugadores, agentes y fallas internas.",
                        [("id_incidencia", StringType(), "Identificador del ticket (INC-00001)"),
                         ("fecha_apertura", TimestampType(), "Fecha y hora en que se abrió el ticket"),
                         ("fecha_cierre", TimestampType(), "Fecha y hora de cierre; vacía si sigue abierto"),
                         ("prioridad", StringType(), "P1 (urgente) a P4 (baja)"),
                         ("categoria", StringType(), "Tipo de problema"),
                         ("equipo", StringType(), "Equipo que atiende el ticket"),
                         ("estatus", StringType(), "Abierta, En progreso o Cerrada"),
                         ("sla_horas", IntegerType(), "Horas comprometidas para resolver según la prioridad"),
                         ("descripcion", StringType(), "Texto libre del reclamo")]),
        "encuestas_satisfaccion": ("Encuesta que responde el usuario al cerrarse su incidencia.",
                                   [("id_incidencia", StringType(), "Ticket evaluado (une con incidencias)"),
                                    ("calificacion", IntegerType(), "Calificación de 1 (muy mala) a 5 (excelente)"),
                                    ("comentario", StringType(), "Comentario libre del usuario"),
                                    ("fecha_encuesta", DateType(), "Fecha en que se respondió la encuesta")]),
        "proyectos": ("Proyectos del área de TI con su avance y fecha compromiso.",
                      [("id_proyecto", StringType(), "Identificador del proyecto"),
                       ("nombre", StringType(), "Nombre del proyecto"),
                       ("responsable", StringType(), "Líder del proyecto"),
                       ("fecha_inicio", DateType(), "Fecha de inicio"),
                       ("fecha_compromiso", DateType(), "Fecha comprometida de entrega"),
                       ("pct_avance", IntegerType(), "Porcentaje de avance (0 a 100)"),
                       ("estatus", StringType(), "En curso, En riesgo, En pausa o Completado")]),
    }
    for nombre, (comentario_tabla, columnas) in ESQUEMAS.items():
        esquema_spark = StructType([StructField(c, tipo, True) for c, tipo, _ in columnas])
        filas = [tuple(r[c] for c, _, _ in columnas) for r in tablas[nombre]]
        (spark.createDataFrame(filas, esquema_spark).write.mode("overwrite")
         .option("overwriteSchema", "true").saveAsTable(f"{T}.{nombre}"))
        spark.sql(f"COMMENT ON TABLE {T}.{nombre} IS '{comentario_tabla}'")
        for c, _, desc in columnas:
            spark.sql(f"ALTER TABLE {T}.{nombre} ALTER COLUMN {c} COMMENT '{desc}'")
        ok(f"{nombre}: {len(filas):,} filas")
    config_guardar("fecha_taller", FECHA_TALLER.isoformat())

spark.sql(consultas.vista_incidencias_sla(CATALOGO, ESQUEMA))

# Fecha de corte del lab: las horas abiertas se calculan contra la mañana del taller, para que
# las respuestas del ensayo y del día sean idénticas.
FECHA_DATOS = date.fromisoformat(config_leer("fecha_taller") or FECHA_TALLER.isoformat())
CORTE = f"{FECHA_DATOS.isoformat()} 09:00:00"
spark.sql(f"""CREATE OR REPLACE VIEW {T}.incidencias_lab
COMMENT 'Incidencias con las horas que llevan abiertas a la fecha de corte del laboratorio ({CORTE}). Úsala en las tools del lab de agentes.'
AS SELECT id_incidencia, prioridad, categoria, equipo, estatus, descripcion, sla_horas, fecha_apertura, fecha_cierre,
  CAST(timestampdiff(MINUTE, fecha_apertura, coalesce(fecha_cierre, TIMESTAMP'{CORTE}')) / 60.0 AS DOUBLE) AS horas_abierta
FROM {T}.incidencias""")
config_guardar("lab_fecha_corte", CORTE)
n_p1 = spark.sql(f"SELECT count(*) FROM {T}.incidencias_lab WHERE estatus <> 'Cerrada' AND prioridad = 'P1'").first()[0]
verificar("Datos", "listo", f"{CATALOGO}.{ESQUEMA} + vista incidencias_lab (corte {CORTE}, {n_p1} P1 abiertas)")

# COMMAND ----------

# MAGIC %md ## Paso 3 – SQL Warehouse

# COMMAND ----------

paso(3, "SQL Warehouse")
WAREHOUSE_ID = config_leer("warehouse_id")
almacenes = {x["id"]: x for x in api("GET", "/api/2.0/sql/warehouses").get("warehouses", [])}
if WAREHOUSE_ID not in almacenes:
    wh = next((x for x in almacenes.values() if x["name"] == NOMBRE_WAREHOUSE), None)
    if wh is None:
        try:
            wh = api("POST", "/api/2.0/sql/warehouses", {
                "name": NOMBRE_WAREHOUSE, "cluster_size": "2X-Small", "min_num_clusters": 1, "max_num_clusters": 2,
                "auto_stop_mins": 15, "enable_serverless_compute": True, "warehouse_type": "PRO",
                "tags": {"custom_tags": [{"key": "proyecto", "value": "taller-la-tinka"}]}})
        except Exception as e:
            raise ErrorSetup(f"No pude crear el SQL Warehouse serverless. Verifica que serverless esté habilitado.\nDetalle: {e}")
    WAREHOUSE_ID = wh["id"]
    config_guardar("warehouse_id", WAREHOUSE_ID)
verificar("SQL Warehouse", "listo", WAREHOUSE_ID)

# COMMAND ----------

# MAGIC %md ## Paso 4 – Espacio de Genie "Mesa de servicio"

# COMMAND ----------

paso(4, "Espacio de Genie")


def genie_existe(space_id):
    try:
        return bool(space_id) and bool(api("GET", f"/api/2.0/genie/spaces/{space_id}").get("space_id"))
    except Exception:
        return False


GENIE_ID = next((g for g in [GENIE_WIDGET, config_leer("genie_id")] if genie_existe(g)), None)
if GENIE_ID:
    ok(f"Reutilizo el Genie {GENIE_ID}")
else:
    carpeta_genie = f"/Workspace/Users/{YO}/{CARPETA_LAB}"
    w.workspace.mkdirs(carpeta_genie)
    GENIE_ID = api("POST", "/api/2.0/genie/spaces", {
        "serialized_space": genie.construir(CATALOGO, ESQUEMA, FECHA_DATOS), "warehouse_id": WAREHOUSE_ID,
        "title": NOMBRE_GENIE, "description": genie.DESCRIPCION, "parent_path": carpeta_genie})["space_id"]
    ok("Espacio creado")
config_guardar("genie_id", GENIE_ID)
verificar("Genie", "listo", f"{NOMBRE_GENIE} ({GENIE_ID})")

# COMMAND ----------

# MAGIC %md ## Paso 5 – Modelo, MCP gestionados y tablas de sistema

# COMMAND ----------

paso(5, "Modelo, MCP gestionados y tablas de sistema")
MODELO = None
for m in MODELOS:
    try:
        api("GET", f"/api/2.1/unity-catalog/model-services/system.ai.{m}")
        api("POST", f"/serving-endpoints/databricks-{m}/invocations",
            {"messages": [{"role": "user", "content": "Responde solo: ok"}], "max_tokens": 5})
        MODELO = m
        break
    except Exception:
        continue
if MODELO is None:
    raise ErrorSetup(f"Ningún modelo está disponible en Unity Gateway. Probé: {', '.join(MODELOS)}.")
config_guardar("lab_modelo", MODELO)


def modelo_uc(m):
    """Nombre del modelo en system.ai (destino de un model service): databricks-<m> o <m>."""
    for candidato in (f"databricks-{m}", m):
        try:
            w.registered_models.get(f"system.ai.{candidato}")
            return candidato
        except Exception:
            continue
    return None


MODELO_UC = modelo_uc(MODELO)
RESPALDO_UC = next((r for r in (modelo_uc(m) for m in MODELOS if m != MODELO) if r), MODELO_UC)
verificar("Modelo", "listo", f"system.ai.{MODELO} (endpoint databricks-{MODELO}; respaldo {RESPALDO_UC})")


def mcp_tools(ruta):
    r = api("POST", ruta, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    return [t["name"] for t in r.get("result", {}).get("tools", [])]


for nombre, ruta in [("MCP Databricks SQL", "/api/2.0/mcp/sql"),
                     ("MCP Genie", f"/api/2.0/mcp/genie/{GENIE_ID}"),
                     ("MCP UC functions", f"/api/2.0/mcp/functions/system/ai")]:
    try:
        verificar(nombre, "listo", ", ".join(mcp_tools(ruta))[:90] or "sin tools (normal en system.ai)")
    except Exception as e:
        verificar(nombre, "falta", f"Activa el preview 'Managed MCP Servers'. Detalle: {str(e)[:120]}")

try:
    spark.sql("SELECT 1 FROM system.ai_gateway.usage LIMIT 1").collect()
    verificar("system.ai_gateway.usage", "listo", "consultable")
except Exception as e:
    verificar("system.ai_gateway.usage", "falta", f"Habilita el schema de sistema ai_gateway. Detalle: {str(e)[:120]}")

try:
    api("GET", "/api/2.0/agents/memory-stores", query={"page_size": 1})
    api("GET", "/api/2.0/agents/session-stores", query={"page_size": 1})
    verificar("Memoria y sesiones de agentes (Agent Bricks)", "listo", "APIs de memory stores y session stores disponibles")
except Exception as e:
    verificar("Memoria y sesiones de agentes (Agent Bricks)", "falta",
              f"Activa el preview 'Agent Memory Sessions' (Lab 3: memoria e historial del agente). Detalle: {str(e)[:120]}")

# COMMAND ----------

# MAGIC %md ## Paso 6 – Permisos del grupo

# COMMAND ----------

paso(6, "Permisos del grupo")
for sentencia in [
    f"GRANT USE CATALOG, CREATE SCHEMA ON CATALOG `{CATALOGO}` TO `{GRUPO}`",
    f"GRANT USE SCHEMA, SELECT, EXECUTE, READ VOLUME ON SCHEMA {T} TO `{GRUPO}`",
]:
    spark.sql(sentencia)
ok(f"USE CATALOG + CREATE SCHEMA en {CATALOGO}; lectura en {ESQUEMA}")

api("PATCH", f"/api/2.0/permissions/genie/{GENIE_ID}",
    {"access_control_list": [{"group_name": GRUPO, "permission_level": "CAN_RUN"}]})
api("PATCH", f"/api/2.0/permissions/warehouses/{WAREHOUSE_ID}",
    {"access_control_list": [{"group_name": GRUPO, "permission_level": "CAN_USE"}]})
ok("Genie (CAN RUN) y warehouse (CAN USE)")

# Los model services de system.ai suelen tener EXECUTE para todos; si no, lo damos al grupo.
try:
    spark.sql(f"GRANT EXECUTE ON MODEL SERVICE system.ai.`{MODELO}` TO `{GRUPO}`")
    ok(f"EXECUTE en system.ai.{MODELO}")
except Exception:
    ok(f"EXECUTE en system.ai.{MODELO}: se hereda del default del workspace")

# COMMAND ----------

# MAGIC %md ## Paso 7 – Espacio de cada participante
# MAGIC
# MAGIC Para cada persona del grupo: su schema `ag_<usuario>` (es dueña) y una copia de los notebooks en
# MAGIC `/Workspace/Users/<correo>/Lab Agentes La Tinka`. Quien llegue sin estar en el grupo puede usar la copia de
# MAGIC `/Workspace/Shared/Lab Agentes La Tinka`: el primer notebook le crea su schema.

# COMMAND ----------

paso(7, "Espacio de cada participante")
CONFIG_LAB = {"catalogo": CATALOGO, "esquema_datos": ESQUEMA, "genie_id": GENIE_ID, "warehouse_id": WAREHOUSE_ID,
              "modelo": MODELO, "modelo_uc": MODELO_UC, "modelo_respaldo_uc": RESPALDO_UC,
              "fecha_corte": CORTE, "grupo": GRUPO}
config_py = ("# Generado por setup/00_setup_lab. No lo edites a mano: vuelve a correr el setup.\n"
             f"CONFIG_LAB = {json.dumps(CONFIG_LAB, ensure_ascii=False, indent=2)}\n")


def copiar_arbol(origen, destino):
    """Copia una carpeta del workspace (notebooks y archivos) preservando el tipo de cada objeto."""
    w.workspace.mkdirs(destino)
    for obj in w.workspace.list(origen):
        nombre = obj.path.rsplit("/", 1)[-1]
        if nombre.startswith(".") or nombre == "__pycache__":
            continue
        if obj.object_type == ObjectType.DIRECTORY:
            copiar_arbol(obj.path, f"{destino}/{nombre}")
        elif obj.object_type == ObjectType.NOTEBOOK:
            contenido = w.workspace.export(obj.path, format=ExportFormat.SOURCE).content
            w.workspace.import_(f"{destino}/{nombre}", content=contenido, format=ImportFormat.SOURCE,
                                language=obj.language, overwrite=True)
        elif obj.object_type == ObjectType.FILE:
            contenido = w.workspace.export(obj.path, format=ExportFormat.AUTO).content
            w.workspace.import_(f"{destino}/{nombre}", content=contenido, format=ImportFormat.AUTO, overwrite=True)


def escribir_config(destino):
    import base64
    w.workspace.import_(f"{destino}/Includes/_config.py", content=base64.b64encode(config_py.encode()).decode(),
                        format=ImportFormat.AUTO, overwrite=True)


ORIGEN_LABS = f"{RAIZ_REPO_WS}/labs"
destinos = [f"/Workspace/Shared/{CARPETA_LAB}"]
if COPIAR:
    destinos += [f"/Workspace/Users/{u}/{CARPETA_LAB}" for u in PARTICIPANTES]
for destino in destinos:
    copiar_arbol(ORIGEN_LABS, destino)
    escribir_config(destino)
escribir_config(ORIGEN_LABS)
api("PATCH", "/api/2.0/permissions/directories/" +
    str(w.workspace.get_status(f"/Workspace/Shared/{CARPETA_LAB}").object_id),
    {"access_control_list": [{"group_name": GRUPO, "permission_level": "CAN_READ"}]})
ok(f"Notebooks copiados a {len(destinos)} carpetas")

for u in PARTICIPANTES:
    esquema_u = f"`{CATALOGO}`.`ag_{slug(u)}`"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {esquema_u} COMMENT 'Espacio de {u} en el lab de agentes'")
    spark.sql(f"ALTER SCHEMA {esquema_u} OWNER TO `{u}`")
ok(f"{len(PARTICIPANTES)} schemas ag_<usuario> listos (cada participante es dueño del suyo)")
verificar("Participantes", "listo", f"{len(PARTICIPANTES)} personas con schema y notebooks")

config_guardar("lab_grupo", GRUPO)

# COMMAND ----------

# MAGIC %md ## Resumen

# COMMAND ----------

filas = "".join(
    f"<tr><td>{c}</td><td style='color:{'#00A972' if e == 'listo' else '#FF3621'};font-weight:700'>"
    f"{'✓ listo' if e == 'listo' else '⚠ ' + e}</td><td>{d}</td></tr>" for c, e, d in VERIFICACION)
displayHTML(f"""
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#1B3139">
<h2 style="margin:0 0 8px">Laboratorio de agentes listo</h2>
<table style="border-collapse:collapse;font-size:14px">
<tr style="background:#F9F7F4"><th align=left style="padding:6px 12px">Componente</th><th align=left style="padding:6px 12px">Estado</th><th align=left style="padding:6px 12px">Detalle</th></tr>
{filas.replace('<td>', '<td style="padding:6px 12px;border-top:1px solid #ECEAE6">')}
</table>
<h3 style="margin:18px 0 6px">Revisa a mano en Settings → Previews (no se pueden validar por API)</h3>
<ul style="font-size:14px;line-height:1.6">
<li><b>Unity Gateway Service Policies</b> (Lab 4: guardrails de PII y jailbreak)</li>
<li><b>Databricks Sandbox</b> (Lab 3: el agente ejecuta código)</li>
<li><b>Managed MCP Servers</b> (Labs 1–3) y, para el módulo opcional, <b>Unity Gateway skills</b></li>
<li><b>Agent Memory Sessions</b> (Lab 3: memoria e historial del agente; arriba se valida por API)</li>
</ul>
<p style="font-size:14px">Genie: <a href="{HOST}/genie/rooms/{GENIE_ID}" target="_blank">{NOMBRE_GENIE}</a> ·
Notebooks: <code>/Workspace/Users/&lt;correo&gt;/{CARPETA_LAB}</code> (o <code>/Workspace/Shared/{CARPETA_LAB}</code>)</p>
<p style="font-size:14px"><b>Siguiente paso:</b> ensaya los labs con un usuario <b>no admin</b> del grupo.</p>
</div>""")
