# Databricks notebook source
# MAGIC %md
# MAGIC # Setup común de los labs
# MAGIC Lo ejecuta cada notebook con `%run ./Includes/Setup-Lab`. Calcula tus nombres de recursos, crea tu schema si
# MAGIC falta y deja listas las variables y funciones auxiliares que usan los labs. No necesitas abrirlo.

# COMMAND ----------

import json, os, re, time, asyncio, threading
from databricks.sdk import WorkspaceClient

_RUTA_CONFIG = next(r for r in ("Includes/_config.py", "../Includes/_config.py") if os.path.exists(r))
exec(open(_RUTA_CONFIG, encoding="utf-8").read())  # define CONFIG_LAB (lo escribe el setup)

w = WorkspaceClient()
HOST = w.config.host.rstrip("/")
YO = spark.sql("SELECT current_user()").first()[0]

CATALOGO = CONFIG_LAB["catalogo"]
ESQUEMA_DATOS = CONFIG_LAB["esquema_datos"]
GENIE_ID = CONFIG_LAB["genie_id"]
WAREHOUSE_ID = CONFIG_LAB["warehouse_id"]
MODELO = CONFIG_LAB["modelo"]                       # p. ej. claude-sonnet-4-5
MODELO_ENDPOINT = f"databricks-{MODELO}"             # endpoint de Foundation Model APIs
MODELO_SYSTEM = f"system.ai.{MODELO}"                # model service de Unity Gateway
MODELO_UC = CONFIG_LAB.get("modelo_uc", f"databricks-{MODELO}")            # modelo en system.ai (destino)
RESPALDO_UC = CONFIG_LAB.get("modelo_respaldo_uc", MODELO_UC)             # destino de respaldo (fallback)
FECHA_CORTE = CONFIG_LAB["fecha_corte"]

# Tus nombres: la parte local del correo, en minúsculas
SLUG = re.sub(r"[^a-z0-9]+", "_", YO.split("@")[0].lower()).strip("_")[:40]
SLUG_APP = SLUG.replace("_", "-")
MI_ESQUEMA = f"ag_{SLUG}"
MCP_APP = f"mcp-{SLUG_APP}"[:30].rstrip("-")                 # app del Lab 2
AGENTE = f"ag-{SLUG_APP}"[:17].rstrip("-")                   # el CLI crea la app agent-bricks-<AGENTE>
AGENTE_APP = f"agent-bricks-{AGENTE}"
MODELO_SERVICIO = f"{CATALOGO}.{MI_ESQUEMA}.modelo_agente"   # model service del Lab 4
CARPETA_MCP = f"/Workspace/Users/{YO}/lab-agentes/mcp-server"

# URLs de los MCP gestionados
URL_MCP_FUNCIONES = f"{HOST}/api/2.0/mcp/functions/{CATALOGO}/{MI_ESQUEMA}"
URL_MCP_GENIE = f"{HOST}/api/2.0/mcp/genie/{GENIE_ID}"
URL_MCP_SQL = f"{HOST}/api/2.0/mcp/sql"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOGO}`.`{MI_ESQUEMA}` COMMENT 'Espacio de {YO} en el lab de agentes'")
spark.sql(f"USE CATALOG `{CATALOGO}`")
spark.sql(f"USE SCHEMA `{MI_ESQUEMA}`")


# Un único event loop en segundo plano: los clientes async (MCP, LLM) sobreviven entre celdas
if "_LOOP_LAB" not in globals() or _LOOP_LAB.is_closed():
    _LOOP_LAB = asyncio.new_event_loop()
    threading.Thread(target=_LOOP_LAB.run_forever, daemon=True).start()


def correr(coro, timeout=180):
    """Ejecuta una corrutina en el loop del lab y devuelve su resultado."""
    return asyncio.run_coroutine_threadsafe(asyncio.wait_for(coro, timeout), _LOOP_LAB).result(timeout + 15)


def token():
    """Token de tu sesión (el notebook lo renueva solo)."""
    return w.config.authenticate()["Authorization"].split(" ", 1)[1]


def mcp_cliente(servidores):
    """Cliente MCP para varios servidores: {"nombre": "url", ...}."""
    from langchain_mcp_adapters.client import MultiServerMCPClient
    cabecera = {"Authorization": f"Bearer {token()}"}
    return MultiServerMCPClient({n: {"transport": "streamable_http", "url": u, "headers": cabecera}
                                 for n, u in servidores.items()})


def mcp_listar(url, nombre="mcp"):
    """Lista las tools de un MCP como las ve el LLM: nombre, descripción y parámetros."""
    return correr(mcp_cliente({nombre: url}).get_tools())


def modelo_chat(modelo=None, gateway=False):
    """LLM compatible con OpenAI servido por Databricks.

    gateway=False: endpoint de Foundation Model APIs (p. ej. databricks-claude-sonnet-4-5).
    gateway=True: model service de Unity Gateway (p. ej. tu catálogo.schema.modelo_agente).
    """
    from langchain_openai import ChatOpenAI
    base = f"{HOST}/ai-gateway/mlflow/v1" if gateway else f"{HOST}/serving-endpoints"
    return ChatOpenAI(model=modelo or MODELO_ENDPOINT, base_url=base, api_key=token())


def sandbox_disponible():
    """True si el workspace tiene Databricks Sandbox (system.ai.sandbox). Es opcional: sin él, el agente no tiene run_code."""
    try:
        w.api_client.do("GET", "/api/2.1/unity-catalog/mcp-services/system.ai.sandbox")
        return True
    except Exception:
        return False


def mostrar_tools(tools):
    filas = "".join(
        f"<tr><td style='padding:6px 10px;border-top:1px solid #ECEAE6'><code>{t.name}</code></td>"
        f"<td style='padding:6px 10px;border-top:1px solid #ECEAE6'>{(t.description or '')[:220]}</td>"
        f"<td style='padding:6px 10px;border-top:1px solid #ECEAE6'><code>{', '.join((t.args_schema if isinstance(t.args_schema, dict) else t.args_schema.model_json_schema()).get('properties', {}).keys())}</code></td></tr>"
        for t in tools)
    displayHTML("<table style='border-collapse:collapse;font-family:-apple-system,Segoe UI,sans-serif;font-size:13px'>"
                "<tr style='background:#F9F7F4'><th align=left style='padding:6px 10px'>Tool</th>"
                "<th align=left style='padding:6px 10px'>Descripción que lee el LLM</th>"
                f"<th align=left style='padding:6px 10px'>Parámetros</th></tr>{filas}</table>")


def mostrar_conversacion(mensajes):
    """Muestra paso a paso qué tools llamó el agente y con qué argumentos."""
    bloques = []
    for m in mensajes:
        tipo = m.__class__.__name__
        llamadas = getattr(m, "tool_calls", None) or []
        if tipo == "HumanMessage":
            bloques.append(f"<div style='background:#EAF1FB;padding:8px 12px;border-radius:8px;margin:6px 0'><b>Pregunta:</b> {m.content}</div>")
        elif llamadas:
            for c in llamadas:
                bloques.append(f"<div style='border-left:4px solid #FFAB00;padding:6px 12px;margin:6px 0'>🛠️ <b>{c['name']}</b> "
                               f"<code>{json.dumps(c['args'], ensure_ascii=False)}</code></div>")
        elif tipo == "ToolMessage":
            texto = m.content if isinstance(m.content, str) else json.dumps(m.content, ensure_ascii=False)
            bloques.append(f"<div style='color:#5A6F77;font-size:12px;padding:2px 12px 2px 26px'>↳ {texto[:260]}…</div>")
        elif tipo == "AIMessage" and m.content:
            texto = m.content if isinstance(m.content, str) else " ".join(p.get("text", "") for p in m.content if isinstance(p, dict))
            bloques.append(f"<div style='background:#E6F5EE;padding:8px 12px;border-radius:8px;margin:6px 0;white-space:pre-wrap'><b>Respuesta:</b>\n{texto}</div>")
    displayHTML("<div style='font-family:-apple-system,Segoe UI,sans-serif;font-size:14px'>" + "".join(bloques) + "</div>")


def tools_usadas(mensajes):
    return [c["name"] for m in mensajes for c in (getattr(m, "tool_calls", None) or [])]


displayHTML(f"""
<div style="font-family:-apple-system,Segoe UI,sans-serif;border:1px solid #DCE0E2;border-radius:10px;padding:12px 16px;color:#1B3139;font-size:14px">
<b>Listo, {YO}.</b> Estos son tus recursos en el laboratorio:
<table style="margin-top:6px;border-collapse:collapse">
<tr><td style="padding:2px 12px 2px 0">Tu schema</td><td><code>{CATALOGO}.{MI_ESQUEMA}</code></td></tr>
<tr><td style="padding:2px 12px 2px 0">Datos</td><td><code>{CATALOGO}.{ESQUEMA_DATOS}</code> (vista <code>incidencias_lab</code>, corte {FECHA_CORTE})</td></tr>
<tr><td style="padding:2px 12px 2px 0">Genie</td><td><code>{GENIE_ID}</code></td></tr>
<tr><td style="padding:2px 12px 2px 0">Modelo</td><td><code>{MODELO_ENDPOINT}</code> · <code>{MODELO_SYSTEM}</code></td></tr>
<tr><td style="padding:2px 12px 2px 0">App MCP (Lab 2)</td><td><code>{MCP_APP}</code></td></tr>
<tr><td style="padding:2px 12px 2px 0">Agente (Lab 3)</td><td><code>{AGENTE}</code> → app <code>{AGENTE_APP}</code></td></tr>
</table></div>""")
