"""Personaliza un proyecto creado con `agentbricks init` para el lab de La Tinka.

Uso (desde la carpeta del proyecto):  python3 aplicar_referencia.py <URL de tu app MCP>

1. Escribe agent/mcps.py para conectar tu MCP del Lab 2 (Databricks Apps) por URL.
2. Agrega a agent/agent.py un prompt de sistema en español (tools, memoria y fuentes).
3. Declara MCP_MESA_SERVICIO_URL en app.yaml (despliegue) y en .env (agentbricks dev).
Se puede correr varias veces: no duplica nada.
"""

import pathlib
import sys

MCPS = '''"""Servidores MCP que el agente usa además de los declarados en agent.toml.

El MCP del Lab 2 vive en Databricks Apps. Unity Gateway no registra apps como MCP services,
así que el agente se conecta directo a su URL (app + /mcp). Desplegado, la llamada sale con la
identidad del service principal del agente: dale CAN USE sobre la app del MCP.
"""

import os

from databricks_langchain import DatabricksMCPServer

from databricks_agentkit import workspace_client


def build_mcp_servers() -> list[DatabricksMCPServer]:
    url = os.getenv("MCP_MESA_SERVICIO_URL", "").strip().rstrip("/")
    if not url:
        return []
    return [
        DatabricksMCPServer(
            name="mcp_mesa_servicio",
            url=url if url.endswith("/mcp") else url + "/mcp",
            workspace_client=workspace_client(),
        )
    ]
'''

PROMPT = '''
SYSTEM_PROMPT = """Eres el asistente de la mesa de servicio de TI de La Tinka. Responde siempre en español.
- Para incidencias abiertas por prioridad usa la función incidencias_abiertas.
- Para preguntas de negocio en lenguaje natural (tendencias, comparaciones, SLA histórico) usa Genie.
- Para el estado de SLA de una incidencia o el estado de un juego usa el MCP de la mesa de servicio.
- Para cálculos o gráficos sobre resultados usa el sandbox.
- Antes de responder la primera pregunta de una conversación usa recall para revisar las preferencias guardadas del usuario y respétalas.
- Si el usuario te pide recordar algo, guárdalo con remember.
Al final indica qué fuentes (tools) usaste."""
'''


def main():
    if len(sys.argv) != 2 or not sys.argv[1].startswith("https://"):
        sys.exit("Uso: python3 aplicar_referencia.py https://mcp-<usuario>-....databricksapps.com")
    url = sys.argv[1].rstrip("/")
    raiz = pathlib.Path(".")
    agente = raiz / "agent" / "agent.py"
    if not agente.exists() or not (raiz / "agent.toml").exists():
        sys.exit("Corre este script dentro de la carpeta creada por `agentbricks init`.")

    (raiz / "agent" / "mcps.py").write_text(MCPS, encoding="utf-8")

    codigo = agente.read_text(encoding="utf-8")
    if "SYSTEM_PROMPT" not in codigo:
        marca = next(l for l in codigo.splitlines() if l.startswith("MODEL = "))
        codigo = codigo.replace(marca, marca + "\n" + PROMPT, 1)
        codigo = codigo.replace("        tools=tools,\n", "        tools=tools,\n        system_prompt=SYSTEM_PROMPT,\n", 1)
        agente.write_text(codigo, encoding="utf-8")

    app_yaml = raiz / "app.yaml"
    texto = app_yaml.read_text(encoding="utf-8")
    if "MCP_MESA_SERVICIO_URL" not in texto:
        lineas = texto.rstrip("\n").split("\n")
        if "env:" in lineas:  # app.yaml ya reescrito por un deploy: agrega a la lista existente
            i = lineas.index("env:")
            sangria = "  " if i + 1 < len(lineas) and lineas[i + 1].startswith("  -") else ""
            lineas[i + 1:i + 1] = [f"{sangria}- name: MCP_MESA_SERVICIO_URL", f'{sangria}  value: "{url}"']
        else:
            lineas += ["env:", "  - name: MCP_MESA_SERVICIO_URL", f'    value: "{url}"']
        app_yaml.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    env = raiz / ".env"
    actual = env.read_text(encoding="utf-8") if env.exists() else ""
    if "MCP_MESA_SERVICIO_URL" not in actual:
        env.write_text(actual.rstrip("\n") + f"\nMCP_MESA_SERVICIO_URL={url}\n", encoding="utf-8")

    print("✓ agent/mcps.py, prompt en agent/agent.py, app.yaml y .env listos")


if __name__ == "__main__":
    main()
