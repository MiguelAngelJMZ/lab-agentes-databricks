# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 1 · Tools con Unity Catalog functions y MCP
# MAGIC #### Duración: 30 minutos

# COMMAND ----------

# MAGIC %md
# MAGIC ## Panorama
# MAGIC
# MAGIC Un agente es un LLM que **decide** qué hacer y **actúa** con herramientas (*tools*). Sin tools, el modelo solo puede conversar; con tools puede consultar datos gobernados, calcular, llamar APIs y escribir resultados. En este lab construyes las tools que vas a reutilizar el resto del día.
# MAGIC
# MAGIC Partimos del dataset que ya conoces: la **mesa de servicio de TI** de La Tinka (incidencias, equipos, SLA, encuestas, proyectos). Genie no es el tema central: aparece como **una tool más** del agente.
# MAGIC
# MAGIC El lab tiene seis secciones:
# MAGIC
# MAGIC - **A. Qué es un agente y qué es una tool**: el ciclo de decisión y por qué la descripción de una tool lo es todo
# MAGIC - **B. Tu primera tool**: una Unity Catalog function con SQL parametrizado
# MAGIC - **C. La función como MCP**: el servidor MCP de UC functions y lo que realmente ve el LLM
# MAGIC - **D. MCP gestionados**: Genie Agent MCP, Genie One y Databricks SQL
# MAGIC - **E. Un agente mínimo**: LangGraph + las tres fuentes, con trazas en MLflow
# MAGIC - **F. Reto**: encapsular una regla de negocio ("en riesgo de SLA") que el LLM no puede adivinar
# MAGIC
# MAGIC **Cómo leer este notebook.** LECTURA son conceptos y diagramas; DEMO es código que corres; RETO es lo que haces tú; UI son pasos en la interfaz de Databricks.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Objetivos de aprendizaje
# MAGIC
# MAGIC Al terminar este lab podrás:
# MAGIC - **Explicar** el ciclo de un agente (decidir → llamar una tool → observar → responder) y el papel de la descripción de cada tool.
# MAGIC - **Crear** una Unity Catalog function con parámetros documentados y probarla en SQL.
# MAGIC - **Exponer** tus funciones por el MCP de UC functions y **listar** las tools tal como las recibe el LLM.
# MAGIC - **Conectar** el Genie "Mesa de servicio" y Databricks SQL como tools vía MCP gestionados.
# MAGIC - **Construir** un agente mínimo con LangGraph y **leer** su traza en MLflow.
# MAGIC - **Encapsular** una regla de negocio en una UC function para que el agente responda de forma consistente.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="border: 1px solid #DCE0E2; border-radius: 12px; overflow: hidden; margin: 16px 0;">
# MAGIC   <div style="background: #FF3621; color: #fff; padding: 11px 18px;">
# MAGIC     <strong style="font-size: 13pt; letter-spacing: 0.05em; text-transform: uppercase;">Antes de empezar: elige el cómputo</strong>
# MAGIC   </div>
# MAGIC   <div style="background: #F9F7F4; padding: 18px 22px; color: #1B3139;">
# MAGIC     <ol style="margin: 0; padding-left: 22px; font-size: 13pt; line-height: 1.7;">
# MAGIC       <li><strong>Conecta Serverless:</strong> en el menú <strong>Connect</strong> (arriba a la derecha) elige <strong>Serverless</strong>.</li>
# MAGIC       <li><strong>Corre las celdas en orden</strong> con <strong>Shift + Enter</strong>. La primera instala librerías (≈ 1 min).</li>
# MAGIC     </ol>
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### Setup del lab
# MAGIC
# MAGIC La primera celda instala las librerías de agentes. La segunda calcula tus nombres de recursos (tu schema es `ag_<tu usuario>`) y lo crea si no existe.

# COMMAND ----------

# MAGIC %pip install -q langgraph langchain langchain-openai langchain-mcp-adapters "mcp>=1.24,<2" "mlflow>=3.5"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./Includes/Setup-Lab

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Qué es un agente y qué es una tool
# MAGIC
# MAGIC Antes de escribir código, fijemos el modelo mental que usaremos todo el día.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### A.1 El ciclo de un agente
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
# MAGIC Un agente repite un ciclo corto: el LLM lee la pregunta y la lista de tools disponibles, **decide** si llamar una (y con qué argumentos), recibe el resultado (**observación**) y vuelve a decidir hasta que puede responder. El LLM nunca ejecuta nada: solo **propone** llamadas; el runtime del agente las ejecuta con la identidad y los permisos que correspondan.
# MAGIC
# MAGIC <div style="display:flex; justify-content:center; margin:14px 0;">
# MAGIC <svg viewBox="0 0 760 250" style="max-width:760px; width:100%;" font-family="-apple-system,sans-serif">
# MAGIC   <defs><marker id="f" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#1B5162"/></marker></defs>
# MAGIC   <rect x="10" y="95" width="130" height="60" rx="12" fill="#EAF1FB" stroke="#2272B4" stroke-width="2"/>
# MAGIC   <text x="75" y="122" text-anchor="middle" font-size="14" font-weight="700" fill="#1B3139">Pregunta</text>
# MAGIC   <text x="75" y="141" text-anchor="middle" font-size="11" fill="#5A6F77">"¿Qué equipos…?"</text>
# MAGIC   <rect x="200" y="80" width="170" height="90" rx="14" fill="#fff" stroke="#1B3139" stroke-width="2.4"/>
# MAGIC   <text x="285" y="115" text-anchor="middle" font-size="15" font-weight="700" fill="#1B3139">LLM decide</text>
# MAGIC   <text x="285" y="136" text-anchor="middle" font-size="11" fill="#5A6F77">lee descripciones</text>
# MAGIC   <text x="285" y="152" text-anchor="middle" font-size="11" fill="#5A6F77">de las tools</text>
# MAGIC   <rect x="440" y="20" width="170" height="60" rx="12" fill="#FEF3E2" stroke="#FFAB00" stroke-width="2"/>
# MAGIC   <text x="525" y="46" text-anchor="middle" font-size="13" font-weight="700" fill="#1B3139">Llamada a tool</text>
# MAGIC   <text x="525" y="64" text-anchor="middle" font-size="11" fill="#5A6F77">incidencias_abiertas('P1')</text>
# MAGIC   <rect x="440" y="170" width="170" height="60" rx="12" fill="#E6F5EE" stroke="#00A972" stroke-width="2"/>
# MAGIC   <text x="525" y="196" text-anchor="middle" font-size="13" font-weight="700" fill="#1B3139">Observación</text>
# MAGIC   <text x="525" y="214" text-anchor="middle" font-size="11" fill="#5A6F77">22 filas · 4 columnas</text>
# MAGIC   <rect x="650" y="95" width="100" height="60" rx="12" fill="#1B3139"/>
# MAGIC   <text x="700" y="130" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">Respuesta</text>
# MAGIC   <path d="M140 125 L198 125" stroke="#1B5162" stroke-width="2" marker-end="url(#f)"/>
# MAGIC   <path d="M370 105 L438 60" stroke="#1B5162" stroke-width="2" marker-end="url(#f)"/>
# MAGIC   <path d="M525 80 L525 168" stroke="#1B5162" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#f)"/>
# MAGIC   <path d="M440 200 L372 150" stroke="#1B5162" stroke-width="2" marker-end="url(#f)"/>
# MAGIC   <path d="M370 125 L648 125" stroke="#1B5162" stroke-width="2" marker-end="url(#f)"/>
# MAGIC   <text x="560" y="118" font-size="10" fill="#5A6F77">cuando ya puede responder</text>
# MAGIC </svg>
# MAGIC </div>
# MAGIC
# MAGIC La consecuencia práctica: **el LLM elige la tool solo por su nombre, su descripción y la descripción de sus parámetros**. Una tool bien hecha pero mal descrita es invisible para el agente; por eso el reto de este lab es sobre el `COMMENT`.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### A.2 UC functions o MCP: cuándo usar cada uno
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
# MAGIC | | Unity Catalog function | MCP |
# MAGIC |---|---|---|
# MAGIC | Qué es | SQL o Python registrado en UC, con parámetros tipados | Protocolo estándar para descubrir y llamar tools de un servidor |
# MAGIC | Úsala cuando | La lógica es **predefinida** y el agente solo aporta parámetros | Necesitas un servidor con varias tools, APIs externas o tools que cualquier cliente (Genie Code, Claude Code, tu agente) pueda descubrir |
# MAGIC | Gobierno | `EXECUTE` en la función + permisos sobre las tablas | Permisos del MCP / de la app + Unity Gateway |
# MAGIC | En este lab | Sección B y el reto | Secciones C y D (y el Lab 2 completo) |
# MAGIC
# MAGIC Las dos cosas se combinan: Databricks publica tus UC functions como un **servidor MCP gestionado**, así que una misma función sirve para SQL, para tu agente en Python y para cualquier cliente MCP.
# MAGIC <p style="font-size:13px; color:#5A6F77;"><strong>Documentación:</strong> <a href="https://docs.databricks.com/aws/en/agents/" target="_blank" style="color:#2272B4;">Create agent tools using Unity Catalog functions</a></p>

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Tu primera tool: una UC function
# MAGIC
# MAGIC La función devuelve las incidencias abiertas (o en progreso) de una prioridad, con el equipo y las horas que llevan abiertas. Lee de la vista `incidencias_lab`, que calcula las horas contra una **fecha de corte fija** del laboratorio, para que todos obtengamos los mismos números.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### B.1 Crear la función
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
# MAGIC Fíjate en tres cosas: el `COMMENT` de cada parámetro, el `COMMENT` de la función y el nombre. Eso es lo que leerá el LLM.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOGO}.{MI_ESQUEMA}.incidencias_abiertas(
  prioridad STRING COMMENT 'Prioridad de la incidencia: P1, P2, P3 o P4'
)
RETURNS TABLE (id_incidencia STRING, descripcion STRING, equipo STRING, horas_abierta DOUBLE)
COMMENT 'Devuelve las incidencias abiertas o en progreso de una prioridad, con el equipo asignado y las horas que lleva abierta.'
RETURN SELECT id_incidencia, descripcion, equipo, round(horas_abierta, 1)
FROM {CATALOGO}.{ESQUEMA_DATOS}.incidencias_lab
WHERE estatus <> 'Cerrada' AND prioridad = incidencias_abiertas.prioridad
""")
print(f"✓ Función {CATALOGO}.{MI_ESQUEMA}.incidencias_abiertas creada")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### B.2 Probarla en SQL
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
# MAGIC Antes de dársela a un agente, comprueba que la lógica funciona por sí sola. Deberías ver **22** incidencias P1.

# COMMAND ----------

display(spark.sql(f"SELECT * FROM {CATALOGO}.{MI_ESQUEMA}.incidencias_abiertas('P1') ORDER BY horas_abierta DESC"))

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">También en el SQL editor</strong><br>Abre <b>SQL Editor</b> y corre <code>SELECT * FROM la_tinka_taller.ag_&lt;tu_usuario&gt;.incidencias_abiertas('P1')</code>. En <b>Catalog</b> → tu schema → <b>Functions</b> verás la función con su descripción.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## C. La función vista como MCP
# MAGIC
# MAGIC Databricks expone automáticamente las funciones de un schema como un **servidor MCP gestionado** en `<workspace>/api/2.0/mcp/functions/<catálogo>/<schema>`. No hay nada que desplegar: los permisos son los de Unity Catalog.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### C.1 Cómo habla un cliente MCP con un servidor
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
# MAGIC MCP (*Model Context Protocol*) es JSON-RPC sobre HTTP. Un cliente hace tres cosas: `initialize`, `tools/list` (descubrir nombre, descripción y esquema de parámetros de cada tool) y `tools/call` (ejecutar una con argumentos). Tu agente usa `tools/list` para armar el menú que ve el LLM y `tools/call` cuando el LLM elige.
# MAGIC
# MAGIC <div style="display:flex; justify-content:center; margin:12px 0;">
# MAGIC <svg viewBox="0 0 700 190" style="max-width:700px; width:100%;" font-family="-apple-system,sans-serif">
# MAGIC   <defs><marker id="g" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#1B5162"/></marker></defs>
# MAGIC   <rect x="10" y="20" width="150" height="150" rx="14" fill="#EAF1FB" stroke="#2272B4" stroke-width="2"/>
# MAGIC   <text x="85" y="90" text-anchor="middle" font-size="15" font-weight="700" fill="#1B3139">Agente</text>
# MAGIC   <text x="85" y="110" text-anchor="middle" font-size="11" fill="#5A6F77">(cliente MCP)</text>
# MAGIC   <rect x="540" y="20" width="150" height="150" rx="14" fill="#E6F5EE" stroke="#00A972" stroke-width="2"/>
# MAGIC   <text x="615" y="85" text-anchor="middle" font-size="14" font-weight="700" fill="#1B3139">Servidor MCP</text>
# MAGIC   <text x="615" y="105" text-anchor="middle" font-size="11" fill="#5A6F77">UC functions de</text>
# MAGIC   <text x="615" y="121" text-anchor="middle" font-size="11" fill="#5A6F77">ag_&lt;usuario&gt;</text>
# MAGIC   <path d="M160 45 L538 45" stroke="#1B5162" stroke-width="2" marker-end="url(#g)"/><text x="350" y="38" text-anchor="middle" font-size="12" fill="#1B3139">1 · initialize</text>
# MAGIC   <path d="M160 95 L538 95" stroke="#1B5162" stroke-width="2" marker-end="url(#g)"/><text x="350" y="88" text-anchor="middle" font-size="12" fill="#1B3139">2 · tools/list → nombre, descripción, parámetros</text>
# MAGIC   <path d="M160 145 L538 145" stroke="#1B5162" stroke-width="2" marker-end="url(#g)"/><text x="350" y="138" text-anchor="middle" font-size="12" fill="#1B3139">3 · tools/call {"prioridad": "P1"} → filas</text>
# MAGIC </svg>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### C.2 Lo que ve el LLM
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
# MAGIC Esta celda se conecta al MCP de tu schema y lista las tools. La columna **Descripción** es literalmente lo que el LLM recibe para decidir. El nombre incluye catálogo y schema (`catalogo__schema__funcion`).

# COMMAND ----------

print("URL del MCP de tus funciones:", URL_MCP_FUNCIONES)
tools_funciones = mcp_listar(URL_MCP_FUNCIONES, "uc-functions")
mostrar_tools(tools_funciones)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### C.3 Llamar la tool por MCP
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
# MAGIC Ahora la ejecutamos por el protocolo, como lo hará el agente: misma función, mismos permisos, resultado en JSON.

# COMMAND ----------

tool_p1 = next(t for t in tools_funciones if t.name.endswith("__incidencias_abiertas"))
resultado = correr(tool_p1.ainvoke({"prioridad": "P1"}))
texto = resultado if isinstance(resultado, str) else resultado[0]["text"] if isinstance(resultado, list) else str(resultado)
datos_p1 = json.loads(texto)
print(f"{len(datos_p1['rows'])} filas · columnas {datos_p1['columns']}")
datos_p1["rows"][:3]

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## D. MCP gestionados: Genie y Databricks SQL
# MAGIC
# MAGIC Además de tus funciones, Databricks publica servidores MCP listos para usar. Son la forma más rápida de darle a un agente acceso gobernado a los datos:
# MAGIC
# MAGIC | MCP gestionado | URL | Para qué |
# MAGIC |---|---|---|
# MAGIC | **Genie Agent MCP** | `/api/2.0/mcp/genie/<space_id>` | Preguntas en lenguaje natural sobre **un** espacio curado (el Genie "Mesa de servicio" que ya conocen) |
# MAGIC | **Genie One MCP** | servicio `system.ai.genie_one_mcp` | Preguntas sobre todo el workspace, con el contexto de Genie Ontology |
# MAGIC | **Databricks SQL MCP** | `/api/2.0/mcp/sql` | Ejecutar SQL concreto (incluye una variante de solo lectura) |
# MAGIC | **UC functions** | `/api/2.0/mcp/functions/<cat>/<schema>` | Tus funciones (sección C) |

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### D.1 El Genie que ya conocen, como tool
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
# MAGIC El Genie Agent MCP expone dos tools: una para preguntar y otra para consultar el resultado de una pregunta larga. Fíjate en que la descripción la genera Databricks a partir del espacio: por eso conviene que el espacio tenga buena descripción e instrucciones.

# COMMAND ----------

tools_genie = mcp_listar(URL_MCP_GENIE, "genie")
mostrar_tools(tools_genie)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### D.2 Databricks SQL como tool
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
# MAGIC El MCP de Databricks SQL deja que el agente escriba y ejecute SQL. Es potente y amplio: en el Lab 4 verás cómo se restringe (por ejemplo, exponer solo la variante de solo lectura).

# COMMAND ----------

tools_sql = mcp_listar(URL_MCP_SQL, "dbsql")
mostrar_tools(tools_sql)

# COMMAND ----------

# MAGIC %md
# MAGIC ## E. Un agente mínimo con LangGraph
# MAGIC
# MAGIC Juntamos todo: un LLM servido por Databricks y las tools de los tres MCP. El agente decide solo cuál usar. Activamos **MLflow Tracing** para ver cada decisión.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### E.1 Armar el agente
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
# MAGIC `create_agent` de LangChain/LangGraph implementa el ciclo de la sección A. El prompt de sistema describe el rol, no qué tool usar: queremos que el agente elija por las descripciones.

# COMMAND ----------

import mlflow
from langchain.agents import create_agent

mlflow.langchain.autolog()

PROMPT_SISTEMA = ("Eres el asistente de la mesa de servicio de TI de La Tinka. Responde en español, "
                  "de forma breve, e indica qué tools usaste.")
llm = modelo_chat()  # endpoint de Foundation Model APIs (ver Includes/Setup-Lab)


def armar_agente(tools):
    return create_agent(llm, tools=tools, system_prompt=PROMPT_SISTEMA)


def preguntar(agente, pregunta):
    r = correr(agente.ainvoke({"messages": [{"role": "user", "content": pregunta}]}), timeout=300)
    mostrar_conversacion(r["messages"])
    return r["messages"]


agente = armar_agente(tools_funciones + tools_genie)
print("Tools del agente:", [t.name for t in tools_funciones + tools_genie])

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### E.2 Preguntas que eligen tools distintas
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
# MAGIC La primera pregunta encaja con tu función. La segunda es una pregunta de negocio abierta: el agente debería ir a **Genie**.

# COMMAND ----------

mensajes = preguntar(agente, "¿Qué equipos tienen más P1 abiertas?")

# COMMAND ----------

mensajes = preguntar(agente, "¿Cómo evolucionó la satisfacción promedio de los últimos tres meses?")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### E.3 Leer la traza
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
# MAGIC Debajo de cada celda aparece la traza de MLflow. Ábrela y recorre:
# MAGIC 1. El **span del LLM**: qué tools tenía disponibles y qué decidió.
# MAGIC 2. El **span de la tool**: argumentos, resultado y latencia.
# MAGIC 3. Los **tokens** de entrada y salida de cada llamada.
# MAGIC
# MAGIC Las trazas quedan en el experimento del notebook (ícono de matraz en la barra derecha).

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">Sin código: AI Playground</strong><br><b>AI Playground</b> → elige un modelo con tools → <b>Tools</b> → <b>+ Add tool</b> → <i>Unity Catalog function</i> (tu función) y <i>Genie</i>. Pregunta "¿qué P1 están abiertas?" y verifica que llama a tu función.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## F. Reto: una regla de negocio que el LLM no puede adivinar
# MAGIC
# MAGIC En la mesa de servicio, una incidencia está **en riesgo de SLA** cuando cumple tres condiciones (regla de ejemplo para el lab):
# MAGIC 1. Sigue abierta o en progreso.
# MAGIC 2. Ya consumió al menos el **80 %** de sus `sla_horas`.
# MAGIC 3. **Todavía no vence.** Las que ya pasaron su SLA no están "en riesgo": están vencidas.
# MAGIC
# MAGIC Ni el LLM ni Genie conocen esta definición. Si les preguntas, aplican la suya y cada vez puede salir un número distinto. **Tu objetivo**: encapsular la regla en una UC function para que el agente dé siempre la respuesta correcta.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### F.1 Sin la regla
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
# MAGIC Hazle la pregunta al agente actual (tu función `incidencias_abiertas` y Genie). La celda calcula en SQL la respuesta correcta y la compara con lo que dijo el agente.

# COMMAND ----------

PREGUNTA_RETO = "¿Cuántas incidencias abiertas están en riesgo de incumplir su SLA?"
ESPERADO = spark.sql(f"""
SELECT count(*) FROM {CATALOGO}.{ESQUEMA_DATOS}.incidencias_lab
WHERE estatus <> 'Cerrada' AND horas_abierta >= sla_horas * 0.8 AND horas_abierta < sla_horas
""").first()[0]
_EN_LETRAS = {1: "una", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez"}


def _texto_final(mensajes):
    c = mensajes[-1].content
    return c if isinstance(c, str) else " ".join(p.get("text", "") for p in c if isinstance(p, dict))


def probar_reto():
    tools = mcp_listar(URL_MCP_FUNCIONES, "uc-functions") + tools_genie
    mensajes = preguntar(armar_agente(tools), PREGUNTA_RETO)
    texto = _texto_final(mensajes).lower()
    uso_regla = any(t.endswith("__incidencias_en_riesgo_sla") for t in tools_usadas(mensajes))
    acerto = bool(re.search(rf"(?<![\d.,]){ESPERADO}(?![\d.,])", texto)) or _EN_LETRAS.get(ESPERADO, "#") in texto
    filas = [("Usó tu función <code>incidencias_en_riesgo_sla</code>", uso_regla),
             (f"Respondió el número correcto (<b>{ESPERADO}</b>)", acerto)]
    html = "".join(f"<div style='font-size:15px;margin:4px 0'>{'✅' if ok_ else '❌'} {t}</div>" for t, ok_ in filas)
    if uso_regla and acerto:
        html += "<div style='font-size:16px;font-weight:700;color:#00A972;margin-top:6px'>✓ Reto logrado</div>"
    displayHTML(html)


probar_reto()

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">¿Acertó sin tu función?</strong><br>Puede pasar: el LLM a veces adivina una definición parecida. Vuelve a correr la celda y mira si el número se mantiene. Una regla de negocio no puede depender de la suerte.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### F.2 Escribe la regla
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
# MAGIC Completa la plantilla de abajo. El nombre y las columnas ya están; tú escribes:
# MAGIC - **`TU_CONDICION`**: la regla en SQL, comparando **columnas de cada incidencia**. Tienes `horas_abierta` (horas que lleva abierta), `sla_horas` (horas comprometidas) y el umbral en el parámetro `incidencias_en_riesgo_sla.umbral_pct` (80 por defecto). Son dos condiciones unidas con `AND`:
# MAGIC   1. Ya consumió al menos el umbral: `horas_abierta` contra `sla_horas` multiplicado por el porcentaje.
# MAGIC   2. Todavía no vence: `horas_abierta` contra `sla_horas`.
# MAGIC - **Los dos `COMMENT`**: qué significa "en riesgo" y para qué sirve el umbral. Explícale al LLM la definición: es lo único que sabrá de la regla.
# MAGIC
# MAGIC Al crear la función, la celda cuenta las filas y te avisa si la regla no da el número esperado. Cuando salga ✓, corre `probar_reto()` en la celda siguiente.
# MAGIC
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #FF3621; border-radius:10px; background:#FFF5F3; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#FF3621;">Un error común</strong><br><code>AND umbral_pct = 80</code> no filtra incidencias: compara el parámetro consigo mismo y siempre es verdadero, así que devuelve todas las abiertas. La condición tiene que usar <code>horas_abierta</code> y <code>sla_horas</code>.
# MAGIC </div>

# COMMAND ----------

# Reemplaza TU_CONDICION y las dos TU DESCRIPCIÓN
MI_FUNCION = f"""
CREATE OR REPLACE FUNCTION {CATALOGO}.{MI_ESQUEMA}.incidencias_en_riesgo_sla(
  umbral_pct DOUBLE DEFAULT 80 COMMENT 'TU DESCRIPCIÓN'
)
RETURNS TABLE (id_incidencia STRING, prioridad STRING, equipo STRING, horas_abierta DOUBLE, sla_horas INT, pct_sla_consumido DOUBLE)
COMMENT 'TU DESCRIPCIÓN'
RETURN SELECT id_incidencia, prioridad, equipo, round(horas_abierta, 1), sla_horas, round(100 * horas_abierta / sla_horas, 1)
FROM {CATALOGO}.{ESQUEMA_DATOS}.incidencias_lab
WHERE estatus <> 'Cerrada'
  AND TU_CONDICION
"""
if "TU_CONDICION" in MI_FUNCION or "TU DESCRIPCIÓN" in MI_FUNCION:
    print("✎ Todavía no editas la plantilla: reemplaza TU_CONDICION y las dos TU DESCRIPCIÓN y vuelve a correr la celda.")
else:
    spark.sql(MI_FUNCION)
    filas = spark.sql(f"SELECT * FROM {CATALOGO}.{MI_ESQUEMA}.incidencias_en_riesgo_sla() ORDER BY pct_sla_consumido DESC")
    display(filas)
    n = filas.count()
    if n == ESPERADO:
        print(f"✓ Función creada y la regla da {n} incidencias en riesgo. Corre la celda siguiente para probar el reto.")
    else:
        vencidas = filas.where("horas_abierta >= sla_horas").count()
        print(f"✗ La función devuelve {n} filas y la regla correcta da {ESPERADO}.")
        if vencidas:
            print(f"  {vencidas} de esas filas ya vencieron su SLA (horas_abierta >= sla_horas): falta la condición «todavía no vence».")
        print("  Revisa TU_CONDICION: debe comparar horas_abierta con sla_horas (lee la alerta de arriba) y vuelve a correr la celda.")

# COMMAND ----------

probar_reto()

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">Si te atoras</strong><br>La solución está en <code>soluciones/Lab 1 - Reto regla de negocio</code>. Prueba también <code>incidencias_en_riesgo_sla(50)</code>: el mismo agente responde otra pregunta ("¿y con un umbral del 50 %?") sin cambiar el código.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusión
# MAGIC
# MAGIC Construiste las tools de base del laboratorio: una **UC function** documentada, expuesta automáticamente por el **MCP de UC functions**, más el **Genie** que ya conocían y **Databricks SQL** como MCP gestionados. Armaste un agente mínimo que elige entre ellas solo por sus descripciones y viste en MLflow cada decisión.
# MAGIC
# MAGIC La idea que se queda: **la descripción es la interfaz** entre tu lógica y el LLM. En el **Lab 2** construirás tu propio servidor MCP en Databricks Apps para lógica que no es SQL (cálculo de SLA, una API interna) y en el **Lab 3** juntarás todo en un agente desplegado con memoria.
