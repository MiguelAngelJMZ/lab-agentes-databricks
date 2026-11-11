"""Construye el serialized_space del espacio Genie "Mesa de servicio".

Sigue las buenas prácticas de Genie: pocas fuentes y sin duplicados, la lógica de negocio
en superficies estructuradas (descripciones y sinónimos por columna, joins, SQL expressions,
ejemplos SQL por forma de consulta) y un texto de instrucciones corto, solo para el
comportamiento global. Los benchmarks son evaluación y no se repiten en los ejemplos.
"""

import hashlib
import json
from datetime import date

from consultas import MESES, benchmarks

DESCRIPCION = (
    "Mesa de servicio de TI de La Tinka (datos sintéticos del taller). Responde en español preguntas sobre "
    "incidencias (volumen, prioridad, estatus, SLA y tiempos de resolución por equipo y categoría), encuestas "
    "de satisfacción de los usuarios y avance de los proyectos de TI."
)


def _id(texto):
    # IDs deterministas (32 hex): actualizar el espacio no duplica elementos
    return hashlib.md5(texto.encode()).hexdigest()


def _por_id(items):
    return sorted(items, key=lambda x: x["id"])


def _col(nombre, descripcion=None, sinonimos=None, categoria=False):
    c = {"column_name": nombre}
    if descripcion:
        c["description"] = [descripcion]
    if sinonimos:
        c["synonyms"] = sinonimos
    if categoria:  # solo en categorías que los usuarios nombran
        c.update(enable_format_assistance=True, enable_entity_matching=True)
    return c


def _tabla(identificador, columnas):
    return {"identifier": identificador, "column_configs": sorted(columnas, key=lambda x: x["column_name"])}


def construir(c, s, fecha_taller: date):
    f = fecha_taller.isoformat()
    hoy = f"DATE'{f}'"
    mes_pasado = MESES[(fecha_taller.month - 2) % 12]
    mes_antepasado = MESES[(fecha_taller.month - 3) % 12]
    inc, enc, pry = f"{c}.{s}.incidencias_sla", f"{c}.{s}.encuestas_satisfaccion", f"{c}.{s}.proyectos"
    t = f"`{c}`.`{s}`"

    # ---------- Fuentes: 3, una por grano (incidencia, encuesta, proyecto) ----------
    fuentes = [
        _tabla(inc, [
            _col("id_incidencia", "Identificador del ticket. Una fila por incidencia.", ["ticket", "caso", "número de incidencia"]),
            _col("fecha_apertura", "Fecha y hora en que se registró la incidencia. Úsala para 'se abrieron', 'nuevas', 'registradas' o 'creadas'.",
                 ["fecha de registro", "fecha de creación", "fecha de alta"]),
            _col("fecha_cierre", "Fecha y hora de cierre. Vacía mientras la incidencia no está cerrada.", ["fecha de resolución", "fecha de solución"]),
            _col("prioridad", "P1 es urgente o crítica; P4 es baja.", ["urgencia", "severidad", "criticidad"], categoria=True),
            _col("categoria", "Tipo de problema reportado.", ["tipo de incidencia", "motivo", "tema"], categoria=True),
            _col("equipo", "Equipo que atiende la incidencia.", ["área responsable", "grupo resolutor", "mesa"], categoria=True),
            _col("gerente", "Gerente del equipo que atiende.", ["jefe", "responsable del equipo"], categoria=True),
            _col("area", "Área de la empresa a la que pertenece el equipo.", ["gerencia", "unidad"], categoria=True),
            _col("estatus", "Abierta, En progreso o Cerrada. 'Abierta' o 'pendiente' en una pregunta significa estatus distinto de Cerrada.",
                 ["estado", "status", "situación"], categoria=True),
            _col("sla_horas", "Horas comprometidas para resolver según la prioridad.", ["SLA", "tiempo comprometido", "acuerdo de servicio"]),
            _col("descripcion", "Texto libre del reclamo.", ["detalle", "comentario del ticket"]),
            _col("horas_resolucion", "Horas entre apertura y cierre. Vacía si no está cerrada.", ["tiempo de resolución", "tiempo de atención", "horas para resolver"]),
            _col("dentro_sla", "Verdadero si se cerró dentro de sla_horas. Vacía si no está cerrada.", ["cumplió SLA", "a tiempo", "dentro del tiempo comprometido"]),
        ]),
        _tabla(enc, [
            _col("id_incidencia", "Incidencia evaluada. Una encuesta por incidencia cerrada; une con incidencias_sla."),
            _col("calificacion", "Calificación del usuario de 1 (muy mala) a 5 (excelente).", ["satisfacción", "nota", "puntaje", "CSAT", "valoración"]),
            _col("comentario", "Comentario libre del usuario.", ["opinión", "feedback"]),
            _col("fecha_encuesta", "Fecha en que se respondió la encuesta. Úsala para ubicar la satisfacción en un mes.", ["fecha de la encuesta"]),
        ]),
        _tabla(pry, [
            _col("nombre", "Nombre del proyecto.", ["proyecto", "iniciativa"]),
            _col("responsable", "Líder del proyecto.", ["líder", "encargado", "dueño", "a cargo"], categoria=True),
            _col("fecha_inicio", "Fecha de inicio del proyecto."),
            _col("fecha_compromiso", "Fecha comprometida de entrega.", ["fecha de entrega", "vencimiento", "deadline", "fecha límite"]),
            _col("pct_avance", "Porcentaje de avance de 0 a 100.", ["% avance", "avance", "progreso", "porcentaje completado"]),
            _col("estatus", "En curso, En riesgo, En pausa o Completado.", ["estado", "situación"], categoria=True),
        ]),
    ]

    # ---------- Relación ----------
    joins = [{
        "id": _id("join_encuestas_incidencias"),
        "left": {"identifier": enc, "alias": "encuestas_satisfaccion"},
        "right": {"identifier": inc, "alias": "incidencias_sla"},
        "sql": ["`encuestas_satisfaccion`.`id_incidencia` = `incidencias_sla`.`id_incidencia`",
                "--rt=FROM_RELATIONSHIP_TYPE_ONE_TO_ONE--"],
    }]

    # ---------- SQL expressions: conceptos de negocio definidos una sola vez ----------
    mm = f"trunc({hoy}, 'MM')"
    snippets = {
        "measures": [
            {"id": _id("m_incidencias"), "alias": "incidencias", "display_name": "Número de incidencias",
             "sql": ["COUNT(incidencias_sla.id_incidencia)"], "synonyms": ["cantidad de incidencias", "tickets", "casos", "volumen"]},
            {"id": _id("m_pct_sla"), "alias": "pct_dentro_sla", "display_name": "% dentro del SLA",
             "sql": ["ROUND(100 * AVG(CASE WHEN incidencias_sla.dentro_sla THEN 1.0 WHEN NOT incidencias_sla.dentro_sla THEN 0.0 END), 1)"],
             "synonyms": ["cumplimiento de SLA", "% a tiempo", "porcentaje dentro del tiempo comprometido"]},
            {"id": _id("m_horas"), "alias": "horas_promedio_resolucion", "display_name": "Tiempo promedio de resolución (horas)",
             "sql": ["ROUND(AVG(incidencias_sla.horas_resolucion), 1)"], "synonyms": ["tiempo promedio de atención", "horas promedio"]},
            {"id": _id("m_calif"), "alias": "calificacion_promedio", "display_name": "Calificación promedio",
             "sql": ["ROUND(AVG(encuestas_satisfaccion.calificacion), 2)"], "synonyms": ["satisfacción promedio", "CSAT promedio", "nota promedio"]},
        ],
        "filters": [
            {"id": _id("f_abiertas"), "display_name": "Incidencias abiertas (no cerradas)",
             "sql": ["incidencias_sla.estatus <> 'Cerrada'"], "synonyms": ["abiertas", "pendientes", "sin cerrar", "siguen abiertas"]},
            {"id": _id("f_p1"), "display_name": "Incidencias urgentes (P1)",
             "sql": ["incidencias_sla.prioridad = 'P1'"], "synonyms": ["urgentes", "críticas", "P1"]},
            {"id": _id("f_mes_pasado_ap"), "display_name": f"Abiertas el mes pasado ({mes_pasado})",
             "sql": [f"incidencias_sla.fecha_apertura >= add_months({mm}, -1) AND incidencias_sla.fecha_apertura < {mm}"],
             "synonyms": ["se abrieron el mes pasado", "nuevas del mes pasado", f"registradas en {mes_pasado}"]},
            {"id": _id("f_ult3m"), "display_name": "Últimos 3 meses (semanas completas, por apertura)",
             "sql": [f"incidencias_sla.fecha_apertura >= date_trunc('WEEK', add_months({hoy}, -3)) "
                     f"AND incidencias_sla.fecha_apertura < date_trunc('WEEK', {hoy})"],
             "synonyms": ["últimos tres meses", "último trimestre móvil"]},
            {"id": _id("f_enc_mes_pasado"), "display_name": f"Encuestas del mes pasado ({mes_pasado})",
             "sql": [f"encuestas_satisfaccion.fecha_encuesta >= add_months({mm}, -1) AND encuestas_satisfaccion.fecha_encuesta < {mm}"],
             "synonyms": ["satisfacción del mes pasado"]},
            {"id": _id("f_enc_mes_anterior"), "display_name": f"Encuestas del mes anterior al pasado ({mes_antepasado})",
             "sql": [f"encuestas_satisfaccion.fecha_encuesta >= add_months({mm}, -2) AND encuestas_satisfaccion.fecha_encuesta < add_months({mm}, -1)"],
             "synonyms": ["mes anterior", f"satisfacción de {mes_antepasado}"]},
            {"id": _id("f_riesgo"), "display_name": "Proyectos en riesgo",
             "sql": [f"proyectos.fecha_compromiso > {hoy} AND proyectos.fecha_compromiso <= date_add({hoy}, 30) AND proyectos.pct_avance < 50"],
             "synonyms": ["en riesgo", "atrasados que vencen pronto"]},
            {"id": _id("f_vencen30"), "display_name": "Proyectos que vencen en los próximos 30 días",
             "sql": [f"proyectos.fecha_compromiso > {hoy} AND proyectos.fecha_compromiso <= date_add({hoy}, 30)"],
             "synonyms": ["vencen pronto", "por vencer"]},
        ],
        "expressions": [
            {"id": _id("e_semana"), "alias": "semana", "display_name": "Semana de apertura (inicia lunes)",
             "sql": ["date_trunc('WEEK', incidencias_sla.fecha_apertura)"]},
            {"id": _id("e_mes"), "alias": "mes", "display_name": "Mes de apertura",
             "sql": ["date_trunc('MONTH', incidencias_sla.fecha_apertura)"]},
            {"id": _id("e_mes_enc"), "alias": "mes_encuesta", "display_name": "Mes de la encuesta",
             "sql": ["date_trunc('MONTH', encuestas_satisfaccion.fecha_encuesta)"]},
        ],
    }
    for k in snippets:
        snippets[k] = _por_id(snippets[k])

    # ---------- Ejemplos SQL: una por forma de consulta, distintas a los benchmarks ----------
    ejemplos = [
        ("¿Cuántas incidencias se abrieron esta semana?",
         f"SELECT COUNT(*) AS incidencias FROM {t}.incidencias_sla "
         f"WHERE fecha_apertura >= date_trunc('WEEK', {hoy}) AND fecha_apertura < date_add({hoy}, 1)",
         "Conteo con periodo relativo a hoy."),
        ("Incidencias abiertas por categoría",
         f"SELECT categoria, COUNT(*) AS incidencias FROM {t}.incidencias_sla WHERE estatus <> 'Cerrada' "
         f"GROUP BY categoria ORDER BY incidencias DESC",
         "Agrupación por una dimensión con filtro de estatus."),
        ("% dentro del SLA por prioridad",
         f"SELECT prioridad, ROUND(100 * AVG(CASE WHEN dentro_sla THEN 1.0 WHEN NOT dentro_sla THEN 0.0 END), 1) AS pct_dentro_sla "
         f"FROM {t}.incidencias_sla WHERE estatus = 'Cerrada' GROUP BY prioridad ORDER BY prioridad",
         "Ratio de cumplimiento de SLA: solo incidencias cerradas."),
        ("Tendencia semanal de incidencias de Pagos y premios en el último mes",
         f"SELECT date_trunc('WEEK', fecha_apertura) AS semana, COUNT(*) AS incidencias FROM {t}.incidencias_sla "
         f"WHERE categoria = 'Pagos y premios' AND fecha_apertura >= date_trunc('WEEK', add_months({hoy}, -1)) "
         f"AND fecha_apertura < date_trunc('WEEK', {hoy}) GROUP BY 1 ORDER BY 1",
         "Serie semanal: semanas completas que empiezan en lunes."),
        (f"Calificación promedio por categoría: {mes_pasado} frente a {mes_antepasado}",
         f"SELECT i.categoria, "
         f"ROUND(AVG(CASE WHEN e.fecha_encuesta >= add_months({mm}, -1) AND e.fecha_encuesta < {mm} THEN e.calificacion END), 2) AS mes_pasado, "
         f"ROUND(AVG(CASE WHEN e.fecha_encuesta >= add_months({mm}, -2) AND e.fecha_encuesta < add_months({mm}, -1) THEN e.calificacion END), 2) AS mes_anterior "
         f"FROM {t}.encuestas_satisfaccion e JOIN {t}.incidencias_sla i ON e.id_incidencia = i.id_incidencia "
         f"GROUP BY i.categoria ORDER BY i.categoria",
         "Comparar dos meses completos uniendo encuestas con incidencias."),
        ("Proyectos que vencen en los próximos 60 días",
         f"SELECT nombre, responsable, pct_avance, fecha_compromiso FROM {t}.proyectos "
         f"WHERE fecha_compromiso > {hoy} AND fecha_compromiso <= date_add({hoy}, 60) ORDER BY fecha_compromiso",
         "Ventana de fechas hacia adelante desde hoy."),
    ]

    instrucciones = (
        "## PURPOSE\n"
        "- Mesa de servicio de TI de La Tinka para un taller con usuarios no técnicos.\n\n"
        "## DISAMBIGUATION\n"
        f"- Hoy es {f}: es la fecha de referencia del taller; úsala en lugar de la fecha del sistema.\n"
        f"- 'El mes pasado' es el mes calendario completo anterior ({mes_pasado}); 'el mes anterior' a ese es {mes_antepasado}. "
        "El mes en curso está incompleto.\n"
        "- 'Se abrieron', 'nuevas' o 'registradas' cuentan por fecha de apertura sin filtrar estatus; "
        "'abiertas', 'pendientes' o 'siguen abiertas' filtran por estatus distinto de Cerrada.\n"
        "- En tendencias semanales usa solo semanas completas (de lunes a domingo): excluye la semana en curso "
        "y empieza en el lunes de la semana en que cae el inicio del periodo.\n\n"
        "## DATA QUALITY NOTES\n"
        "- horas_resolucion y dentro_sla están vacías mientras la incidencia no se cierra.\n\n"
        "## Instructions you must follow when providing summaries\n"
        "- Responde siempre en español.\n"
        "- Indica el periodo de fechas usado.\n"
        "- Redondea los porcentajes a 1 decimal.\n"
    )

    preguntas_ejemplo = [
        "¿Cuántas incidencias hay abiertas hoy?",
        "¿Cuál es el tiempo promedio de resolución por equipo?",
        "¿Qué categoría tiene más incidencias este año?",
        "¿Cómo va la satisfacción de los usuarios por categoría?",
        "¿Qué proyectos vencen este año?",
    ]

    espacio = {
        "version": 2,
        "config": {"sample_questions": _por_id([{"id": _id("sq" + q), "question": [q]} for q in preguntas_ejemplo])},
        "data_sources": {"tables": sorted(fuentes, key=lambda x: x["identifier"])},
        "instructions": {
            "text_instructions": [{"id": _id("instrucciones"), "content": [instrucciones]}],
            "example_question_sqls": _por_id([{"id": _id("ej" + q), "question": [q], "sql": [sql], "usage_guidance": [uso]}
                                              for q, sql, uso in ejemplos]),
            "join_specs": joins,
            "sql_snippets": snippets,
        },
        # Evaluación: no son contexto para Genie y no se repiten en los ejemplos
        "benchmarks": {"questions": _por_id([
            {"id": _id("bm" + q), "question": [q], "answer": [{"format": "SQL", "content": [sql]}]}
            for q, sql in benchmarks(c, s, fecha_taller)
        ])},
    }
    return json.dumps(espacio, ensure_ascii=False)
