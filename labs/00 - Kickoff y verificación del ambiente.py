# Databricks notebook source
# MAGIC %md
# MAGIC # Laboratorio de Agentes en Databricks · Kickoff
# MAGIC #### Duración: 15 minutos

# COMMAND ----------

# MAGIC %md
# MAGIC ## Panorama
# MAGIC
# MAGIC Hoy construimos un agente **de abajo hacia arriba**: primero las *tools*, después un *servidor MCP* propio, luego el *agente* con memoria y, al final, el *gobierno* con Unity Gateway. Todo sobre la mesa de servicio de TI de La Tinka que ya conocen del taller de iniciación.
# MAGIC
# MAGIC | Bloque | Qué construyes | Notebook |
# MAGIC |---|---|---|
# MAGIC | Lab 1 · Tools | UC function + Genie + Databricks SQL como tools vía MCP | `01 - Lab 1` |
# MAGIC | Lab 2 · MCP propio | Servidor MCP en Databricks Apps con tools de negocio | `02 - Lab 2` |
# MAGIC | Lab 3 · Agente | Agente con Agent Bricks: tools, sandbox, memoria, trazas, despliegue | `03A` (CLI en laptop) o `03B` (navegador) |
# MAGIC | Lab 4 · Gobierno | Model service, rate limits, guardrails de PII y uso en tablas de sistema | `04 - Lab 4` |
# MAGIC
# MAGIC Este notebook ubica cada pieza en el portafolio y **verifica que tu ambiente está listo**.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Objetivos de aprendizaje
# MAGIC
# MAGIC - **Ubicar** Genie Agents, Agent Bricks y Unity Gateway en el portafolio de agentes de Databricks.
# MAGIC - **Reconocer** qué es GA, qué es Beta y qué es legacy hoy.
# MAGIC - **Verificar** que tienes acceso a los datos, al Genie, a los MCP gestionados y al modelo del laboratorio.

# COMMAND ----------

# MAGIC %run ./Includes/Setup-Lab

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. El portafolio de agentes en Databricks

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### A.1 Tres piezas, un recorrido
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
# MAGIC   <div style="flex:1 1 230px; background:#fff; border:1px solid #ECEAE6; border-top:4px solid #2272B4; border-radius:12px; padding:14px 16px;">
# MAGIC     <h4 style="margin:0 0 6px;">Genie Agents</h4>
# MAGIC     <p style="font-size:14px; margin:0;">Agentes <b>sin código</b> sobre tablas y documentos, para usuarios de negocio. Ya los conocen: hoy Genie es <b>una tool</b> que nuestro agente puede llamar.</p>
# MAGIC   </div>
# MAGIC   <div style="flex:1 1 230px; background:#fff; border:1px solid #ECEAE6; border-top:4px solid #00A972; border-radius:12px; padding:14px 16px;">
# MAGIC     <h4 style="margin:0 0 6px;">Agent Bricks</h4>
# MAGIC     <p style="font-size:14px; margin:0;">Plataforma para quien <b>escribe código</b>: cualquier framework (LangGraph, OpenAI Agents SDK), cualquier modelo. Agent Runtime, sandbox, memoria, sesiones y MLflow Tracing.</p>
# MAGIC   </div>
# MAGIC   <div style="flex:1 1 230px; background:#fff; border:1px solid #ECEAE6; border-top:4px solid #FF3621; border-radius:12px; padding:14px 16px;">
# MAGIC     <h4 style="margin:0 0 6px;">Unity Gateway</h4>
# MAGIC     <p style="font-size:14px; margin:0;">Antes AI Gateway. El <b>plano de control</b>: model services, MCPs y skills como securables de Unity Catalog, con rate limits, guardrails y uso en <code>system.ai_gateway.usage</code>.</p>
# MAGIC   </div>
# MAGIC </div>
# MAGIC
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #1B5162; border-radius:10px; background:#F9F7F4; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#1B5162;">Qué es legacy</strong><br><b>Knowledge Assistant</b> y <b>Supervisor Agent</b> aparecen como <i>legacy</i> en la documentación. La ruta "custom agents on Apps" con MLflow AgentServer también: para agentes nuevos se recomienda el <b>Agent Bricks CLI</b>.
# MAGIC </div>
# MAGIC <div style="border:1px solid #DCE0E2; border-left:4px solid #FF3621; border-radius:10px; background:#FFF5F3; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
# MAGIC <strong style="color:#FF3621;">Beta</strong><br>El Agent Bricks CLI, Databricks Sandbox, la memoria de agentes, Unity Gateway Skills y las Service Policies están en <b>Beta</b>. Hoy los usamos para un <b>prototipo acotado</b>, no como migración productiva.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### A.2 La arquitectura del laboratorio
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
# MAGIC <svg viewBox="0 0 820 300" style="max-width:820px; width:100%;" font-family="-apple-system,sans-serif">
# MAGIC   <defs><marker id="k" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#1B5162"/></marker></defs>
# MAGIC   <rect x="10" y="10" width="800" height="280" rx="16" fill="#F9F7F4" stroke="#90A5B1" stroke-dasharray="6 4"/>
# MAGIC   <text x="26" y="34" font-size="12" fill="#303F47">Unity Catalog · la_tinka_taller</text>
# MAGIC   <rect x="30" y="60" width="190" height="80" rx="10" fill="#fff" stroke="#1B5162" stroke-width="2"/>
# MAGIC   <text x="125" y="88" text-anchor="middle" font-size="13" font-weight="700" fill="#1B3139">mesa_servicio</text>
# MAGIC   <text x="125" y="106" text-anchor="middle" font-size="11" fill="#5A6F77">incidencias · equipos · SLA</text>
# MAGIC   <text x="125" y="122" text-anchor="middle" font-size="11" fill="#5A6F77">encuestas · proyectos</text>
# MAGIC   <rect x="30" y="180" width="190" height="80" rx="10" fill="#fff" stroke="#00A972" stroke-width="2"/>
# MAGIC   <text x="125" y="208" text-anchor="middle" font-size="13" font-weight="700" fill="#1B3139">ag_&lt;tu usuario&gt;</text>
# MAGIC   <text x="125" y="226" text-anchor="middle" font-size="11" fill="#5A6F77">tus UC functions (Lab 1)</text>
# MAGIC   <text x="125" y="242" text-anchor="middle" font-size="11" fill="#5A6F77">tu model service (Lab 4)</text>
# MAGIC   <rect x="300" y="45" width="170" height="54" rx="10" fill="#EAF1FB" stroke="#2272B4" stroke-width="2"/>
# MAGIC   <text x="385" y="77" text-anchor="middle" font-size="12" font-weight="700" fill="#1B3139">Genie "Mesa de servicio"</text>
# MAGIC   <rect x="300" y="123" width="170" height="54" rx="10" fill="#E6F5EE" stroke="#00A972" stroke-width="2"/>
# MAGIC   <text x="385" y="148" text-anchor="middle" font-size="12" font-weight="700" fill="#1B3139">MCP gestionados</text>
# MAGIC   <text x="385" y="164" text-anchor="middle" font-size="10" fill="#5A6F77">UC functions · Genie · SQL</text>
# MAGIC   <rect x="300" y="201" width="170" height="54" rx="10" fill="#FEF3E2" stroke="#FFAB00" stroke-width="2"/>
# MAGIC   <text x="385" y="226" text-anchor="middle" font-size="12" font-weight="700" fill="#1B3139">mcp-&lt;usuario&gt;</text>
# MAGIC   <text x="385" y="242" text-anchor="middle" font-size="10" fill="#5A6F77">Databricks Apps (Lab 2)</text>
# MAGIC   <rect x="540" y="100" width="150" height="100" rx="14" fill="#1B3139"/>
# MAGIC   <text x="615" y="140" text-anchor="middle" font-size="14" font-weight="700" fill="#fff">Tu agente</text>
# MAGIC   <text x="615" y="160" text-anchor="middle" font-size="11" fill="#DCE0E2">Agent Bricks (Lab 3)</text>
# MAGIC   <text x="615" y="176" text-anchor="middle" font-size="11" fill="#DCE0E2">sandbox · memoria</text>
# MAGIC   <rect x="720" y="100" width="76" height="100" rx="10" fill="#fff" stroke="#FF3621" stroke-width="2"/>
# MAGIC   <text x="758" y="140" text-anchor="middle" font-size="11" font-weight="700" fill="#1B3139">Unity</text>
# MAGIC   <text x="758" y="156" text-anchor="middle" font-size="11" font-weight="700" fill="#1B3139">Gateway</text>
# MAGIC   <text x="758" y="174" text-anchor="middle" font-size="10" fill="#5A6F77">(Lab 4)</text>
# MAGIC   <path d="M220 100 L298 72" stroke="#1B5162" stroke-width="1.6" marker-end="url(#k)"/>
# MAGIC   <path d="M220 215 L298 155" stroke="#1B5162" stroke-width="1.6" marker-end="url(#k)"/>
# MAGIC   <path d="M470 72 L538 125" stroke="#1B5162" stroke-width="1.6" marker-end="url(#k)"/>
# MAGIC   <path d="M470 150 L538 150" stroke="#1B5162" stroke-width="1.6" marker-end="url(#k)"/>
# MAGIC   <path d="M470 228 L538 178" stroke="#1B5162" stroke-width="1.6" marker-end="url(#k)"/>
# MAGIC   <path d="M690 150 L718 150" stroke="#1B5162" stroke-width="1.6" marker-end="url(#k)"/>
# MAGIC </svg>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Verificación del ambiente

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### B.1 ¿Está todo listo para ti?
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
# MAGIC La celda revisa, con **tu** usuario, cada cosa que necesitarás. Si algo sale en rojo, avísale al instructor antes de seguir.

# COMMAND ----------

import requests
chequeos = []


def chequear(nombre, funcion):
    try:
        chequeos.append((nombre, True, funcion()))
    except Exception as e:
        chequeos.append((nombre, False, str(e)[:180]))


chequear("Tu schema", lambda: spark.sql(f"SHOW FUNCTIONS IN `{CATALOGO}`.`{MI_ESQUEMA}`").count() >= 0 and f"{CATALOGO}.{MI_ESQUEMA}")
chequear("Datos de la mesa de servicio", lambda: f"{spark.table(f'{CATALOGO}.{ESQUEMA_DATOS}.incidencias_lab').count():,} incidencias")
chequear("Crear funciones en tu schema", lambda: spark.sql(
    f"CREATE OR REPLACE FUNCTION `{CATALOGO}`.`{MI_ESQUEMA}`.ping() RETURNS STRING RETURN 'ok'").count() >= 0 and "ok")
chequear("Genie (MCP)", lambda: ", ".join(t["name"] for t in w.api_client.do(
    "POST", f"/api/2.0/mcp/genie/{GENIE_ID}", body={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]))
chequear("Databricks SQL (MCP)", lambda: ", ".join(t["name"] for t in w.api_client.do(
    "POST", "/api/2.0/mcp/sql", body={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]))
chequear("Modelo", lambda: w.api_client.do("POST", f"/serving-endpoints/{MODELO_ENDPOINT}/invocations", body={
    "messages": [{"role": "user", "content": "Responde solo: listo"}], "max_tokens": 10})["choices"][0]["message"]["content"])
chequear("Databricks Apps", lambda: f"puedes listar apps ({len(list(w.apps.list()))} en el workspace)")
spark.sql(f"DROP FUNCTION IF EXISTS `{CATALOGO}`.`{MI_ESQUEMA}`.ping")

filas = "".join(f"<tr><td style='padding:5px 12px'>{n}</td><td style='padding:5px 12px;font-weight:700;color:{'#00A972' if okk else '#FF3621'}'>"
                f"{'✓' if okk else '✗'}</td><td style='padding:5px 12px;font-size:12px'>{d}</td></tr>" for n, okk, d in chequeos)
displayHTML(f"<table style='font-family:-apple-system,Segoe UI,sans-serif;font-size:14px;border-collapse:collapse'>{filas}</table>")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### B.2 Solo versión A: tu laptop
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
# MAGIC Si vas a hacer el **Lab 3 con el CLI**, corre esto en tu terminal antes de la pausa. Cambia `<perfil>` por un nombre corto (por ejemplo `tinka`).
# MAGIC
# MAGIC ```bash
# MAGIC # 1. Python 3.12+ y uv
# MAGIC python3 --version && uv --version
# MAGIC
# MAGIC # 2. Databricks CLI con login OAuth a este workspace
# MAGIC databricks auth login --host <URL del workspace> --profile <perfil>
# MAGIC
# MAGIC # 3. Agent Bricks CLI (Beta): la versión validada para el lab
# MAGIC uv tool install databricks-agentbricks==0.9.0
# MAGIC agentbricks --version
# MAGIC agentbricks login --profile <perfil>
# MAGIC ```
# MAGIC
# MAGIC Si algo falla (proxy, permisos de instalación), no te preocupes: haz el Lab 3 en su **versión B**, desde el navegador.

# COMMAND ----------

displayHTML(f"<div style='font-size:15px'>URL del workspace para el login: <code>{HOST}</code></div>")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Siguiente paso
# MAGIC
# MAGIC Abre **`01 - Lab 1 - Tools con UC functions y MCP`**.
