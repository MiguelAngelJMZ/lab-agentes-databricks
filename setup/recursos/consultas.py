"""SQL compartido por el setup, Genie (benchmarks) y las tarjetas del Lab 1.

Todas las consultas usan una fecha de referencia fija (`fecha_taller`) en lugar de
current_date(), para que las respuestas sean idénticas en el ensayo y el día del taller.
"""


def vista_incidencias_sla(c, s):
    return f"""
CREATE OR REPLACE VIEW `{c}`.`{s}`.incidencias_sla
COMMENT 'Incidencias con horas de resolución, cumplimiento de SLA y datos del equipo. Úsala para cualquier pregunta de SLA o tiempos de resolución.'
AS SELECT
  i.id_incidencia, i.fecha_apertura, i.fecha_cierre, i.prioridad, i.categoria, i.equipo,
  e.gerente, e.area, i.estatus, i.sla_horas, i.descripcion,
  ROUND((unix_timestamp(i.fecha_cierre) - unix_timestamp(i.fecha_apertura)) / 3600.0, 1) AS horas_resolucion,
  CASE WHEN i.fecha_cierre IS NULL THEN NULL
       ELSE (unix_timestamp(i.fecha_cierre) - unix_timestamp(i.fecha_apertura)) / 3600.0 <= i.sla_horas END AS dentro_sla
FROM `{c}`.`{s}`.incidencias i
JOIN `{c}`.`{s}`.equipos e ON i.equipo = e.equipo
"""


def preguntas_lab1(c, s, f):
    """Las 6 preguntas "solución" del Lab 1: (nivel, pregunta, sql). `f` = 'YYYY-MM-DD'."""
    t = f"`{c}`.`{s}`"
    hoy = f"DATE'{f}'"
    return [
        (1, "¿Cuántas incidencias se abrieron el mes pasado?",
         f"SELECT COUNT(*) AS incidencias FROM {t}.incidencias "
         f"WHERE fecha_apertura >= add_months(trunc({hoy}, 'MM'), -1) AND fecha_apertura < trunc({hoy}, 'MM')"),
        (1, "¿Cuántas incidencias P1 siguen abiertas por equipo?",
         f"SELECT equipo, COUNT(*) AS incidencias FROM {t}.incidencias "
         f"WHERE prioridad = 'P1' AND estatus <> 'Cerrada' GROUP BY equipo ORDER BY incidencias DESC"),
        (2, "¿Qué % de incidencias se cerró dentro del SLA por categoría?",
         f"SELECT categoria, ROUND(100 * AVG(CASE WHEN dentro_sla THEN 1 ELSE 0 END), 1) AS pct_dentro_sla "
         f"FROM {t}.incidencias_sla WHERE estatus = 'Cerrada' GROUP BY categoria ORDER BY pct_dentro_sla DESC"),
        (2, "Tendencia semanal de incidencias nuevas de los últimos 3 meses",
         f"SELECT date_trunc('WEEK', fecha_apertura) AS semana, COUNT(*) AS incidencias FROM {t}.incidencias "
         f"WHERE fecha_apertura >= date_trunc('WEEK', add_months({hoy}, -3)) AND fecha_apertura < date_trunc('WEEK', {hoy}) "
         f"GROUP BY 1 ORDER BY 1"),
        (3, "Proyectos con fecha compromiso en los próximos 30 días y avance menor a 50%",
         f"SELECT nombre, responsable, pct_avance, fecha_compromiso FROM {t}.proyectos "
         f"WHERE fecha_compromiso > {hoy} AND fecha_compromiso <= date_add({hoy}, 30) AND pct_avance < 50 "
         f"ORDER BY pct_avance"),
        (3, "¿Qué equipo tuvo la mayor caída en satisfacción promedio el mes pasado respecto al mes anterior?",
         f"WITH m AS (SELECT i.equipo, "
         f"AVG(CASE WHEN e.fecha_encuesta >= add_months(trunc({hoy}, 'MM'), -1) AND e.fecha_encuesta < trunc({hoy}, 'MM') THEN e.calificacion END) AS mes_pasado, "
         f"AVG(CASE WHEN e.fecha_encuesta >= add_months(trunc({hoy}, 'MM'), -2) AND e.fecha_encuesta < add_months(trunc({hoy}, 'MM'), -1) THEN e.calificacion END) AS mes_anterior "
         f"FROM {t}.encuestas_satisfaccion e JOIN {t}.incidencias i ON e.id_incidencia = i.id_incidencia GROUP BY i.equipo) "
         f"SELECT equipo, ROUND(mes_pasado - mes_anterior, 2) AS variacion FROM m ORDER BY variacion ASC LIMIT 1"),
    ]


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def benchmarks(c, s, fecha_taller):
    """Benchmarks del espacio de Genie: (pregunta, sql).

    Las 6 preguntas del Lab 1 con 3 redacciones cada una (como las escribiría un participante)
    y 6 preguntas extra con 2 redacciones. Ninguna se copia en los ejemplos SQL del espacio.
    """
    f = fecha_taller.isoformat()
    t = f"`{c}`.`{s}`"
    hoy = f"DATE'{f}'"
    mes_pasado = MESES[(fecha_taller.month - 2) % 12]
    mes_antepasado = MESES[(fecha_taller.month - 3) % 12]
    sql = {n: q for n, (_, _, q) in enumerate(preguntas_lab1(c, s, f), 1)}
    redacciones = {
        1: ["¿Cuántas incidencias se abrieron el mes pasado?",
            f"¿Cuántos tickets se registraron en {mes_pasado}?",
            "Total de incidencias nuevas del mes pasado"],
        2: ["¿Cuántas incidencias P1 siguen abiertas por equipo?",
            "Incidencias urgentes sin cerrar por equipo",
            "¿Qué equipos tienen incidencias P1 pendientes y cuántas tiene cada uno?"],
        3: ["¿Qué % de incidencias se cerró dentro del SLA por categoría?",
            "Porcentaje de cumplimiento de SLA por categoría",
            "¿En qué porcentaje cumplimos el tiempo comprometido en cada categoría?"],
        4: ["Tendencia semanal de incidencias nuevas de los últimos 3 meses",
            "¿Cuántas incidencias se abrieron cada semana en los últimos tres meses?",
            "Evolución semanal de tickets registrados en los últimos 3 meses"],
        5: ["Proyectos con fecha compromiso en los próximos 30 días y avance menor a 50%",
            "¿Qué proyectos están en riesgo?",
            "Proyectos que vencen en los próximos 30 días y llevan menos de la mitad de avance"],
        6: ["¿Qué equipo tuvo la mayor caída en satisfacción promedio el mes pasado respecto al mes anterior?",
            f"¿Qué equipo empeoró más en satisfacción en {mes_pasado} comparado con {mes_antepasado}?",
            "Equipo con la mayor baja en calificación promedio de encuestas el mes pasado frente al anterior"],
    }
    extras = [
        (["¿Cuál es el tiempo promedio de resolución en horas por prioridad?",
          "Horas promedio para resolver una incidencia según su prioridad"],
         f"SELECT prioridad, ROUND(AVG(horas_resolucion), 1) AS horas_promedio FROM {t}.incidencias_sla "
         f"WHERE estatus = 'Cerrada' GROUP BY prioridad ORDER BY prioridad"),
        (["¿Cuántas incidencias abiertas hay por prioridad?",
          "Tickets pendientes por prioridad"],
         f"SELECT prioridad, COUNT(*) AS incidencias FROM {t}.incidencias_sla "
         f"WHERE estatus <> 'Cerrada' GROUP BY prioridad ORDER BY prioridad"),
        (["¿Cuál es la calificación promedio de satisfacción por equipo?",
          "Promedio de las encuestas de satisfacción de cada equipo"],
         f"SELECT i.equipo, ROUND(AVG(e.calificacion), 2) AS calificacion_promedio FROM {t}.encuestas_satisfaccion e "
         f"JOIN {t}.incidencias_sla i ON e.id_incidencia = i.id_incidencia GROUP BY i.equipo ORDER BY calificacion_promedio DESC"),
        (["Muéstrame los proyectos de Ana Torres",
          "¿Qué proyectos tiene a su cargo Ana Torres?"],
         f"SELECT nombre, estatus, pct_avance, fecha_compromiso FROM {t}.proyectos "
         f"WHERE responsable = 'Ana Torres' ORDER BY fecha_compromiso"),
        (["¿Qué % de incidencias se cerró dentro del SLA por equipo?",
          "Cumplimiento de SLA de cada equipo en porcentaje"],
         f"SELECT equipo, ROUND(100 * AVG(CASE WHEN dentro_sla THEN 1 ELSE 0 END), 1) AS pct_dentro_sla "
         f"FROM {t}.incidencias_sla WHERE estatus = 'Cerrada' GROUP BY equipo ORDER BY pct_dentro_sla DESC"),
        (["¿Cuántas incidencias se cerraron este mes?",
          "Total de tickets cerrados en lo que va del mes"],
         f"SELECT COUNT(*) AS incidencias FROM {t}.incidencias_sla "
         f"WHERE fecha_cierre >= trunc({hoy}, 'MM') AND fecha_cierre < date_add({hoy}, 1)"),
    ]
    salida = [(q, sql[n]) for n, qs in redacciones.items() for q in qs]
    salida += [(q, consulta) for qs, consulta in extras for q in qs]
    return salida
