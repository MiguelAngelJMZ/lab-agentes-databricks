# Databricks notebook source
# MAGIC %md
# MAGIC # Limpiar mis recursos del laboratorio
# MAGIC #### Duración: 2 minutos

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## Panorama
# MAGIC
# MAGIC Este notebook borra **solo lo que tú construiste** durante el laboratorio, para que puedas volver a practicarlo desde cero. Lo corres tú, con tu usuario: no puede tocar recursos de otras personas.
# MAGIC
# MAGIC | Se borra | Cómo se comprueba que es tuyo y del lab |
# MAGIC |---|---|
# MAGIC | Tu agente `agent-bricks-ag-<usuario>` (Lab 3) | Su código está en tu `agentbricks_deployments/` y su `agent.toml` usa tu schema del lab |
# MAGIC | Sus stores de memoria y sesiones y su experimento de trazas | Solo los nombres **exactos** que declara ese `agent.toml` |
# MAGIC | Su Runtime Store | `agent-bricks-ag-<usuario>`, si tu agente es del lab o si su app ya no existe (huérfano: bloquearía tu próximo deploy) |
# MAGIC | Tu servidor MCP `mcp-<usuario>` (Lab 2) | Su código está en `lab-agentes/mcp-server` o tiene la descripción que le pone el Lab 2 |
# MAGIC | Tu schema `ag_<usuario>` con lo que creaste (funciones, model service) | Tiene el comentario que le pone el lab ("Espacio de … en el lab de agentes") |
# MAGIC | Tu carpeta de trabajo `lab-agentes` (servidor MCP y proyecto del agente) | Solo las subcarpetas del lab; la carpeta solo si queda vacía |
# MAGIC | Tu experimento de trazas `lab-agentes-trazas` (Labs 1 y 5) | Su ruta exacta: `/Users/<tu correo>/lab-agentes-trazas` |
# MAGIC
# MAGIC **No se borra:** esta carpeta con los notebooks del lab, los datos de `mesa_servicio`, el Genie, el warehouse ni nada de otras personas. Lo que no pase la comprobación aparece en la lista de **omitidos** con el motivo.
# MAGIC
# MAGIC Para volver a practicar, cuando termine empieza otra vez por `00 - Kickoff`: los labs recrean tu schema y tus apps.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### Cómo usarlo
# MAGIC
# MAGIC 1. Corre todo con el modo **simular** (el valor por defecto): verás qué se borraría, sin borrar nada.
# MAGIC 2. Revisa la lista. Si está bien, cambia el widget **Modo** a **borrar** y vuelve a correr todo.
# MAGIC
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #FF3621; border-radius:10px; background:#FFF5F3; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#FF3621;">No se puede deshacer</strong><br>Las apps, los stores y el schema se borran de forma definitiva. Si dentro de tu schema <code>ag_&lt;usuario&gt;</code> creaste tablas propias que quieras conservar, cópialas antes.
# MAGIC </div>

# COMMAND ----------

dbutils.widgets.dropdown("modo", "simular", ["simular", "borrar"], "Modo")
BORRAR = dbutils.widgets.get("modo") == "borrar"

# COMMAND ----------

# MAGIC %run ./Includes/Setup-Lab

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## A. Qué se borraría
# MAGIC <script>
# MAGIC (function() {
# MAGIC   var TEXT='DEMO', ACCENT='#2E7D32';
# MAGIC   var base='display:inline-block; border-radius:4px; padding:3px 10px; font-size:11px; font-weight:700; letter-spacing:0.06em; margin-left:10px; vertical-align:middle;';
# MAGIC   var el=document.currentScript, h=null;
# MAGIC   while (el && !h) { h = el.querySelector ? el.querySelector('h1,h2,h3,h4,h5,h6') : null; if (!h) el=el.parentElement; }
# MAGIC   if (!h || h.querySelector('[data-pill]')) return;
# MAGIC   var span=document.createElement('span');
# MAGIC   span.setAttribute('data-pill','1');
# MAGIC   span.style.cssText=base+'background:'+ACCENT+'; color:#ffffff;';
# MAGIC   span.textContent=TEXT;
# MAGIC   h.appendChild(span);
# MAGIC })();
# MAGIC </script>

# COMMAND ----------

import tomllib

DESCRIPCION_MCP = "MCP de la mesa de servicio (lab de agentes)"  # la pone el Lab 2 al crear la app
CASA = f"/Workspace/Users/{YO}"
DESPLIEGUE = f"{CASA}/agentbricks_deployments/{AGENTE_APP}"
TRABAJO = f"{CASA}/lab-agentes"
MARCA = f"{CATALOGO}.{MI_ESQUEMA}."  # tu schema del lab, tal como aparece en tu agent.toml


def existe(ruta):
    try:
        w.workspace.get_status(ruta)
        return True
    except Exception:
        return False


def leer(ruta):
    try:
        return w.workspace.download(ruta).read().decode("utf-8")
    except Exception:
        return None


def hijos(ruta):
    """Contenido de una carpeta, o None si no se pudo listar (entonces no se borra)."""
    try:
        return [o.path for o in w.workspace.list(ruta)]
    except Exception:
        return None


def mis_stores():
    """Memory y session stores visibles para ti, paginados de a 100 (el máximo de la API)."""
    nombres = {}
    for tipo in ("memory-stores", "session-stores"):
        token = None
        try:
            while True:
                r = w.api_client.do("GET", f"/api/2.0/agents/{tipo}",
                                    query={"page_size": 100, **({"page_token": token} if token else {})})
                for st in next((v for v in r.values() if isinstance(v, list)), []):
                    nombres[st.get("display_name") or st["name"].split("/", 1)[1]] = st["name"]
                token = r.get("next_page_token")
                if not token:
                    break
        except Exception as e:
            print(f"⚠ No pude listar {tipo}: {str(e)[:120]}")
    return nombres


def runtime_store(app_name):
    """El Runtime Store que agentbricks deploy crea para tu app (o None). Si se borra la app sin él, queda huérfano
    y el siguiente deploy falla con "Runtime Store ... does not belong to this app identity"."""
    try:
        st = w.api_client.do("GET", f"/api/2.0/agents/runtime-stores/{app_name}")
        return st if ((st.get("owner") or {}).get("app") or {}).get("name") == app_name else None
    except Exception:
        return None


def ruta_codigo(app):
    d = getattr(app, "active_deployment", None) or getattr(app, "pending_deployment", None)
    return (d.source_code_path if d else None) or app.default_source_code_path


def app_o_nada(nombre):
    try:
        return w.apps.get(nombre)
    except Exception:
        return None


PLAN, OMITIDOS = [], []

# 1. Agente (Lab 3): el agent.toml del despliegue, o el del proyecto de 03B, dice qué recursos son suyos.
toml_txt = leer(f"{DESPLIEGUE}/agent.toml") or leer(f"{TRABAJO}/{AGENTE}/agent.toml")
es_del_lab = bool(toml_txt) and MARCA in toml_txt
agente = app_o_nada(AGENTE_APP)
# Runtime Store: se borra antes que la app (como hace el CLI) si tu agente es del lab o si su app ya no existe.
if runtime_store(AGENTE_APP):
    if es_del_lab or not agente:
        PLAN.append((f"runtime store {AGENTE_APP}" + ("" if es_del_lab else " (huérfano: su app ya no existe)"),
                     lambda: w.api_client.do("DELETE", f"/api/2.0/agents/runtime-stores/{AGENTE_APP}")))
    else:
        OMITIDOS.append((f"runtime store {AGENTE_APP}", "su app existe y no es la del lab"))
if agente:
    if es_del_lab and ruta_codigo(agente) == DESPLIEGUE:
        PLAN.append((f"app {AGENTE_APP}", lambda: w.apps.delete(AGENTE_APP)))
    else:
        OMITIDOS.append((f"app {AGENTE_APP}", "su código o su agent.toml no son los del lab"))
if es_del_lab:
    cfg, stores = tomllib.loads(toml_txt), mis_stores()
    for clave in ("memory_store", "session_store"):
        nombre = cfg.get(clave, {}).get("name")
        if nombre in stores:
            PLAN.append((f"store {nombre}", lambda r=stores[nombre]: w.api_client.do("DELETE", f"/api/2.0/agents/{r}")))
    experimento = cfg.get("tracing", {}).get("experiment_name")
    if experimento and experimento.startswith(f"/Shared/agentbricks_traces/{AGENTE}-") and existe(experimento):
        exp = w.experiments.get_by_name(experimento).experiment
        PLAN.append((f"experimento {experimento}", lambda i=exp.experiment_id: w.experiments.delete_experiment(i)))
    if existe(DESPLIEGUE):
        PLAN.append((f"carpeta {DESPLIEGUE}", lambda: w.workspace.delete(DESPLIEGUE, recursive=True)))
elif existe(DESPLIEGUE):
    OMITIDOS.append((f"carpeta {DESPLIEGUE}", "su agent.toml no usa tu schema del lab"))

# 2. Servidor MCP (Lab 2)
mcp = app_o_nada(MCP_APP)
if mcp:
    if ruta_codigo(mcp) == CARPETA_MCP or (mcp.description or "") == DESCRIPCION_MCP:
        PLAN.append((f"app {MCP_APP}", lambda: w.apps.delete(MCP_APP)))
    else:
        OMITIDOS.append((f"app {MCP_APP}", "no la creó el Lab 2 (código y descripción distintos)"))

# 3. Tu schema (Labs 1 y 4)
if MI_ESQUEMA == ESQUEMA_DATOS or not MI_ESQUEMA.startswith("ag_"):
    OMITIDOS.append((f"schema {CATALOGO}.{MI_ESQUEMA}", "nombre protegido"))
else:
    comentario = w.schemas.get(f"{CATALOGO}.{MI_ESQUEMA}").comment or ""
    if comentario.startswith("Espacio de ") and comentario.endswith("en el lab de agentes"):
        funciones = [f.name for f in w.functions.list(CATALOGO, MI_ESQUEMA)]
        tablas = [t.name for t in w.tables.list(CATALOGO, MI_ESQUEMA)]
        detalle = ", ".join(funciones + tablas)[:100] or "vacío"
        PLAN.append((f"schema {CATALOGO}.{MI_ESQUEMA} con su contenido ({detalle})",
                     lambda: spark.sql(f"DROP SCHEMA IF EXISTS `{CATALOGO}`.`{MI_ESQUEMA}` CASCADE")))
    else:
        OMITIDOS.append((f"schema {CATALOGO}.{MI_ESQUEMA}", f"no tiene el comentario del lab ({comentario[:60]!r})"))

# 4. Tu experimento de trazas del lab (Labs 1 y 5)
if existe(EXPERIMENTO_LAB):
    exp_lab = w.experiments.get_by_name(EXPERIMENTO_LAB).experiment
    PLAN.append((f"experimento {EXPERIMENTO_LAB}", lambda i=exp_lab.experiment_id: w.experiments.delete_experiment(i)))

# 5. Tu carpeta de trabajo: solo las subcarpetas del lab; la carpeta, si queda vacía
if existe(TRABAJO):
    del_lab = []
    if existe(CARPETA_MCP) and "mcp-mesa-servicio" in (leer(f"{CARPETA_MCP}/server/tools.py") or ""):
        del_lab.append(CARPETA_MCP)
    if existe(f"{TRABAJO}/{AGENTE}") and MARCA in (leer(f"{TRABAJO}/{AGENTE}/agent.toml") or ""):
        del_lab.append(f"{TRABAJO}/{AGENTE}")
    for c in del_lab:
        PLAN.append((f"carpeta {c}", lambda c=c: w.workspace.delete(c, recursive=True)))
    contenido = hijos(TRABAJO)
    resto = None if contenido is None else [h for h in contenido if h not in del_lab]
    if resto is None:
        OMITIDOS.append((f"carpeta {TRABAJO}", "no pude listar su contenido"))
    elif resto:
        OMITIDOS.append((f"carpeta {TRABAJO}", f"tiene otro contenido: {', '.join(h.rsplit('/', 1)[-1] for h in resto)[:120]}"))
    else:
        PLAN.append((f"carpeta {TRABAJO} (queda vacía)", lambda: w.workspace.delete(TRABAJO, recursive=True)))

filas = "".join(f"<tr><td style='padding:3px 10px'><code>{r}</code></td></tr>" for r, _ in PLAN) \
        or "<tr><td style='padding:3px 10px'>No encontré recursos tuyos del laboratorio.</td></tr>"
filas_om = "".join(f"<tr><td style='padding:3px 10px'><code>{r}</code></td><td style='padding:3px 10px'>{m}</td></tr>" for r, m in OMITIDOS)
displayHTML(f"""<div style="font-family:-apple-system,Segoe UI,sans-serif;font-size:14px;color:#1B3139">
<h3 style="margin:0 0 6px">{'Se va a borrar' if BORRAR else 'Se borraría'} ({len(PLAN)})</h3><table>{filas}</table>
{f'<h3 style="margin:16px 0 6px;color:#B26B00">Omitidos: no se tocan ({len(OMITIDOS)})</h3><table>{filas_om}</table>' if OMITIDOS else ''}
</div>""")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## B. Borrar
# MAGIC <script>
# MAGIC (function() {
# MAGIC   var TEXT='DEMO', ACCENT='#2E7D32';
# MAGIC   var base='display:inline-block; border-radius:4px; padding:3px 10px; font-size:11px; font-weight:700; letter-spacing:0.06em; margin-left:10px; vertical-align:middle;';
# MAGIC   var el=document.currentScript, h=null;
# MAGIC   while (el && !h) { h = el.querySelector ? el.querySelector('h1,h2,h3,h4,h5,h6') : null; if (!h) el=el.parentElement; }
# MAGIC   if (!h || h.querySelector('[data-pill]')) return;
# MAGIC   var span=document.createElement('span');
# MAGIC   span.setAttribute('data-pill','1');
# MAGIC   span.style.cssText=base+'background:'+ACCENT+'; color:#ffffff;';
# MAGIC   span.textContent=TEXT;
# MAGIC   h.appendChild(span);
# MAGIC })();
# MAGIC </script>
# MAGIC
# MAGIC Solo borra si el widget **Modo** está en **borrar**.

# COMMAND ----------

if not BORRAR:
    print("Modo simular: no se borró nada. Si la lista de arriba está bien, cambia 'Modo' a 'borrar' y vuelve a correr todo.")
else:
    errores = 0
    for recurso, funcion in PLAN:
        try:
            funcion()
            print(f"🗑  {recurso}")
        except Exception as e:
            errores += 1
            print(f"⚠  {recurso} → {str(e)[:160]}")
    print(f"\n✓ Listo: {len(PLAN) - errores} borrados, {errores} con error, {len(OMITIDOS)} omitidos. "
          "Para volver a practicar, empieza por 00 - Kickoff.")
