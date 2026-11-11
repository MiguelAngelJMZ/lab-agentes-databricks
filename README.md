# Laboratorio de Agentes en Databricks – La Tinka

Laboratorio técnico (2–3 h) para construir agentes en Databricks de abajo hacia arriba: **tools → MCP → agente → gobierno**, sobre el dataset de la mesa de servicio de TI del taller de iniciación. Fecha: **26 de noviembre de 2026**.

## Contenido

| Carpeta / archivo | Qué es |
|---|---|
| `setup/00_setup_lab` | **El único notebook que corre la persona administradora** (una vez, días antes). Valida el ambiente, reutiliza o crea datos y Genie, da permisos al grupo y deja a cada participante su schema y su copia de los notebooks |
| `setup/99_limpieza` | Borra lo que crearon los participantes (simular → borrar) |
| `labs/00 … 05` | Notebooks del laboratorio (estilo *lecture + demo*, en español) |
| `labs/Includes/` | Setup común de los labs (`Setup-Lab`) y la configuración que escribe el setup (`_config.py`) |
| `labs/mcp-server/` | Servidor MCP de la mesa de servicio (plantilla oficial *MCP Server Starter* + tools de negocio) |
| `labs/agente-referencia/` | `aplicar_referencia.py`: conecta el MCP y agrega el prompt en español al proyecto de `agentbricks init` |
| `labs/soluciones/` | Soluciones de los retos de los Labs 1 y 2 |
| `materiales/guia_participante.html` | Para enviar por correo: instalación de la laptop (versión A) y cómo empezar |
| `herramientas/` | Fuentes compactas de los notebooks y el script que los genera (`python3 herramientas/construir_notebooks.py`) |

## Puesta en marcha (resumen)

1. Crear el grupo de participantes y activar los previews (*Managed MCP Servers*, *Databricks Sandbox*, *Unity Gateway Service Policies*).
2. Importar esta carpeta al workspace (con `setup/` y `labs/` como hermanas).
3. Correr `setup/00_setup_lab` en Serverless con `grupo_participantes` → *Run all*.
4. Ensayar con un usuario no admin: correr los Labs 0 → 4 y medir tiempos.

## Dos versiones del Lab 3

- **03A · CLI en la laptop:** `agentbricks init → tools add → dev → deploy` (requiere Python 3.12+, uv, Databricks CLI con OAuth y `databricks-agentbricks==0.9.0`).
- **03B · Navegador:** el mismo Agent Bricks CLI corriendo dentro de un notebook serverless. Sin instalaciones.
