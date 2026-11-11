# Databricks notebook source
# MAGIC %md
# MAGIC # Opcional · Evaluar el agente con MLflow
# MAGIC #### Duración: 45 minutos

# COMMAND ----------

# MAGIC %md
# MAGIC ## Panorama
# MAGIC
# MAGIC "Funciona en la demo" no es lo mismo que "funciona". Antes de una PoC necesitas **medir**: un set de preguntas reales con lo que esperas, *scorers* que califiquen cada respuesta y una forma de **comparar versiones** (otro prompt, otro modelo, otra tool).
# MAGIC
# MAGIC Aquí evaluamos el agente mínimo del Lab 1 con dos prompts de sistema y comparamos los resultados en MLflow:
# MAGIC - **LLM judges** integrados: `Correctness` (¿coincide con lo esperado?) y `Guidelines` (¿cumple nuestras reglas de estilo?).
# MAGIC - **Un scorer de código** propio: ¿el agente usó la tool correcta?

# COMMAND ----------

# MAGIC %md
# MAGIC ### Objetivos de aprendizaje
# MAGIC
# MAGIC - **Construir** un dataset de evaluación con preguntas, hechos esperados y la tool esperada.
# MAGIC - **Combinar** LLM judges con un scorer de código en `mlflow.genai.evaluate()`.
# MAGIC - **Comparar** dos versiones del prompt y **leer** los resultados en la UI de MLflow.

# COMMAND ----------

# MAGIC %pip install -q langgraph langchain langchain-openai langchain-mcp-adapters "mcp>=1.24,<2" "mlflow>=3.5"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./Includes/Setup-Lab

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## A. El agente a evaluar
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
# MAGIC El mismo agente del Lab 1: tu UC function y el Genie como tools. `predecir` es la función que MLflow llamará con cada pregunta; devuelve la respuesta y las tools usadas.

# COMMAND ----------

import mlflow
from langchain.agents import create_agent

mlflow.langchain.autolog()
TOOLS = mcp_listar(URL_MCP_FUNCIONES, "uc-functions") + mcp_listar(URL_MCP_GENIE, "genie")
LLM = modelo_chat()

PROMPTS = {
    "v1_basico": "Eres el asistente de la mesa de servicio de TI de La Tinka. Responde en español.",
    "v2_reglas": ("Eres el asistente de la mesa de servicio de TI de La Tinka. Responde en español, en máximo cinco líneas, "
                  "con cifras exactas tomadas de las tools y sin inventar datos. Para incidencias abiertas por prioridad usa "
                  "incidencias_abiertas; para el resto de preguntas de negocio usa Genie. Termina indicando la fuente usada."),
}


def armar_predictor(prompt):
    agente = create_agent(LLM, tools=TOOLS, system_prompt=prompt)

    def predecir(pregunta: str) -> dict:
        r = correr(agente.ainvoke({"messages": [{"role": "user", "content": pregunta}]}), timeout=300)
        texto = r["messages"][-1].content
        texto = texto if isinstance(texto, str) else " ".join(p.get("text", "") for p in texto if isinstance(p, dict))
        return {"respuesta": texto, "tools": tools_usadas(r["messages"])}

    return predecir

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## B. El dataset de evaluación
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
# MAGIC Ocho preguntas reales con los **hechos** que debe contener una buena respuesta (los calculamos con SQL sobre el dataset, a la fecha de corte del lab) y la tool que esperamos que use. En una PoC real empiezas con 10–15 preguntas de usuarios reales y lo vas ampliando con las trazas de producción.

# COMMAND ----------

DATASET = [
    {"inputs": {"pregunta": "¿Cuántas incidencias P1 están abiertas?"},
     "expectations": {"expected_facts": ["Hay 22 incidencias P1 abiertas o en progreso"], "tool": "incidencias_abiertas"}},
    {"inputs": {"pregunta": "¿Qué equipo tiene más P1 abiertas?"},
     "expectations": {"expected_facts": ["Pagos y Premios tiene más P1 abiertas, con 7"], "tool": "incidencias_abiertas"}},
    {"inputs": {"pregunta": "¿Cuál es la P1 abierta más antigua y cuántas horas lleva?"},
     "expectations": {"expected_facts": ["INC-02238", "lleva unas 260.7 horas abierta"], "tool": "incidencias_abiertas"}},
    {"inputs": {"pregunta": "¿Cuántas incidencias P3 siguen abiertas?"},
     "expectations": {"expected_facts": ["Hay 41 incidencias P3 abiertas o en progreso"], "tool": "incidencias_abiertas"}},
    {"inputs": {"pregunta": "¿Qué equipo tiene el peor cumplimiento de SLA en incidencias cerradas?"},
     "expectations": {"expected_facts": ["Pagos y Premios tiene el peor cumplimiento, alrededor de 66.7%"], "tool": "query_space"}},
    {"inputs": {"pregunta": "¿Qué equipo tiene el mejor cumplimiento de SLA en incidencias cerradas?"},
     "expectations": {"expected_facts": ["Seguridad y Accesos tiene el mejor cumplimiento, alrededor de 89.1%"], "tool": "query_space"}},
    {"inputs": {"pregunta": "¿Cuántas incidencias cerradas atendió Mesa de Ayuda N1?"},
     "expectations": {"expected_facts": ["Mesa de Ayuda N1 cerró 769 incidencias"], "tool": "query_space"}},
    {"inputs": {"pregunta": "¿Cuántas P2 hay abiertas?"},
     "expectations": {"expected_facts": ["Hay 19 incidencias P2 abiertas o en progreso"], "tool": "incidencias_abiertas"}},
]
print(f"{len(DATASET)} preguntas")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## C. Los scorers
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
# MAGIC - `Correctness`: un LLM judge compara la respuesta con `expected_facts`.
# MAGIC - `Guidelines`: un LLM judge revisa reglas en lenguaje natural.
# MAGIC - `tool_correcta`: código Python, determinista: ¿alguna tool usada contiene el nombre esperado?

# COMMAND ----------

from mlflow.genai.scorers import Correctness, Guidelines, scorer


@scorer
def tool_correcta(outputs, expectations) -> bool:
    return any(expectations["tool"] in t for t in outputs.get("tools", []))


SCORERS = [
    Correctness(),
    Guidelines(name="estilo", guidelines="La respuesta está en español, es breve (máximo cinco líneas) e indica la fuente de los datos."),
    tool_correcta,
]

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## D. Evaluar y comparar
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
# MAGIC Cada versión del prompt es una corrida de evaluación en el experimento del notebook. Tarda ≈ 2–4 minutos por versión.

# COMMAND ----------

resultados = {}
for nombre, prompt in PROMPTS.items():
    with mlflow.start_run(run_name=f"eval_{nombre}"):
        r = mlflow.genai.evaluate(data=DATASET, predict_fn=armar_predictor(prompt), scorers=SCORERS)
        resultados[nombre] = r.metrics
import pandas as pd
display(pd.DataFrame(resultados).T[[c for c in pd.DataFrame(resultados).T.columns if c.endswith("/mean")]])

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC #### D.1 Leer los resultados
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
# MAGIC Abre el experimento del notebook (ícono de matraz) → pestaña **Evaluations**. Compara las dos corridas pregunta por pregunta: para cada fallo, el judge explica **por qué**. Busca en particular las preguntas de SLA: ¿el agente fue a Genie o intentó contestar con la función de incidencias abiertas?

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## Reto
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
# MAGIC Escribe una tercera versión del prompt (`v3_...`) que mejore la métrica más baja sin empeorar las demás, y vuelve a correr la sección D. Pista: los fallos de `tool_correcta` se suelen arreglar mejor con un buen `COMMENT` en la función (Lab 1) que con más instrucciones en el prompt.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## Conclusión
# MAGIC
# MAGIC Con un dataset pequeño y tres scorers ya puedes decidir con datos entre dos versiones de un agente. El mismo `mlflow.genai.evaluate()` sirve para el agente desplegado del Lab 3 (cambiando `predict_fn` por una llamada a su endpoint) y para monitorear producción con las trazas.
# MAGIC <p style="font-size:13px; color:#5A6F77;"><strong>Documentación:</strong> <a href="https://docs.databricks.com/aws/en/agents/" target="_blank" style="color:#2272B4;">Evaluate and improve</a></p>
