# Databricks notebook source
# MAGIC %md
# MAGIC # Solución · Lab 1 · Reto de la regla de negocio
# MAGIC
# MAGIC La función hace dos cosas que el LLM no podía hacer solo:
# MAGIC - **Fija la definición** de "en riesgo de SLA": abierta, con al menos `umbral_pct` % del SLA consumido y **sin vencer** (`horas_abierta < sla_horas`). Sin esa última condición contarías también las vencidas.
# MAGIC - **La explica en el `COMMENT`**, para que el agente sepa que esta es la fuente oficial de la regla y cuándo usarla.
# MAGIC
# MAGIC Corre las dos celdas y vuelve al Lab 1 a ejecutar `probar_reto()`.

# COMMAND ----------

# MAGIC %run ../Includes/Setup-Lab

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOGO}.{MI_ESQUEMA}.incidencias_en_riesgo_sla(
  umbral_pct DOUBLE DEFAULT 80 COMMENT 'Porcentaje del SLA ya consumido a partir del cual una incidencia está en riesgo (0 a 100). Por defecto 80.'
)
RETURNS TABLE (id_incidencia STRING, prioridad STRING, equipo STRING, horas_abierta DOUBLE, sla_horas INT, pct_sla_consumido DOUBLE)
COMMENT 'Regla oficial de la mesa de servicio para incidencias EN RIESGO de incumplir el SLA: abiertas o en progreso que ya consumieron al menos umbral_pct % de sus sla_horas y que todavía NO vencen. Las incidencias con el SLA ya vencido no están en riesgo y no se incluyen. Úsala para cualquier pregunta sobre incidencias en riesgo de SLA; devuelve una fila por incidencia.'
RETURN SELECT id_incidencia, prioridad, equipo, round(horas_abierta, 1), sla_horas, round(100 * horas_abierta / sla_horas, 1)
FROM {CATALOGO}.{ESQUEMA_DATOS}.incidencias_lab
WHERE estatus <> 'Cerrada'
  AND horas_abierta >= sla_horas * incidencias_en_riesgo_sla.umbral_pct / 100
  AND horas_abierta < sla_horas
""")
display(spark.sql(f"SELECT * FROM {CATALOGO}.{MI_ESQUEMA}.incidencias_en_riesgo_sla() ORDER BY pct_sla_consumido DESC"))
