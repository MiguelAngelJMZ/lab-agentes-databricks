# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 3 (versión B) · Agente custom desde el navegador
# MAGIC #### Duración: 50 minutos

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## Panorama
# MAGIC
# MAGIC Es **el mismo agente** que la versión A, construido con el **mismo Agent Bricks CLI**, pero sin instalar nada en tu laptop: el CLI corre **dentro de este notebook serverless** y el proyecto vive en una carpeta de tu workspace, donde lo editas con el editor de Databricks.
# MAGIC
# MAGIC | Tool | De dónde viene |
# MAGIC |---|---|
# MAGIC | `incidencias_abiertas` | Tu UC function (Lab 1) |
# MAGIC | Genie "Mesa de servicio" | Genie Agent |
# MAGIC | `run_code` | Databricks Sandbox (*opcional*: solo si tu workspace lo tiene) |
# MAGIC | `calcular_sla`, `estado_plataforma_juego` | Tu MCP en Apps (Lab 2) |
# MAGIC | `remember`, `recall` | Memoria de largo plazo |
# MAGIC
# MAGIC Lo único que cambia frente a la versión A: no hay `agentbricks dev` (no hay "local"); pruebas directamente el agente desplegado.
# MAGIC
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">¿Y la plantilla de Apps?</strong><br>También existe la ruta <b>+ New → App → Agents → Custom Agent (OpenAI SDK)</b>. Usa MLflow AgentServer, que la documentación marca como <i>legacy</i>; para agentes nuevos se recomienda el Agent Bricks CLI, por eso lo usamos aquí también.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Objetivos de aprendizaje
# MAGIC
# MAGIC - **Ejecutar** el Agent Bricks CLI desde un notebook y **describir** lo que declara `agent.toml`.
# MAGIC - **Ubicar** en el proyecto dónde vive cada pieza del agente y **decidir** dónde se agrega cada tipo de tool.
# MAGIC - **Agregar** al agente tu UC function, el Genie, el sandbox y tu MCP del Lab 2.
# MAGIC - **Editar** el código del agente en el workspace y **redeployar**.
# MAGIC - **Leer** una traza en MLflow y **demostrar** que el agente recuerda una preferencia entre sesiones.

# COMMAND ----------

# MAGIC %pip install -q uv "mlflow>=3.5"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./Includes/Setup-Lab

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### Setup: el CLI dentro del notebook
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
# MAGIC `agentbricks(...)` ejecuta el CLI con `uv` en un entorno aislado (no toca las librerías del notebook) y con tu identidad. La celda también descarga el Databricks CLI, que el Agent Bricks CLI usa por debajo. Tu proyecto queda en `/Workspace/Users/<tú>/lab-agentes/<agente>`.

# COMMAND ----------

import io, platform, shutil, subprocess, sys, zipfile
import requests

UV = shutil.which("uv") or os.path.join(os.path.dirname(sys.executable), "uv")

# El Agent Bricks CLI usa por debajo el Databricks CLI: lo descargamos en /tmp (≈ 15 MB, una vez por sesión)
VERSION_CLI = "1.24.0"
VERSION_AGENTBRICKS = "0.9.0"  # versión validada para el lab
CARPETA_CLI = "/tmp/databricks-cli"
if not os.path.exists(f"{CARPETA_CLI}/databricks"):
    arq = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}[platform.machine()]
    zip_cli = requests.get(f"https://github.com/databricks/cli/releases/download/v{VERSION_CLI}/"
                           f"databricks_cli_{VERSION_CLI}_linux_{arq}.zip", timeout=120)
    zip_cli.raise_for_status()
    zipfile.ZipFile(io.BytesIO(zip_cli.content)).extractall(CARPETA_CLI)
    os.chmod(f"{CARPETA_CLI}/databricks", 0o755)
CARPETA_TRABAJO = f"/Workspace/Users/{YO}/lab-agentes"
PROYECTO = f"{CARPETA_TRABAJO}/{AGENTE}"
os.makedirs(CARPETA_TRABAJO, exist_ok=True)


def agentbricks(*args, cwd=None, timeout=900):
    """Corre `agentbricks <args>` y muestra su salida."""
    # Sin las credenciales del notebook (el CLI usa DATABRICKS_HOST/TOKEN), pero conservando la versión
    # del runtime: MLflow la necesita para configurar el tracing.
    conservar = ("DATABRICKS_ENV_VERSION", "DATABRICKS_RUNTIME_VERSION")
    entorno = {k: v for k, v in os.environ.items()
               if k in conservar or not k.startswith(("DATABRICKS_", "SPARK", "PYSPARK"))}
    entorno.update(DATABRICKS_HOST=HOST, DATABRICKS_TOKEN=token(), AGENTBRICKS_DISABLE_AGENT_HINT="1",
                   NO_COLOR="1", TERM="dumb", COLUMNS="110", UV_CACHE_DIR="/tmp/uv-cache",
                   PATH=f"{CARPETA_CLI}:{os.environ['PATH']}")
    p = subprocess.run([UV, "tool", "run", "--quiet", "--from", f"databricks-agentbricks=={VERSION_AGENTBRICKS}", "agentbricks", *args],
                       cwd=cwd or PROYECTO, env=entorno, capture_output=True, text=True, timeout=timeout)
    salida = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", p.stdout + p.stderr)
    salida = "\n".join(l for l in salida.splitlines() if not re.match(r"^\s*[⠁-⣿]\s*[\d:]*\s*$", l))
    print(salida.strip()[-4000:])
    if p.returncode != 0:
        raise RuntimeError(f"agentbricks {' '.join(args)} terminó con código {p.returncode}")


agentbricks("--version", cwd=CARPETA_TRABAJO)

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Crear el proyecto

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### A.1 `init`
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
# MAGIC Crea el proyecto LangGraph con chat UI y declara los stores de memoria y sesiones y el experimento de trazas. Si ya existe, no hace nada.

# COMMAND ----------

if os.path.exists(f"{PROYECTO}/agent.toml"):
    print(f"• El proyecto {PROYECTO} ya existe")
else:
    agentbricks("init", "--framework", "langgraph", AGENTE, cwd=CARPETA_TRABAJO)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### A.2 Qué creó `init`
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
# MAGIC `init` creó un proyecto completo en tu workspace: el agente, un servidor HTTP durable, un chat en el navegador, tests y la configuración de despliegue. Corre la celda para ver el árbol de tu proyecto. Parece mucho, pero **solo cuatro piezas (★) definen tu agente**. El resto es infraestructura que no necesitas tocar (el árbol omite las carpetas ocultas, como `.agents/`).

# COMMAND ----------

ESTRELLA = {"agent.toml", "agent/agent.py", "agent/mcps.py", "agent/tools"}


def mostrar_proyecto(raiz=PROYECTO):
    lineas = []
    for actual, carpetas, archivos in os.walk(raiz):
        carpetas[:] = sorted(c for c in carpetas if not c.startswith((".", "__")))
        rel = os.path.relpath(actual, raiz)
        nivel = 0 if rel == "." else rel.count(os.sep) + 1
        if rel != ".":
            lineas.append(("    " * (nivel - 1)) + f"{os.path.basename(actual)}/" + ("  ★" if rel in ESTRELLA else ""))
        for a in sorted(f for f in archivos if not f.endswith(".pyc")):
            ruta = a if rel == "." else f"{rel}/{a}"
            lineas.append(("    " * nivel) + a + ("  ★" if ruta in ESTRELLA else ""))
    displayHTML("<pre style='background:#0B2026;color:#E6F5EE;padding:14px 16px;border-radius:10px;font-size:13px;line-height:1.45'>"
                + f"{os.path.basename(raiz)}/\n" + "\n".join("    " + l for l in lineas) + "</pre>")


mostrar_proyecto()

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC | Archivo | Qué es | ¿Lo tocas? |
# MAGIC |---|---|---|
# MAGIC | **`agent.toml`** | Qué recursos de Databricks usa el agente: tools, memoria, sesiones, trazas, modelo | **Sí: es el núcleo**, casi siempre vía comandos del CLI |
# MAGIC | **`agent/agent.py`** | El agente: prompt de sistema (`SYSTEM_PROMPT`), armado de tools, modelo y `run_agent` | **Sí**: el prompt y la lógica |
# MAGIC | **`agent/mcps.py`** | MCP propios que no se declaran en `agent.toml` (ver A.6) | Sí, si usas MCP propios |
# MAGIC | **`agent/tools/`** | Tools en Python: cualquier función con `@tool` en un archivo de esta carpeta se registra sola | Sí, si quieres tools locales |
# MAGIC | `app.yaml` | Variables de entorno del despliegue | A veces: el script del lab escribe aquí la URL de tu MCP |
# MAGIC | `.env.example`, `.env` | Variables para correr el agente en una laptop con `agentbricks dev` | No en esta versión |
# MAGIC | `pyproject.toml` | Dependencias de Python | Si agregas librerías |
# MAGIC | `runtime/` | Servidor HTTP (`/api/invocations`), streaming, recuperación ante fallos y la UI | No |
# MAGIC | `ui/` | El chat del navegador | No |
# MAGIC | `tests/` | Pruebas de la plantilla | Opcional |
# MAGIC | `AGENTS.md`, `CLAUDE.md`, `.agents/skills/` | Instrucciones para asistentes de código (Claude Code, Cursor…), para que te ayuden a editar el proyecto | No |
# MAGIC | `README.md`, `AGENTKIT_CONTRACT.md`, `CHAT_APP.md` | Documentación de la plantilla | Solo lectura |
# MAGIC
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">Dos ejemplos que trae la plantilla</strong><br>En <code>agent/tools/</code> vienen <code>get_current_time</code> (una tool simple) y <code>send_message</code>. En <code>agent.py</code>, <code>send_message</code> aparece en <code>REQUIRE_APPROVAL</code>: antes de ejecutarla el agente se detiene y pide aprobación (<i>human in the loop</i>). Es la forma de proteger tools que hacen cambios.
# MAGIC </div>
# MAGIC <p style="font-size:13px; color:#5A6F77;"><strong>Documentación:</strong> <a href="`agentbricks init --help`: `--framework langgraph` (por defecto) u `openai` (OpenAI Agents SDK); `--server custom` para un FastAPI mínimo; `--existing` para migrar un agente que ya tienes." target="_blank" style="color:#2272B4;">Opciones de init</a></p>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### A.3 Tools gestionadas y model service
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
# MAGIC Cada comando valida el recurso y lo declara en `agent.toml`. El último hace que el modelo pase por **tu** model service, que gobernarás en el Lab 4.
# MAGIC
# MAGIC El **sandbox es opcional**: la celda lo agrega solo si tu workspace tiene Databricks Sandbox (`system.ai.sandbox`). Si no existe, lo deja fuera, porque una tool declarada que no responde impide que el agente arranque.

# COMMAND ----------

toml_actual = open(f"{PROYECTO}/agent.toml").read()
if "incidencias_abiertas" not in toml_actual:
    agentbricks("tools", "add", "uc-function", f"{CATALOGO}.{MI_ESQUEMA}.incidencias_abiertas")
if "genie_agent" not in toml_actual:
    agentbricks("tools", "add", "genie-agent", GENIE_ID)
SANDBOX = sandbox_disponible()
if SANDBOX and 'kind = "sandbox"' not in toml_actual:
    agentbricks("tools", "add", "sandbox")
elif not SANDBOX and 'kind = "sandbox"' in toml_actual:
    agentbricks("tools", "remove", "sandbox")  # declarado pero sin servicio: el agente no arrancaría
if not SANDBOX:
    print("• Sin sandbox: Databricks Sandbox no está disponible en este workspace. Tu agente funcionará sin run_code.\n")
if "model_services" not in toml_actual:
    agentbricks("experimental", "models", "bind", MODELO_SERVICIO, "--default", MODELO_SYSTEM)
print(open(f"{PROYECTO}/agent.toml").read())

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### A.4 Cómo llegan las tools al agente
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
# MAGIC Las tools entran en dos momentos. Al **construir**, cada `tools add` de la celda A.3 validó la tool y la declaró en `agent.toml`. Al **responder**, en cada pregunta, `create_agent_graph` en `agent/agent.py` junta las tools de cuatro fuentes y arma el agente:
# MAGIC
# MAGIC <div style="display:flex; justify-content:center; margin:12px 0;">
# MAGIC <svg viewBox="0 0 860 250" style="max-width:860px; width:100%;" font-family="-apple-system,sans-serif">
# MAGIC   <defs><marker id="fl" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#1B5162"/></marker></defs>
# MAGIC   <rect x="10" y="10" width="270" height="48" rx="10" fill="#fff" stroke="#2272B4" stroke-width="2"/><text x="24" y="31" font-size="12" font-weight="700" fill="#1B3139">agent.toml · [[tools]]</text><text x="24" y="48" font-size="10.5" fill="#5A6F77">UC function, sandbox, MCP gestionados, Genie</text>
# MAGIC   <rect x="10" y="68" width="270" height="48" rx="10" fill="#fff" stroke="#2272B4" stroke-width="2"/><text x="24" y="89" font-size="12" font-weight="700" fill="#1B3139">agent/mcps.py</text><text x="24" y="106" font-size="10.5" fill="#5A6F77">tu MCP del Lab 2 (por URL)</text>
# MAGIC   <rect x="10" y="126" width="270" height="48" rx="10" fill="#fff" stroke="#2272B4" stroke-width="2"/><text x="24" y="147" font-size="12" font-weight="700" fill="#1B3139">agent/tools/*.py</text><text x="24" y="164" font-size="10.5" fill="#5A6F77">tools Python con @tool</text>
# MAGIC   <rect x="10" y="184" width="270" height="48" rx="10" fill="#fff" stroke="#2272B4" stroke-width="2"/><text x="24" y="205" font-size="12" font-weight="700" fill="#1B3139">[memory_store]</text><text x="24" y="222" font-size="10.5" fill="#5A6F77">remember · recall · forget</text>
# MAGIC   <rect x="380" y="70" width="230" height="104" rx="14" fill="#F9F7F4" stroke="#FF3621" stroke-width="2"/><text x="495" y="100" text-anchor="middle" font-size="13" font-weight="700" fill="#1B3139">create_agent_graph()</text><text x="495" y="120" text-anchor="middle" font-size="10.5" fill="#5A6F77">agent/agent.py · en cada pregunta</text><text x="495" y="138" text-anchor="middle" font-size="10.5" fill="#5A6F77">con la identidad de quien pregunta</text><text x="495" y="156" text-anchor="middle" font-size="10.5" fill="#5A6F77">(auth = "user")</text>
# MAGIC   <rect x="690" y="88" width="160" height="68" rx="12" fill="#1B3139"/><text x="770" y="118" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">Agente</text><text x="770" y="137" text-anchor="middle" font-size="10.5" fill="#C9D3D6">LLM + tools + prompt</text>
# MAGIC   <path d="M280 34 L378 100" stroke="#1B5162" stroke-width="2" marker-end="url(#fl)"/>
# MAGIC   <path d="M280 92 L378 115" stroke="#1B5162" stroke-width="2" marker-end="url(#fl)"/>
# MAGIC   <path d="M280 150 L378 130" stroke="#1B5162" stroke-width="2" marker-end="url(#fl)"/>
# MAGIC   <path d="M280 208 L378 146" stroke="#1B5162" stroke-width="2" marker-end="url(#fl)"/>
# MAGIC   <path d="M610 122 L688 122" stroke="#1B5162" stroke-width="2" marker-end="url(#fl)"/>
# MAGIC </svg>
# MAGIC </div>
# MAGIC
# MAGIC Este es el código que vas a encontrar en tu `agent/agent.py`:
# MAGIC
# MAGIC ```python
# MAGIC mcp = await mcp_tools(build_mcp_servers(), ...)   # agent.toml (UC function, sandbox, MCP) + agent/mcps.py
# MAGIC tools = [
# MAGIC     *all_tools(),          # agent/tools/*.py
# MAGIC     *memory_tools(actor),  # remember / recall / forget de ESTE usuario
# MAGIC     *genie_tools(...),     # el Genie declarado en agent.toml
# MAGIC     *mcp,
# MAGIC ]
# MAGIC return create_agent(model=..., tools=tools, system_prompt=SYSTEM_PROMPT, ...)
# MAGIC ```
# MAGIC
# MAGIC Que el agente se arme **en cada pregunta** no es un detalle: así cada llamada usa las credenciales de quien pregunta y su propia memoria. Por eso agregar una tool **no requiere editar `agent.py`**: basta con declararla donde corresponde.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### A.5 Tu MCP y el prompt en español
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
# MAGIC `agente-referencia/aplicar_referencia.py` conecta tu MCP del Lab 2 por URL (`agent/mcps.py`), agrega un prompt de sistema en español a `agent/agent.py` y declara la URL en `app.yaml`. Ábrelo: son 80 líneas.

# COMMAND ----------

URL_MCP_PROPIO = w.apps.get(MCP_APP).url
r = subprocess.run([sys.executable, os.path.abspath("agente-referencia/aplicar_referencia.py"), URL_MCP_PROPIO],
                   cwd=PROYECTO, capture_output=True, text=True)
print(r.stdout or r.stderr)
displayHTML(f"<div style='font-size:15px'>Tu proyecto: <a href='{HOST}/#workspace{PROYECTO}' target='_blank'>{PROYECTO}</a> · "
            f"abre <code>agent/agent.py</code> y busca <code>SYSTEM_PROMPT</code>.</div>")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### A.6 ¿Dónde agrego una tool nueva?
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
# MAGIC Depende de qué tipo de tool sea:
# MAGIC
# MAGIC | Quiero agregar… | Dónde | Cómo |
# MAGIC |---|---|---|
# MAGIC | Una **UC function** | `agent.toml` | `agentbricks tools add uc-function <catálogo>.<schema>.<función>` |
# MAGIC | Un **Genie** | `agent.toml` | `agentbricks tools add genie-agent <space_id>` |
# MAGIC | El **sandbox** de código | `agent.toml` | `agentbricks tools add sandbox` |
# MAGIC | Un **MCP gestionado o registrado en Unity Gateway** (`system.ai.*`, un MCP externo registrado, Genie One) | `agent.toml` | `agentbricks tools add mcp <servicio>`. Para ver los disponibles: `agentbricks tools list --kind mcp` |
# MAGIC | **Un MCP propio en Databricks Apps** (como el del Lab 2) o cualquier URL directa | `agent/mcps.py` | Por código (ejemplo abajo) |
# MAGIC | Una **función Python** propia | `agent/tools/` | Un archivo nuevo con una función decorada con `@tool` |
# MAGIC
# MAGIC Tu MCP del Lab 2 va en `mcps.py` porque una app de Databricks Apps **no se puede registrar** como MCP service en Unity Gateway. Para agregar un segundo MCP en una app, extiende la lista de `build_mcp_servers()`:
# MAGIC
# MAGIC ```python
# MAGIC def build_mcp_servers() -> list[DatabricksMCPServer]:
# MAGIC     servidores = []
# MAGIC     for nombre, variable in [("mcp_mesa_servicio", "MCP_MESA_SERVICIO_URL"),
# MAGIC                              ("mcp_inventario", "MCP_INVENTARIO_URL")]:   # ← el nuevo
# MAGIC         url = os.getenv(variable, "").strip().rstrip("/")
# MAGIC         if url:
# MAGIC             servidores.append(DatabricksMCPServer(
# MAGIC                 name=nombre,
# MAGIC                 url=url if url.endswith("/mcp") else url + "/mcp",
# MAGIC                 workspace_client=workspace_client()))
# MAGIC     return servidores
# MAGIC ```
# MAGIC
# MAGIC Y tres pasos más:
# MAGIC 1. Declara la variable en el `app.yaml` de tu proyecto, dentro de la lista `env:` (igual que `MCP_MESA_SERVICIO_URL`): `- name: MCP_INVENTARIO_URL` y `value: <url de la app>`.
# MAGIC 2. Dale al service principal del agente `CAN USE` sobre esa app, como en la celda B.2.
# MAGIC 3. Redespliega con `desplegar()` (celda C.1).
# MAGIC
# MAGIC En esta versión los comandos del CLI se corren con el helper del notebook: por ejemplo `agentbricks("tools", "add", "uc-function", "<catálogo>.<schema>.<función>")` y después `desplegar()`.
# MAGIC
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">MCP de terceros</strong><br>Para un MCP externo (de un proveedor), lo recomendable es <b>registrarlo en Unity Gateway</b> y agregarlo con <code>tools add mcp</code>. Así queda gobernado: permisos, rate limits, policies y registro en <code>system.ai_gateway.usage</code>, sin credenciales en el código.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Desplegar

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### B.1 `deploy`
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
# MAGIC Sube el código como app `agent-bricks-<agente>`, crea los stores, tu model service y los permisos del service principal. **La primera vez tarda 4–6 minutos.** Si el CLI se cansa de esperar el cómputo de la app, la celda reintenta una vez. Al final verás *"Couldn't check the agent answers… uses a PAT"*: es normal desde un notebook; el agente sí quedó desplegado.

# COMMAND ----------

def desplegar():
    try:
        agentbricks("deploy", AGENTE, timeout=1200)
    except RuntimeError:
        print("\n• Reintentando: la app tardó en arrancar la primera vez…\n")
        agentbricks("deploy", AGENTE, timeout=1200)


desplegar()

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### B.2 Dar acceso a tu MCP
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
# MAGIC Tu agente llama al MCP del Lab 2 con la identidad de su service principal: necesita `CAN USE` sobre la app del MCP.

# COMMAND ----------

from databricks.sdk.service.apps import AppAccessControlRequest, AppPermissionLevel

app_agente = w.apps.get(AGENTE_APP)
w.apps.update_permissions(MCP_APP, access_control_list=[
    AppAccessControlRequest(service_principal_name=app_agente.service_principal_client_id,
                            permission_level=AppPermissionLevel.CAN_USE)])
print(f"✓ {AGENTE_APP} puede usar {MCP_APP}")
displayHTML(f"<div style='font-size:15px'>Abre tu agente: <a href='{app_agente.url}' target='_blank'>{app_agente.url}</a></div>")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### B.3 Probarlo
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
# MAGIC En el chat del agente pregunta:
# MAGIC
# MAGIC > *¿Cuántas P1 llevan más de 24 horas abiertas, qué equipos concentran más y cuál es el estado de SLA de la más antigua?*
# MAGIC
# MAGIC Deberías ver tres tools en cadena: `incidencias_abiertas` → `run_code` → `calcular_sla`, y al final la lista de fuentes usadas. Si tu workspace no tiene sandbox, la cadena es `incidencias_abiertas` → `calcular_sla` y el conteo lo hace el modelo.

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Editar y redeployar

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### C.1 Cambia el comportamiento
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
# MAGIC Abre `agent/agent.py` en tu proyecto (link de la celda A.5) y cambia el `SYSTEM_PROMPT`: por ejemplo, que siempre cierre con una recomendación de a quién escalar. Guarda y redeploya (≈ 35 s):

# COMMAND ----------

desplegar()

# COMMAND ----------

# MAGIC %md
# MAGIC ## D. Trazas y memoria

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### D.1 Tus últimas trazas
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
experimentos = mlflow.search_experiments(filter_string=f"name LIKE '/Shared/agentbricks_traces/{AGENTE}-%'")
if not experimentos:
    print("Todavía no hay experimento: despliega el agente y hazle una pregunta.")
else:
    exp = experimentos[0]
    orden = dict(max_results=5, order_by=["timestamp_ms DESC"])
    try:
        trazas = mlflow.search_traces(locations=[exp.experiment_id], include_spans=False, **orden)
    except TypeError:  # MLflow anterior a 3.5
        trazas = mlflow.search_traces(experiment_ids=[exp.experiment_id], **orden)
    if len(trazas):
        display(trazas[[c for c in ["trace_id", "request_time", "execution_duration", "state", "request_preview"] if c in trazas.columns]])
    else:
        print("El experimento existe pero aún no tiene trazas: hazle una pregunta al agente desplegado.")
    displayHTML(f"<a href='{HOST}/ml/experiments/{exp.experiment_id}/traces' target='_blank'>Abrir las trazas en MLflow</a>")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### D.2 Reto: que recuerde una preferencia
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
# MAGIC 1. En el chat: *"Recuerda esto: prefiero las respuestas en una tabla y sin emojis."* → `remember`.
# MAGIC 2. **New chat** y pregunta: *"¿Qué equipos tienen más P1 abiertas?"* → `recall` al inicio y respuesta en tabla, sin emojis.
# MAGIC 3. En la tarjeta **Memory** del chat verás la entrada que guardó.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">Si te atoras</strong><br>Los logs del agente: <code>agentbricks("deployments", "logs", AGENTE_APP)</code>. Errores comunes: olvidar la celda B.2 (el MCP responde 401/403) o un error de sintaxis en <code>agent/agent.py</code> (el deploy falla al arrancar).
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusión
# MAGIC
# MAGIC Construiste y desplegaste un agente custom sin instalar nada: el mismo CLI, el mismo `agent.toml` y el mismo runtime que la versión con laptop. Lo que aprendiste se traslada tal cual al flujo de desarrollo local cuando el equipo tenga su ambiente listo.
# MAGIC
# MAGIC En el **Lab 4** gobiernas el modelo de tu agente desde Unity Gateway.
