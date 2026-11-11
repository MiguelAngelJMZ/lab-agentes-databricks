# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 3 (versión A) · Agente custom con Agent Bricks CLI
# MAGIC #### Duración: 50 minutos

# COMMAND ----------

# MAGIC %md
# MAGIC ## Panorama
# MAGIC
# MAGIC Ahora juntas todo en **un agente desplegado**. Usas el **Agent Bricks CLI** desde tu laptop: pasas de una carpeta vacía a un agente en Databricks con tools, sandbox, memoria, sesiones y trazas, sin escribir infraestructura.
# MAGIC
# MAGIC Tu agente tendrá cinco fuentes:
# MAGIC
# MAGIC | Tool | De dónde viene | Cómo se agrega |
# MAGIC |---|---|---|
# MAGIC | `incidencias_abiertas` | Tu UC function (Lab 1) | `agentbricks tools add uc-function` |
# MAGIC | Genie "Mesa de servicio" | Genie Agent | `agentbricks tools add genie-agent` |
# MAGIC | `run_code` | Databricks Sandbox | `agentbricks tools add sandbox` |
# MAGIC | `calcular_sla`, `estado_plataforma_juego` | Tu MCP en Apps (Lab 2) | por código: `agent/mcps.py` |
# MAGIC | `remember`, `recall` | Memoria de largo plazo | viene en la plantilla |
# MAGIC
# MAGIC **Este notebook es tu guía:** genera los comandos exactos para tu usuario, da los permisos que tu agente necesita y te muestra sus trazas y su memoria. Los comandos se corren en la **terminal de tu laptop**.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Objetivos de aprendizaje
# MAGIC
# MAGIC - **Describir** qué declara `agent.toml` (tools, memoria, sesiones, tracing, model service) y qué crea `agentbricks deploy`.
# MAGIC - **Crear** un agente LangGraph con `agentbricks init` y **agregarle** tools gestionadas con `agentbricks tools add`.
# MAGIC - **Conectar** tu MCP de Databricks Apps por código y **dar** al agente el permiso `CAN USE` sobre él.
# MAGIC - **Probar** el agente en local con `agentbricks dev` y **desplegarlo** con `agentbricks deploy`.
# MAGIC - **Leer** una traza en MLflow y **demostrar** que el agente recuerda una preferencia entre sesiones.

# COMMAND ----------

# MAGIC %pip install -q "mlflow>=3.5"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./Includes/Setup-Lab

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Agent Bricks en una página

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### A.1 `agent.toml`, la fuente de verdad
# MAGIC <script>
# MAGIC (function() {
# MAGIC   var TEXT='LECTURA', ACCENT='#5A6F77';
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
# MAGIC Cada comando del CLI escribe en `agent.toml`; `dev` y `deploy` lo leen para conectar todo. Así queda el tuyo al terminar el lab:
# MAGIC
# MAGIC ```toml
# MAGIC [agent]
# MAGIC framework = "langgraph"
# MAGIC server = "agentbricks"            # DurableAgentServer: foreground, streaming y background
# MAGIC
# MAGIC [memory_store]                    # memoria de largo plazo (remember / recall)
# MAGIC name = "ag-<usuario>-xxxx-memory"
# MAGIC [session_store]                   # historial durable de cada conversación
# MAGIC name = "ag-<usuario>-xxxx-sessions"
# MAGIC [tracing]                         # MLflow Tracing
# MAGIC experiment_name = "/Shared/agentbricks_traces/ag-<usuario>-xxxx"
# MAGIC
# MAGIC [[tools]]                         # Lab 1
# MAGIC id = "incidencias_abiertas"
# MAGIC source = {kind = "uc_function", function = "la_tinka_taller.ag_<usuario>.incidencias_abiertas"}
# MAGIC [[tools]]                         # el Genie que ya conocen
# MAGIC id = "genie_agent"
# MAGIC source = {kind = "genie_agent", space_id = "<id>"}
# MAGIC [[tools]]                         # el agente ejecuta código
# MAGIC id = "sandbox"
# MAGIC source = {kind = "sandbox", service = "system.ai.sandbox"}
# MAGIC
# MAGIC [experimental.model_services.agent]   # Lab 4: el modelo pasa por TU model service
# MAGIC name = "la_tinka_taller.ag_<usuario>.modelo_agente"
# MAGIC default = "system.ai.claude-sonnet-4-5"
# MAGIC ```

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### A.2 Qué hace cada comando
# MAGIC <script>
# MAGIC (function() {
# MAGIC   var TEXT='LECTURA', ACCENT='#5A6F77';
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
# MAGIC <div style="display:flex; gap:12px; flex-wrap:wrap; margin:10px 0;">
# MAGIC   <div style="flex:1 1 170px; background:#fff; border:1px solid #ECEAE6; border-top:4px solid #2272B4; border-radius:12px; padding:12px 14px;"><h4 style="margin:0 0 6px;">init</h4><p style="font-size:13px; margin:0;">Crea el proyecto (LangGraph + chat UI), declara stores de memoria y sesiones y el experimento de trazas.</p></div>
# MAGIC   <div style="flex:1 1 170px; background:#fff; border:1px solid #ECEAE6; border-top:4px solid #FFAB00; border-radius:12px; padding:12px 14px;"><h4 style="margin:0 0 6px;">tools add</h4><p style="font-size:13px; margin:0;">Valida y declara una tool gestionada en <code>agent.toml</code>. Las tools propias en Python van en <code>agent/tools/</code>.</p></div>
# MAGIC   <div style="flex:1 1 170px; background:#fff; border:1px solid #ECEAE6; border-top:4px solid #00A972; border-radius:12px; padding:12px 14px;"><h4 style="margin:0 0 6px;">dev</h4><p style="font-size:13px; margin:0;">Corre el agente en tu laptop con el mismo runtime de Databricks. Trazas en un MLflow local; memoria apagada.</p></div>
# MAGIC   <div style="flex:1 1 170px; background:#fff; border:1px solid #ECEAE6; border-top:4px solid #FF3621; border-radius:12px; padding:12px 14px;"><h4 style="margin:0 0 6px;">deploy</h4><p style="font-size:13px; margin:0;">Sube el código como app <code>agent-bricks-&lt;nombre&gt;</code>, crea los stores, el model service y los permisos del service principal. ≈ 4 min la primera vez, ≈ 35 s después.</p></div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Construir el agente en tu laptop

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### B.1 Tus comandos
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
# MAGIC Esta celda arma los comandos con **tus** nombres. Cópialos a tu terminal **en orden**. Antes, en la celda B.2 verás la URL de tu MCP del Lab 2.

# COMMAND ----------

try:
    URL_MCP_PROPIO = w.apps.get(MCP_APP).url
except Exception:
    URL_MCP_PROPIO = "<URL de tu app MCP del Lab 2>"
    print("⚠ No encuentro tu app del Lab 2. Termina el Lab 2 o pide al instructor la URL del MCP compartido.")

PERFIL = "<perfil>"  # el que creaste en el kickoff con `databricks auth login`
comandos = f"""# 0. Una carpeta de trabajo
mkdir -p ~/lab-agentes && cd ~/lab-agentes

# 1. Scaffold: plantilla LangGraph con chat UI
agentbricks -p {PERFIL} init --framework langgraph {AGENTE}
cd {AGENTE}

# 2. Tools gestionadas
agentbricks -p {PERFIL} tools add uc-function {CATALOGO}.{MI_ESQUEMA}.incidencias_abiertas
agentbricks -p {PERFIL} tools add genie-agent {GENIE_ID}
agentbricks -p {PERFIL} tools add sandbox

# 3. El modelo pasa por tu model service (lo usarás en el Lab 4)
agentbricks -p {PERFIL} experimental models bind {MODELO_SERVICIO} --default {MODELO_SYSTEM}

# 4. Tu MCP del Lab 2 y el prompt en español (descarga el script desde la celda B.3)
python3 ~/Downloads/aplicar_referencia.py {URL_MCP_PROPIO}

# 5. Revisa lo que quedó declarado
cat agent.toml
"""
displayHTML(f"<pre style='background:#0B2026;color:#E6F5EE;padding:14px 16px;border-radius:10px;font-size:13px;line-height:1.5'>{comandos}</pre>")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### B.2 Qué hace `aplicar_referencia.py`
# MAGIC <script>
# MAGIC (function() {
# MAGIC   var TEXT='LECTURA', ACCENT='#5A6F77';
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
# MAGIC La plantilla trae `agent/mcps.py` vacío y un agente sin prompt de sistema. El script (está en `agente-referencia/` dentro de esta carpeta) hace tres cambios pequeños para el lab:
# MAGIC
# MAGIC 1. **`agent/mcps.py`**: conecta tu MCP del Lab 2 por URL. Unity Gateway no registra apps de Databricks Apps como MCP services, así que el agente se conecta directo (`<url>/mcp`) con la identidad de su service principal.
# MAGIC 2. **`agent/agent.py`**: agrega un `SYSTEM_PROMPT` en español que dice para qué sirve cada fuente y pide usar `recall` al inicio de cada conversación.
# MAGIC 3. **`app.yaml` y `.env`**: declaran `MCP_MESA_SERVICIO_URL` para el despliegue y para `agentbricks dev`.
# MAGIC
# MAGIC Ábrelo antes de correrlo: son 80 líneas y no hay magia.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### B.3 Descargar el script
# MAGIC <script>
# MAGIC (function() {
# MAGIC   var TEXT='UI', ACCENT='#2272B4';
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
# MAGIC En el navegador de archivos de la izquierda: carpeta **`agente-referencia`** → `aplicar_referencia.py` → menú **⋮** → **Download**. Queda en `~/Downloads/`.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## C. Probar en local
# MAGIC
# MAGIC Desde la carpeta del agente:
# MAGIC
# MAGIC ```bash
# MAGIC agentbricks -p <perfil> dev
# MAGIC ```
# MAGIC
# MAGIC Abre `http://localhost:8000` y pregunta:
# MAGIC
# MAGIC > *¿Cuántas P1 llevan más de 24 horas abiertas, qué equipos concentran más y cuál es el estado de SLA de la más antigua?*
# MAGIC
# MAGIC Deberías ver tres tools en cadena: `incidencias_abiertas` → `run_code` (sandbox) → `calcular_sla` (tu MCP). Las trazas locales quedan en la URL **Traces** que imprime `dev`.
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">En dev la memoria está apagada</strong><br><code>agentbricks dev</code> corre con la memoria de largo plazo apagada y el historial en memoria del proceso. La memoria real aparece al desplegar.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## D. Desplegar

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### D.1 `deploy`
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
# MAGIC ```bash
# MAGIC agentbricks -p <perfil> deploy <nombre de tu agente, celda B.1>
# MAGIC ```
# MAGIC
# MAGIC El CLI crea la app `agent-bricks-<nombre>`, los stores de memoria y sesiones, tu model service `modelo_agente` y los permisos del service principal del agente. La primera vez tarda ≈ 4 minutos.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### D.2 Dar acceso a tu MCP
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
# MAGIC Tu agente llama al MCP del Lab 2 con **su propia identidad** (el service principal de la app). Esa identidad necesita `CAN USE` sobre la app del MCP. Corre esta celda **después** de que termine el deploy.

# COMMAND ----------

from databricks.sdk.service.apps import AppAccessControlRequest, AppPermissionLevel

app_agente = w.apps.get(AGENTE_APP)
sp_agente = app_agente.service_principal_client_id
w.apps.update_permissions(MCP_APP, access_control_list=[
    AppAccessControlRequest(service_principal_name=sp_agente, permission_level=AppPermissionLevel.CAN_USE)])
print(f"✓ {AGENTE_APP} (service principal {sp_agente}) puede usar {MCP_APP}")
displayHTML(f"<div style='font-size:15px'>Abre tu agente: <a href='{app_agente.url}' target='_blank'>{app_agente.url}</a></div>")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### D.3 La pregunta combinada
# MAGIC <script>
# MAGIC (function() {
# MAGIC   var TEXT='UI', ACCENT='#2272B4';
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
# MAGIC En el chat de tu agente desplegado, repite la pregunta de la sección C. Compara: ahora la llamada a la UC function y a Genie sale **con tu identidad** (`auth = "user"` en `agent.toml`) y la del MCP con la del agente.

# COMMAND ----------

# MAGIC %md
# MAGIC ## E. Leer la traza en MLflow
# MAGIC
# MAGIC Cada conversación queda como una traza en el experimento declarado en `[tracing]`.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### E.1 Tus últimas trazas
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

import mlflow

mlflow.set_tracking_uri("databricks")
experimentos = [e for e in mlflow.search_experiments(filter_string=f"name LIKE '/Shared/agentbricks_traces/{AGENTE}-%'")]
if not experimentos:
    print("Todavía no hay experimento: despliega el agente y hazle una pregunta.")
else:
    exp = experimentos[0]
    orden = dict(max_results=5, order_by=["timestamp_ms DESC"])
    try:
        trazas = mlflow.search_traces(locations=[exp.experiment_id], include_spans=False, **orden)
    except TypeError:  # MLflow anterior a 3.5
        trazas = mlflow.search_traces(experiment_ids=[exp.experiment_id], **orden)
    print(f"Experimento: {exp.name}")
    if len(trazas):
        display(trazas[[c for c in ["trace_id", "request_time", "execution_duration", "state", "request_preview"] if c in trazas.columns]])
    else:
        print("El experimento existe pero aún no tiene trazas: hazle una pregunta al agente desplegado.")
    displayHTML(f"<a href='{HOST}/ml/experiments/{exp.experiment_id}/traces' target='_blank'>Abrir las trazas en MLflow</a>")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### E.2 Qué mirar en una traza
# MAGIC <script>
# MAGIC (function() {
# MAGIC   var TEXT='UI', ACCENT='#2272B4';
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
# MAGIC Abre la traza de la pregunta combinada y recorre: **qué tool eligió** el LLM en cada paso, **con qué argumentos**, la **latencia** de cada span y los **tokens** de cada llamada al modelo. Busca el span de `run_code`: verás el código Python que escribió el agente.

# COMMAND ----------

# MAGIC %md
# MAGIC ## F. Reto: que el agente recuerde una preferencia
# MAGIC
# MAGIC Demuestra que tu agente recuerda una preferencia **entre conversaciones distintas**.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### F.1 Dos conversaciones
# MAGIC <script>
# MAGIC (function() {
# MAGIC   var TEXT='RETO', ACCENT='#FF3621';
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
# MAGIC 1. En el chat del agente desplegado escribe: *"Recuerda esto: prefiero las respuestas en una tabla y sin emojis."* → el agente llama `remember`.
# MAGIC 2. Abre una **conversación nueva** (botón *New chat*) y pregunta: *"¿Qué equipos tienen más P1 abiertas?"*
# MAGIC 3. Debe llamar `recall` al inicio y responder **en una tabla, sin emojis**.
# MAGIC
# MAGIC La memoria se guarda por **actor**: el chat usa tu identidad, así que la preferencia es tuya y no la ven tus compañeros.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### F.2 Lo que quedó en la memoria
# MAGIC <script>
# MAGIC (function() {
# MAGIC   var TEXT='UI', ACCENT='#2272B4';
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
# MAGIC En el chat del agente, abre la tarjeta **Memory** del panel lateral: muestra el store de tu agente y las entradas de **tu** actor (la UI resuelve el actor igual que el agente, a partir de tu identidad). Verás la entrada `/preferencias.md` que escribió `remember`. Puedes buscar, crear o borrar entradas desde ahí.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">Si te atoras</strong><br><code>agentbricks -p &lt;perfil&gt; deployments logs agent-bricks-&lt;nombre&gt;</code> muestra los logs del agente. Los errores más comunes: olvidar la celda D.2 (el MCP responde 401/403) o correr <code>aplicar_referencia.py</code> fuera de la carpeta del agente.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusión
# MAGIC
# MAGIC Desplegaste un agente custom en Databricks con cinco fuentes de herramientas, memoria de largo plazo, sesiones durables y trazas en MLflow, todo declarado en `agent.toml`. Viste dos identidades en juego: la tuya para los datos (UC function, Genie, sandbox) y la del agente para tu MCP.
# MAGIC
# MAGIC En el **Lab 4** pones ese agente bajo gobierno: su modelo ya pasa por **tu model service** (`modelo_agente`); le agregarás un rate limit, un guardrail de PII y verás cada llamada en `system.ai_gateway.usage`.
