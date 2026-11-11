"""Servidores MCP que el agente usa además de los declarados en agent.toml.

El MCP del Lab 2 vive en Databricks Apps. Unity Gateway no registra apps como MCP services,
así que el agente se conecta directo a su URL (app + /mcp). Desplegado, la llamada sale con la
identidad del service principal del agente: dale CAN USE sobre la app del MCP.
"""

import os

from databricks_langchain import DatabricksMCPServer

from databricks_agentkit import workspace_client


def build_mcp_servers() -> list[DatabricksMCPServer]:
    url = os.getenv("MCP_MESA_SERVICIO_URL", "").strip()
    if not url:
        return []
    return [
        DatabricksMCPServer(
            name="mcp_mesa_servicio",
            url=url.rstrip("/") + ("" if url.rstrip("/").endswith("/mcp") else "/mcp"),
            workspace_client=workspace_client(),
        )
    ]
