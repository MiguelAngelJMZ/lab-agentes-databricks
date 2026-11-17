# Laboratorio de Agentes en Databricks – La Tinka

Todo lo necesario para el laboratorio técnico del **26 de noviembre de 2026** (2 a 3 horas): construir agentes en Databricks de abajo hacia arriba, **tools → MCP → agente → gobierno**, sobre el dataset de la mesa de servicio de TI del taller de iniciación.

```
lab-agentes-databricks/
├── setup/00_setup_lab                   Notebook que deja listo todo el laboratorio (lo corre el admin)
├── setup/99_limpieza                    Notebook que borra lo de todos los participantes después del taller
├── setup/recursos/                      Generadores de datos y del Genie (los usa el setup)
├── labs/                                Notebooks del lab: el setup los copia a cada participante
│   ├── 00 … 05                          Kickoff y Labs 1 a 4 (+ evaluación opcional)
│   ├── 99 - Limpiar mis recursos…       Cada participante borra solo lo que construyó
│   ├── Includes/                        Setup común de los labs y la configuración que escribe el setup
│   ├── mcp-server/                      Servidor MCP de la mesa de servicio (Lab 2)
│   ├── agente-referencia/               Script que conecta el MCP y el prompt al agente (Lab 3)
│   └── soluciones/                      Soluciones de los retos de los Labs 1 y 2
├── materiales/guia_participante.html    Para enviar por correo: cómo prepararse y cómo empezar
└── herramientas/                        Fuentes de los notebooks y el script que los genera
```

El material del instructor (guía con guion y respuestas esperadas, y presentación) no está en este repositorio.

## Qué construye cada participante

| Notebook | Lab | Qué construye | Tiempo |
|---|---|---|---|
| `00 - Kickoff y verificación del ambiente` | — | Verifica que su ambiente esté listo | 15 min |
| `01 - Lab 1 - Tools con UC functions y MCP` | Tools | Una UC function, el Genie y Databricks SQL como tools vía MCP, y un agente mínimo | 30 min |
| `02 - Lab 2 - Servidor MCP propio en Databricks Apps` | MCP | Su servidor MCP `mcp-<usuario>` en Databricks Apps | 40 min |
| `03A` (laptop) o `03B` (navegador) - Lab 3 | Agente | Su agente con Agent Bricks: tools, memoria, sesiones y trazas, desplegado como app | 50 min |
| `04 - Lab 4 - Gobierno con Unity Gateway` | Gobierno | Fallback, rate limit y guardrails de PII y jailbreak sobre el modelo de su agente | 25 min |
| `05 - Opcional - Evaluación del agente con MLflow` | Opcional | Evaluación del agente con `mlflow.genai.evaluate()` | 45 min |

**Dos versiones del Lab 3:**
- **03A · CLI en la laptop:** `agentbricks init → tools add → dev → deploy`. Requiere Python 3.12+, uv, Databricks CLI con login OAuth y `databricks-agentbricks==0.9.0` (ver `materiales/guia_participante.html`).
- **03B · Navegador:** el mismo Agent Bricks CLI corriendo dentro de un notebook serverless. No hay que instalar nada.

## Preparar el laboratorio en el workspace de La Tinka

**Antes de empezar**, el equipo de La Tinka necesita:

1. Un workspace con **Unity Catalog**, **Serverless** (notebooks y SQL Warehouse) y **Databricks Apps** habilitados.
2. Un **grupo de cuenta** con los participantes (por ejemplo `lab_agentes`), asignado al workspace. Cada participante debe haber iniciado sesión al menos una vez.
3. Estos **previews** activos en **Settings → Previews**:

   | Preview | Para qué |
   |---|---|
   | Managed MCP Servers | Labs 1 a 3: UC functions, Genie y Databricks SQL como tools |
   | Agent Memory Sessions | Lab 3: memoria y sesiones del agente |
   | Unity Gateway Service Policies | Lab 4: guardrails de PII y jailbreak |
   | Databricks Sandbox *(opcional)* | Lab 3: que el agente ejecute código. En algunas regiones no está disponible; el lab funciona sin él |

4. Que el cómputo serverless tenga **salida a internet** (PyPI y GitHub): el Lab 3B descarga ahí sus paquetes y el Databricks CLI.
5. Que la persona que corra el setup sea **administradora del workspace**.

**Pasos:**

1. En el workspace, ir a **Workspace → Create → Git folder**.
2. En *Git repository URL* pegar `https://github.com/MiguelAngelJMZ/lab-agentes-databricks` y hacer clic en **Create Git folder**. Como el repositorio es público, no hace falta configurar credenciales de Git.
3. Dentro de la carpeta clonada, abrir `setup/00_setup_lab` y conectarlo a **Serverless**.
4. Llenar los campos de arriba:

   | Campo | Valor |
   |---|---|
   | `grupo_participantes` | **Obligatorio.** El grupo del paso 2 |
   | `genie_space_id` | El ID del Genie "Mesa de servicio" si ya existe en el workspace. Vacío: el setup lo busca o lo crea |
   | `catalogo` / `esquema_datos` | `la_tinka_taller` / `mesa_servicio`, los del taller de iniciación |
   | `fecha_taller` | Ya viene con 2026-11-26 |
   | `copiar_notebooks` | `si`: copia los notebooks a cada participante |

5. Hacer clic en **Run all**. Tarda unos 3 a 6 minutos.
6. Revisar la **tabla de verificación** del final: todo debe salir en ✓. Lo que salga en ⚠ indica qué falta activar.

El notebook se puede correr varias veces: no duplica nada. Si llega alguien nuevo al grupo, vuelve a correrlo y se le crea su espacio.

### Qué crea

| Recurso | Nombre | Quién accede |
|---|---|---|
| Datos | `la_tinka_taller.mesa_servicio`: reutiliza los del taller de iniciación (o los crea) y agrega la vista `incidencias_lab` | El grupo tiene `USE CATALOG`, `CREATE SCHEMA` y lectura sobre los datos |
| Espacio de Genie | `Mesa de servicio` (reutilizado o creado) | El grupo tiene CAN RUN |
| SQL Warehouse | `Taller La Tinka` (reutilizado, o serverless 2X-Small que se apaga a los 15 min) | El grupo tiene CAN USE |
| Modelo | El primer modelo de Claude disponible en Unity Gateway (`system.ai.*`) | El grupo tiene `EXECUTE` |
| Schema por participante | `la_tinka_taller.ag_<usuario>` | Cada participante es su dueño |
| Notebooks por participante | `/Workspace/Users/<correo>/Lab Agentes La Tinka/` y una copia en `/Workspace/Shared/Lab Agentes La Tinka/` | Cada participante trabaja en su copia |

`<usuario>` es la parte del correo antes de la @, en minúsculas y con `_` en lugar de puntos: `ana.torres@latinka.com.pe` → `ag_ana_torres`. Durante el lab, cada participante crea además **2 apps** (`mcp-<usuario>` y `agent-bricks-ag-<usuario>`): conviene revisar que la cuota de apps del workspace alcance.

## El día del taller

Cada participante abre **Workspace → Users → su correo → Lab Agentes La Tinka**, conecta **Serverless** y sigue los notebooks en orden: `00` → `01` → `02` → `03A` o `03B` → `04`. Si no ve su carpeta, puede usar la copia de **Workspace → Shared → Lab Agentes La Tinka**.

Antes del taller, envía a los participantes `materiales/guia_participante.html`: explica cómo preparar la laptop para la versión A del Lab 3.

## Después del taller

Hay dos limpiezas. Las dos se corren primero en modo **simular**, que muestra qué se borraría y qué se omite, y después en modo **borrar**.

| Notebook | Quién lo corre | Qué borra |
|---|---|---|
| `setup/99_limpieza` | El admin | Lo que construyeron **todos** los participantes del grupo, y las carpetas del lab |
| `labs/99 - Limpiar mis recursos del laboratorio` | Cada participante | Solo **lo suyo**, para volver a practicar. Conserva sus notebooks |

Las dos limpiezas solo borran recursos que pueden identificar como del laboratorio: el nombre exacto y una marca que deja el lab (la ruta del código de la app, el `agent.toml` del agente, el comentario del schema). Lo que no pasa la comprobación aparece como **omitido** y no se toca. **Nunca** borran el catálogo, los datos de `mesa_servicio`, el Genie ni el warehouse, que comparte el taller de iniciación.

## Para quien mantiene el laboratorio

- Los notebooks de `labs/` se **generan** desde las fuentes de `herramientas/fuentes/*.nb`. Para cambiar un notebook, edita su fuente y corre `python3 herramientas/construir_notebooks.py`.
- El setup escribe `labs/Includes/_config.py` en la carpeta desde donde se corre. En un Git folder queda como cambio local: si un *pull* falla por ese archivo, descarta el cambio, haz el *pull* y vuelve a correr el setup.
