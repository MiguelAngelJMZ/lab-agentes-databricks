# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 2 · Servidor MCP propio en Databricks Apps
# MAGIC #### Duración: 40 minutos

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## Panorama
# MAGIC
# MAGIC En el Lab 1 las tools eran SQL. Pero mucha lógica de negocio no vive en una tabla: reglas de escalamiento, cálculos, llamadas a APIs internas. Para eso construyes tu **propio servidor MCP** y lo hospedas en **Databricks Apps**: Databricks pone el cómputo, la URL HTTPS y la autenticación OAuth; tú escribes funciones Python.
# MAGIC
# MAGIC El servidor de este lab, **mcp-mesa-servicio**, parte de la plantilla oficial *MCP Server (Starter)* y trae tres tools de la mesa de servicio:
# MAGIC
# MAGIC | Tool | Qué hace |
# MAGIC |---|---|
# MAGIC | `calcular_sla(prioridad, horas_abierta)` | Estado de SLA (dentro / en riesgo / vencida), horas restantes y a quién escalar |
# MAGIC | `estado_plataforma_juego(juego)` | Simula una API interna de monitoreo de Tinka, Kábala, Ganadiario, Te Apuesto, Kinelo y Raspaditas |
# MAGIC | `usuario_actual()` | Devuelve quién llama: demuestra que el servidor recibe la identidad del usuario final |
# MAGIC
# MAGIC Secciones:
# MAGIC - **A. Por qué un MCP propio** y las tres formas de hospedarlo
# MAGIC - **B. Anatomía del servidor**: dónde se definen las tools y por qué el docstring importa
# MAGIC - **C. Desplegarlo** como app `mcp-<tu usuario>`
# MAGIC - **D. Probarlo** desde AI Playground
# MAGIC - **E. Reto**: agregar la tool `prioridad_sugerida` y redeployar

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### Objetivos de aprendizaje
# MAGIC
# MAGIC Al terminar este lab podrás:
# MAGIC - **Elegir** entre la plantilla Starter, la plantilla OpenAPI y un servidor existente para hospedar un MCP en Databricks Apps.
# MAGIC - **Leer** un servidor FastMCP y **escribir** una tool con un docstring que el LLM entienda.
# MAGIC - **Desplegar** y **redeployar** el servidor como app y obtener su URL MCP (`<url de la app>/mcp`).
# MAGIC - **Conectar** el MCP a AI Playground y llamar sus tools.
# MAGIC - **Explicar** cómo autentica una app MCP (OAuth, `CAN USE`, identidad del usuario final).

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="border: 1px solid #DCE0E2; border-radius: 12px; overflow: hidden; margin: 16px 0;">
# MAGIC   <div style="background: #FF3621; color: #fff; padding: 11px 18px;">
# MAGIC     <strong style="font-size: 13pt; letter-spacing: 0.05em; text-transform: uppercase;">Antes de empezar: elige el cómputo</strong>
# MAGIC   </div>
# MAGIC   <div style="background: #F9F7F4; padding: 18px 22px; color: #1B3139;">
# MAGIC     <ol style="margin: 0; padding-left: 22px; font-size: 13pt; line-height: 1.7;">
# MAGIC       <li><strong>Conecta Serverless</strong> en el menú <strong>Connect</strong>.</li>
# MAGIC       <li><strong>Corre las celdas en orden.</strong> Crear la app toma ≈ 2–3 minutos: lánzala y mientras tanto lee la sección B.</li>
# MAGIC     </ol>
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Setup del lab

# COMMAND ----------

# MAGIC %run ./Includes/Setup-Lab

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Por qué un MCP propio

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### A.1 Tres formas de hospedar un MCP en Databricks Apps
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
# MAGIC <div style="display:flex; gap:14px; flex-wrap:wrap; margin:10px 0;">
# MAGIC   <div style="flex:1 1 220px; background:#fff; border:1px solid #ECEAE6; border-top:4px solid #00A972; border-radius:12px; padding:14px 16px;">
# MAGIC     <h4 style="margin:0 0 6px;">Plantilla Starter</h4>
# MAGIC     <p style="font-size:14px; margin:0;">Escribes tools en Python (FastMCP). Trae una tool <code>health</code> para probar. <b>Es la que usamos hoy.</b></p>
# MAGIC   </div>
# MAGIC   <div style="flex:1 1 220px; background:#fff; border:1px solid #ECEAE6; border-top:4px solid #2272B4; border-radius:12px; padding:14px 16px;">
# MAGIC     <h4 style="margin:0 0 6px;">Plantilla OpenAPI</h4>
# MAGIC     <p style="font-size:14px; margin:0;">Ya tienes una API REST: subes su <code>spec.json</code> a un volumen y una conexión HTTP de UC guarda las credenciales. El MCP expone los endpoints como tools.</p>
# MAGIC   </div>
# MAGIC   <div style="flex:1 1 220px; background:#fff; border:1px solid #ECEAE6; border-top:4px solid #FFAB00; border-radius:12px; padding:14px 16px;">
# MAGIC     <h4 style="margin:0 0 6px;">Servidor existente</h4>
# MAGIC     <p style="font-size:14px; margin:0;">Cualquier servidor MCP con <i>Streamable HTTP</i> que escuche en <code>DATABRICKS_APP_PORT</code>, con su <code>app.yaml</code>.</p>
# MAGIC   </div>
# MAGIC </div>
# MAGIC
# MAGIC En la UI las tres empiezan igual: **Unity Gateway → MCPs → + MCP → Build a new MCP server**. El nombre de la app debe empezar con **`mcp-`** para que AI Playground la reconozca como servidor MCP.
# MAGIC
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #FF3621; border-radius:10px; background:#FFF5F3; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#FF3621;">Apps no se registran como MCP service</strong><br>Unity Gateway permite <b>registrar</b> MCP externos (de terceros o autohospedados fuera de Databricks) como securables de UC. Un MCP en Databricks Apps <b>no se registra</b>: los clientes se conectan directo a <code>&lt;url de la app&gt;/mcp</code> y el acceso se gobierna con los permisos de la app (<code>CAN USE</code>) y OAuth. Los tokens personales (PAT) no funcionan.
# MAGIC </div>
# MAGIC <p style="font-size:13px; color:#5A6F77;"><strong>Documentación:</strong> <a href="https://docs.databricks.com/aws/en/agents/mcp-tools/custom-mcp" target="_blank" style="color:#2272B4;">Host an MCP server on Databricks Apps</a></p>

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Anatomía del servidor

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### B.1 Los archivos
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
# MAGIC | Archivo | Para qué |
# MAGIC |---|---|
# MAGIC | `app.yaml` | Comando de arranque de la app: `uv run custom-mcp-server` |
# MAGIC | `pyproject.toml` | Dependencias (FastMCP, FastAPI, Databricks SDK) |
# MAGIC | `server/app.py` | Crea el servidor FastMCP en modo **stateless** y lo sirve en `/mcp` |
# MAGIC | `server/tools.py` | **Aquí viven las tools.** Es el único archivo que tocas en el reto |
# MAGIC | `server/utils.py` | Toma el token del usuario (`x-forwarded-access-token`) para actuar en su nombre |
# MAGIC
# MAGIC Así se ve una tool. El decorador la registra; el **docstring** se convierte en la descripción que lee el LLM, y los *type hints* en el esquema de parámetros:
# MAGIC
# MAGIC ```python
# MAGIC @mcp_server.tool
# MAGIC def calcular_sla(prioridad: str, horas_abierta: float) -> dict:
# MAGIC     """Calcula el estado de SLA de una incidencia de la mesa de servicio.
# MAGIC
# MAGIC     Úsala cuando necesites saber si una incidencia está dentro del SLA, en riesgo o
# MAGIC     vencida, cuántas horas le quedan y a quién hay que escalarla.
# MAGIC     """
# MAGIC     ...
# MAGIC ```

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### B.2 Cómo autentica
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
# MAGIC <div style="display:flex; justify-content:center; margin:12px 0;">
# MAGIC <svg viewBox="0 0 760 170" style="max-width:760px; width:100%;" font-family="-apple-system,sans-serif">
# MAGIC   <defs><marker id="h" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#1B5162"/></marker></defs>
# MAGIC   <rect x="10" y="50" width="150" height="70" rx="12" fill="#EAF1FB" stroke="#2272B4" stroke-width="2"/>
# MAGIC   <text x="85" y="80" text-anchor="middle" font-size="13" font-weight="700" fill="#1B3139">Cliente MCP</text>
# MAGIC   <text x="85" y="98" text-anchor="middle" font-size="11" fill="#5A6F77">AI Playground · agente</text>
# MAGIC   <rect x="300" y="40" width="170" height="90" rx="12" fill="#FEF3E2" stroke="#FFAB00" stroke-width="2"/>
# MAGIC   <text x="385" y="72" text-anchor="middle" font-size="13" font-weight="700" fill="#1B3139">Proxy de Apps</text>
# MAGIC   <text x="385" y="92" text-anchor="middle" font-size="11" fill="#5A6F77">valida OAuth y</text>
# MAGIC   <text x="385" y="108" text-anchor="middle" font-size="11" fill="#5A6F77">CAN USE en la app</text>
# MAGIC   <rect x="600" y="50" width="150" height="70" rx="12" fill="#E6F5EE" stroke="#00A972" stroke-width="2"/>
# MAGIC   <text x="675" y="80" text-anchor="middle" font-size="13" font-weight="700" fill="#1B3139">mcp-&lt;usuario&gt;</text>
# MAGIC   <text x="675" y="98" text-anchor="middle" font-size="11" fill="#5A6F77">tools en Python</text>
# MAGIC   <path d="M160 85 L298 85" stroke="#1B5162" stroke-width="2" marker-end="url(#h)"/>
# MAGIC   <text x="229" y="76" text-anchor="middle" font-size="11" fill="#1B3139">token OAuth</text>
# MAGIC   <path d="M470 85 L598 85" stroke="#1B5162" stroke-width="2" marker-end="url(#h)"/>
# MAGIC   <text x="534" y="76" text-anchor="middle" font-size="11" fill="#1B3139">x-forwarded-access-token</text>
# MAGIC   <text x="380" y="160" text-anchor="middle" font-size="12" fill="#5A6F77">El servidor puede actuar como el usuario final (tool usuario_actual) o como el service principal de la app.</text>
# MAGIC </svg>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Desplegar el servidor
# MAGIC
# MAGIC Tienes dos caminos. **En el lab usamos el camino 2** porque es más rápido y no depende de que todos encuentren los mismos botones; el camino 1 es el que usarías en tu día a día.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### C.1 Camino 1 · desde la UI (referencia)
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
# MAGIC 1. **Unity Gateway** → **MCPs** → **+ MCP** → **Build a new MCP server**.
# MAGIC 2. **Install from a template** → pestaña **Agents** → **MCP Server (Starter)** → **Next**.
# MAGIC 3. Nombre: `mcp-<tu usuario>` → **Create app**. Espera a que termine el despliegue en **Overview**.
# MAGIC 4. Para editar el código: **Edit in your IDE** (o copia los archivos a una carpeta del workspace), cambia `server/tools.py` y haz **Deploy** desde esa carpeta.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### C.2 Camino 2 · desde este notebook
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
# MAGIC La celda copia el código del servidor a tu carpeta `/Workspace/Users/<tú>/lab-agentes/mcp-server` (solo la primera vez, para no pisar tus cambios), crea la app `mcp-<tu usuario>` y la despliega. **Tarda ≈ 2–3 minutos**: lánzala y sigue leyendo.

# COMMAND ----------

import base64
from databricks.sdk.service.apps import App, AppDeployment
from databricks.sdk.service.workspace import ImportFormat

ORIGEN_MCP = os.path.abspath("mcp-server")


def copiar_servidor():
    try:
        w.workspace.get_status(CARPETA_MCP)
        print(f"• Ya tienes tu copia en {CARPETA_MCP} (no la sobrescribo)")
        return
    except Exception:
        pass
    for raiz, carpetas, archivos in os.walk(ORIGEN_MCP):
        carpetas[:] = [c for c in carpetas if not c.startswith((".", "__"))]
        for archivo in archivos:
            rel = os.path.relpath(os.path.join(raiz, archivo), ORIGEN_MCP)
            w.workspace.mkdirs(os.path.dirname(f"{CARPETA_MCP}/{rel}"))
            with open(os.path.join(raiz, archivo), "rb") as fh:
                w.workspace.import_(f"{CARPETA_MCP}/{rel}", content=base64.b64encode(fh.read()).decode(),
                                    format=ImportFormat.AUTO, overwrite=True)
    print(f"✓ Código copiado a {CARPETA_MCP}")


def desplegar_mcp():
    try:
        app = w.apps.get(MCP_APP)
        print(f"• La app {MCP_APP} ya existe")
    except Exception:
        print(f"• Creando la app {MCP_APP} (≈ 2 min)…")
        app = w.apps.create_and_wait(App(name=MCP_APP, description="MCP de la mesa de servicio (lab de agentes)"))
    inicio = time.time()
    d = w.apps.deploy_and_wait(app_name=MCP_APP, app_deployment=AppDeployment(source_code_path=CARPETA_MCP))
    app = w.apps.get(MCP_APP)
    print(f"✓ Despliegue {d.status.state.value} en {time.time() - inicio:.0f}s · {d.status.message}")
    return app


copiar_servidor()
app_mcp = desplegar_mcp()
URL_MCP_PROPIO = app_mcp.url + "/mcp"
displayHTML(f"<div style='font-size:15px'>URL de tu MCP: <code>{URL_MCP_PROPIO}</code><br>"
            f"App: <a href='{HOST}/apps/{MCP_APP}' target='_blank'>{MCP_APP}</a> · "
            f"Código: <a href='{HOST}/#workspace{CARPETA_MCP}' target='_blank'>{CARPETA_MCP}</a></div>")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### C.3 Abrir la app
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
# MAGIC Abre el link de la app. La página raíz responde `{"status": "healthy", "mcp": "/mcp"}`: el servidor está vivo. En la pestaña **Logs** verás cada request MCP que llegue.

# COMMAND ----------

# MAGIC %md
# MAGIC ## D. Probar el MCP
# MAGIC
# MAGIC Un MCP en Apps exige un **token OAuth** del usuario. Lo más directo es probarlo desde las herramientas de Databricks que ya hacen ese login por ti.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### D.1 En AI Playground
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
# MAGIC 1. **AI Playground** → elige un modelo con tools (por ejemplo Claude Sonnet).
# MAGIC 2. **Tools** → **+ Add tool** → **MCP Servers** → elige tu app `mcp-<tu usuario>` (aparece por el prefijo `mcp-`).
# MAGIC 3. Pregunta: *"Llama la tool health"* → debe responder `healthy`.
# MAGIC 4. Pregunta: *"La incidencia P1 lleva 6 horas abierta, ¿cómo está su SLA y a quién escalo?"* → debe llamar `calcular_sla`.
# MAGIC 5. Pregunta: *"¿Quién soy?"* → `usuario_actual` devuelve **tu** correo: el servidor recibe tu identidad.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">Versión con CLI (laptop)</strong><br>Con tu perfil OAuth y <code>uv run --with databricks-mcp python</code>: <code>from databricks.sdk import WorkspaceClient; from databricks_mcp import DatabricksMCPClient; w = WorkspaceClient(profile='&lt;perfil&gt;'); print([t.name for t in DatabricksMCPClient(server_url='&lt;url&gt;/mcp', workspace_client=w).list_tools()])</code>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## E. Reto: agrega la tool `prioridad_sugerida`
# MAGIC
# MAGIC La mesa de ayuda recibe reclamos en texto libre y quiere que el agente **sugiera su prioridad** (P1 a P4). La función ya está escrita: tu trabajo es **agregarla al servidor, redesplegarlo y probarla**. Es el ciclo real de mantener un MCP: editar `tools.py` → redeploy → reconectar.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### E.1 La función que vas a agregar
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
# MAGIC Fíjate en tres cosas:
# MAGIC - `@mcp_server.tool` la registra como tool del servidor.
# MAGIC - El **docstring** es lo que lee el LLM: dice qué hace y cuándo usarla.
# MAGIC - Los **type hints** (`descripcion: str`, `-> dict`) se convierten en el esquema de parámetros.
# MAGIC
# MAGIC ```python
# MAGIC     @mcp_server.tool
# MAGIC     def prioridad_sugerida(descripcion: str) -> dict:
# MAGIC         """Sugiere la prioridad (P1 a P4) de un reclamo nuevo de la mesa de servicio a partir de su texto.
# MAGIC
# MAGIC         Úsala cuando alguien describa un problema y pregunte qué prioridad debería tener o qué tan
# MAGIC         urgente es. Devuelve la prioridad, las horas de SLA que le corresponden y la regla aplicada.
# MAGIC
# MAGIC         Args:
# MAGIC             descripcion: texto del reclamo tal como lo escribió el usuario o el agente de venta.
# MAGIC         """
# MAGIC         texto = descripcion.lower()
# MAGIC         reglas = [
# MAGIC             ("P1", ("caído", "caido", "no vende", "no puedo vender", "premio", "no llegó el pago", "rechaza pagos"),
# MAGIC              "Afecta ventas o el pago de premios"),
# MAGIC             ("P2", ("error", "no puedo", "no carga", "rechazada", "pendiente"),
# MAGIC              "Falla que impide una operación del usuario"),
# MAGIC             ("P3", ("lento", "demora", "notificación", "historial"),
# MAGIC              "Degradación o funcionalidad secundaria"),
# MAGIC         ]
# MAGIC         for prioridad, palabras, motivo in reglas:
# MAGIC             encontradas = [p for p in palabras if p in texto]
# MAGIC             if encontradas:
# MAGIC                 return {"prioridad": prioridad, "sla_horas": SLA_HORAS[prioridad],
# MAGIC                         "regla": motivo, "palabras_clave": encontradas}
# MAGIC         return {"prioridad": "P4", "sla_horas": SLA_HORAS["P4"], "regla": "Consulta o pedido sin impacto operativo",
# MAGIC                 "palabras_clave": []}
# MAGIC ```

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### E.2 Pégala en `server/tools.py`
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
# MAGIC 1. Corre la celda de abajo y abre el link a **tu** `tools.py`.
# MAGIC 2. Ve al **final del archivo**. La última línea es el comentario `# RETO del Lab 2: pega aquí la función prioridad_sugerida…`.
# MAGIC 3. Pon el cursor al final de ese comentario, presiona **Enter** y pega la función de E.1 tal cual.
# MAGIC 4. Revisa la sangría: `@mcp_server.tool` debe quedar **alineado con el comentario** (4 espacios), igual que las otras tools del archivo, porque todas viven dentro de `load_tools`.
# MAGIC 5. No hay que guardar: el editor guarda solo.

# COMMAND ----------

ARCHIVO_TOOLS = f"{CARPETA_MCP}/server/tools.py"
displayHTML(f"<div style='font-size:15px'>📝 Abre tu archivo: <a href='{HOST}/#workspace{ARCHIVO_TOOLS}' target='_blank'>{ARCHIVO_TOOLS}</a></div>")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### E.3 Revisar y redesplegar
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
# MAGIC La celda revisa tu `tools.py` antes de desplegar: que la función esté y que el archivo no tenga errores de sintaxis ni de sangría. Si todo está bien, redespliega la app (≈ 15–30 s).

# COMMAND ----------

import ast


def revisar_tools():
    codigo = open(ARCHIVO_TOOLS, encoding="utf-8").read()
    try:
        arbol = ast.parse(codigo)
    except SyntaxError as e:
        print(f"✗ Error de sintaxis en la línea {e.lineno}: {e.msg}. Suele ser la sangría: revisa el paso 4 de E.2.")
        return False
    carga = next((n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == "load_tools"), None)
    internas = [n.name for n in ast.walk(carga) if isinstance(n, ast.FunctionDef)] if carga else []
    if "prioridad_sugerida" in internas:
        print("✓ prioridad_sugerida está dentro de load_tools")
        return True
    if "def prioridad_sugerida" in codigo:
        print("✗ La función quedó fuera de load_tools: agrégale sangría para alinearla con el comentario # RETO del Lab 2.")
    else:
        print("✗ Todavía no encuentro prioridad_sugerida en tu tools.py: pega la función de E.1 (paso 3 de E.2).")
    return False


if revisar_tools():
    app_mcp = desplegar_mcp()

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### E.4 Probarla en AI Playground
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
# MAGIC 1. En **AI Playground**, quita tu MCP de las tools y vuelve a agregarlo: las tools se leen al conectar, así que sin reconectar no verás la nueva.
# MAGIC 2. Pregunta: *"Un vendedor reporta: el terminal no vende desde las 8 de la mañana. ¿Qué prioridad le pongo?"* → debe llamar `prioridad_sugerida` y responder **P1** (regla "Afecta ventas o el pago de premios").
# MAGIC 3. Pregunta: *"La app está lenta al cargar el historial de jugadas, ¿qué tan urgente es?"* → **P3**.
# MAGIC 4. Pregunta: *"Llegó el reclamo 'no me llegó el pago del premio'. ¿Qué prioridad tiene y cómo está su SLA si lleva 3 horas abierto?"* → el modelo encadena `prioridad_sugerida` y `calcular_sla`.
# MAGIC
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">Si no aparece la tool</strong><br>Revisa la pestaña <b>Logs</b> de tu app <code>mcp-&lt;usuario&gt;</code>: si el servidor no arrancó, ahí verás el error. La función también está en <code>soluciones/Lab 2 - tool prioridad_sugerida.py</code>. En el <b>Lab 3</b> tu agente tendrá esta tool automáticamente, porque conecta todo tu MCP.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusión
# MAGIC
# MAGIC Tienes tu propio servidor MCP en Databricks Apps, con tools de negocio en Python, autenticación OAuth y la identidad del usuario final disponible en cada llamada. Lo probaste sin escribir un cliente, desde AI Playground, y le agregaste una tool nueva con un redeploy.
# MAGIC
# MAGIC En el **Lab 3** este servidor se convierte en una tool más de tu agente, junto a tu UC function, el Genie y el sandbox. Anota la URL de tu MCP: la vas a necesitar.
