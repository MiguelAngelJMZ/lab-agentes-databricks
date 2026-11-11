"""Generador determinista del dataset sintético "Mesa de servicio de TI – La Tinka".

Python puro (sin Spark) para que el resultado sea idéntico en cualquier workspace
y se pueda verificar localmente. Todas las fechas son relativas a `fecha_taller`,
así "el mes pasado" de las tarjetas del Lab 1 es el mes anterior al taller.

Uso:
    from datos import generar
    tablas = generar(date(2026, 11, 26))   # dict nombre_tabla -> list[dict]
"""

import random
from datetime import date, datetime, timedelta

SEMILLA = 2026

EQUIPOS = [
    # equipo, gerente, área
    ("Mesa de Ayuda N1", "Rosa Quispe", "Atención al Cliente"),
    ("Canal Digital", "Diego Salazar", "Tecnología"),
    ("Punto de Venta", "Carmen Huamán", "Operaciones Comerciales"),
    ("Pagos y Premios", "Luis Paredes", "Finanzas"),
    ("Infraestructura TI", "Jorge Valdivia", "Tecnología"),
    ("Seguridad y Accesos", "Patricia Rojas", "Tecnología"),
]

# Equipo que no tendrá incidencias P1 abiertas → la tarjeta 2 tiene exactamente 5 filas
EQUIPO_SIN_P1_ABIERTAS = "Seguridad y Accesos"
# Equipo con la mayor caída de satisfacción del mes pasado vs. el anterior (tarjeta 6)
EQUIPO_CAIDA_SATISFACCION = "Pagos y Premios"

SLA_HORAS = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}
PESO_PRIORIDAD = [("P1", 0.08), ("P2", 0.22), ("P3", 0.45), ("P4", 0.25)]

# categoría -> (equipos que la atienden, prob. de cumplir SLA, plantillas de descripción)
CATEGORIAS = {
    "Pagos y premios": (
        ["Pagos y Premios", "Mesa de Ayuda N1"],
        0.71,
        [
            "No me llegó el pago del premio de {juego} a mi cuenta {banco}, ya pasaron {dias} días.",
            "Gané S/ {monto} en {juego} y el retiro sigue en estado pendiente.",
            "Me descontaron dos veces la recarga de S/ {monto} con {medio}.",
            "El premio de {juego} aparece cobrado pero no recibí el dinero.",
            "La transferencia de mi premio fue rechazada por el banco {banco}.",
        ],
    ),
    "Acceso a cuenta": (
        ["Seguridad y Accesos", "Mesa de Ayuda N1"],
        0.88,
        [
            "Olvidé mi contraseña y no me llega el correo de recuperación.",
            "Mi cuenta quedó bloqueada después de tres intentos fallidos.",
            "No recibo el código SMS para validar mi identidad.",
            "No puedo actualizar mi número de celular en mi perfil.",
            "Me aparece que mi DNI ya está registrado con otra cuenta.",
        ],
    ),
    "App y web": (
        ["Canal Digital", "Mesa de Ayuda N1"],
        0.80,
        [
            "La app se cerró al comprar mi jugada de {juego}.",
            "La página web se queda cargando al momento de pagar.",
            "No veo mis jugadas anteriores en el historial de la app.",
            "La app muestra error 500 al abrir resultados de {juego}.",
            "Después de actualizar la app ya no puedo iniciar sesión desde {dispositivo}.",
        ],
    ),
    "Punto de venta": (
        ["Punto de Venta", "Mesa de Ayuda N1"],
        0.76,
        [
            "No puedo validar mi ticket de {juego} en el punto de venta de {distrito}.",
            "La terminal del agente en {distrito} no imprime los tickets.",
            "El agente de {distrito} dice que el sistema está caído y no vende {juego}.",
            "El ticket ganador de S/ {monto} no se puede cobrar en la agencia.",
            "La terminal POS rechaza pagos con tarjeta en {distrito}.",
        ],
    ),
    "Infraestructura": (
        ["Infraestructura TI"],
        0.93,
        [
            "Alta latencia en el servidor de base de datos de ventas.",
            "Caída intermitente de la VPN de agencias en {distrito}.",
            "Disco al 95% en el servidor de reportes nocturnos.",
            "Certificado SSL del portal de agentes vence en 7 días.",
            "Falla en el respaldo programado de la base de sorteos.",
        ],
    ),
    "Sorteos y resultados": (
        ["Canal Digital", "Infraestructura TI"],
        0.64,
        [
            "Los resultados del sorteo de {juego} no se publicaron a tiempo en la web.",
            "Mi jugada de {juego} no aparece participando en el sorteo de anoche.",
            "Los números ganadores de {juego} en la app no coinciden con la TV.",
            "El pozo acumulado de {juego} muestra un monto desactualizado.",
            "No me llegó la notificación de resultados de {juego}.",
        ],
    ),
}

JUEGOS = ["Tinka", "Kábala", "Ganadiario", "Te Apuesto", "Kinelo", "Raspaditas"]
BANCOS = ["BCP", "Interbank", "BBVA", "Scotiabank"]
MEDIOS = ["Yape", "Plin", "tarjeta Visa", "PagoEfectivo"]
DISTRITOS = ["Miraflores", "San Juan de Lurigancho", "Arequipa Cercado", "Trujillo", "Surco", "Callao", "Piura"]
DISPOSITIVOS = ["Android", "iPhone"]

COMENTARIOS = {
    5: [
        "Excelente atención, resolvieron mi problema en minutos.",
        "Muy amables y rápidos, gracias por la ayuda.",
        "Me explicaron todo con claridad, quedé muy satisfecho.",
        "Rápido y sin complicaciones, así da gusto.",
    ],
    4: [
        "Buena atención, aunque tuve que esperar un poco.",
        "Resolvieron el caso, pero me pidieron los mismos datos dos veces.",
        "Todo bien, el agente fue atento.",
    ],
    3: [
        "Se resolvió, pero tardaron más de lo que me dijeron.",
        "Regular, tuve que llamar dos veces para que me atiendan.",
        "La solución funcionó, pero nadie me avisó que ya estaba listo.",
    ],
    2: [
        "Tardaron demasiado y no me dieron información del avance.",
        "Me cerraron el caso sin resolverlo, tuve que abrir otro.",
        "El agente no sabía cómo ayudarme con mi premio.",
    ],
    1: [
        "Pésimo servicio, sigo sin recibir mi dinero.",
        "Nadie me responde, es la tercera vez que reclamo.",
        "Muy decepcionado, perdí mi jugada y no me dieron solución.",
        "Horrible, me tuvieron una semana esperando el pago del premio.",
    ],
}

# Quejas concretas por categoría: dan material real a ai_summarize y ai_query
QUEJAS_POR_CATEGORIA = {
    "Pagos y premios": [
        "Llevo {dias} días esperando el pago de mi premio de {juego} y nadie me da una fecha.",
        "Me pidieron los mismos documentos tres veces para cobrar S/ {monto}.",
        "El retiro a {banco} sigue rechazado y me cerraron el caso sin resolverlo.",
        "Me devolvieron la recarga de {medio} recién después de una semana, pésimo.",
    ],
    "Acceso a cuenta": [
        "Estuve {dias} días sin poder entrar a mi cuenta y perdí el sorteo de {juego}.",
        "El código de verificación nunca llegó y el agente solo me dijo que espere.",
        "Me desbloquearon la cuenta pero al día siguiente volvió a bloquearse.",
    ],
    "App y web": [
        "La app se sigue cerrando al pagar, me dijeron que actualice y nada cambió.",
        "Perdí mi jugada de {juego} porque la web se cayó y nadie se hace responsable.",
        "Respondieron con un mensaje automático que no tenía nada que ver con mi problema.",
    ],
    "Punto de venta": [
        "En la agencia de {distrito} siguen sin poder pagar mi ticket ganador.",
        "El agente de {distrito} me trató mal y me mandó a llamar a la central.",
        "La terminal de {distrito} lleva {dias} días sin imprimir y nadie viene a repararla.",
    ],
    "Infraestructura": [
        "Otra vez se cayó el sistema de reportes y nos enteramos por los usuarios.",
        "La VPN de la agencia de {distrito} falla todas las tardes y no hay solución definitiva.",
    ],
    "Sorteos y resultados": [
        "Los resultados de {juego} salieron tarde otra vez y mis clientes reclamaron en la agencia.",
        "Mi jugada de {juego} no participó en el sorteo y solo me ofrecieron disculpas.",
        "El pozo de {juego} en la app no coincidía con la TV y nadie me explicó por qué.",
    ],
}

RESPONSABLES = [
    "Ana Torres", "Miguel Chávez", "Lucía Mendoza", "Raúl Castillo", "Sofía Ramírez",
    "Pedro Gutiérrez", "Valeria Flores", "Andrés Vargas", "Gabriela Ríos", "Fernando León",
]

PROYECTOS = [
    "Migración del portal de agentes", "Nueva app Tinka 3.0", "Pagos con Yape en web",
    "Renovación de terminales POS", "Chatbot de atención al cliente", "Data lake de ventas",
    "Monitoreo 24/7 de sorteos", "Autenticación con doble factor", "Portal de cobro de premios",
    "Tablero de ventas por agencia", "Actualización de servidores de sorteos", "Integración con Plin",
    "Programa de lealtad de jugadores", "Automatización de conciliaciones", "Rediseño de la web de resultados",
    "Respaldo en la nube", "Gestión de identidades", "Reporte regulatorio mensual",
    "Kiosko de autoservicio", "Alertas de fraude en pagos", "Capacitación de agentes digitales",
    "Optimización de la red de agencias", "Encuesta de satisfacción en app", "Catálogo de datos corporativo",
]


def _elegir(rng, pares):
    x, acumulado = rng.random(), 0.0
    for valor, peso in pares:
        acumulado += peso
        if x <= acumulado:
            return valor
    return pares[-1][0]


def _rellenar(rng, plantilla):
    return plantilla.format(
        juego=rng.choice(JUEGOS), banco=rng.choice(BANCOS), medio=rng.choice(MEDIOS),
        distrito=rng.choice(DISTRITOS), dispositivo=rng.choice(DISPOSITIVOS),
        monto=rng.choice([20, 50, 100, 150, 250, 500, 1200, 3500]), dias=rng.randint(3, 15),
    )


def _mes_anterior(d, n=1):
    y, m = d.year, d.month - n
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def generar(fecha_taller: date):
    rng = random.Random(SEMILLA)
    hoy = datetime.combine(fecha_taller, datetime.min.time()) + timedelta(hours=9)
    inicio = datetime.combine(_mes_anterior(fecha_taller, 6), datetime.min.time())
    mes_pasado = _mes_anterior(fecha_taller, 1)
    mes_antepasado = _mes_anterior(fecha_taller, 2)

    equipos = [{"equipo": e, "gerente": g, "area": a} for e, g, a in EQUIPOS]

    # ---------------- incidencias ----------------
    incidencias = []
    dia = inicio
    n = 0
    while dia < hoy:
        # volumen diario con estacionalidad semanal (más reclamos lunes) y leve tendencia al alza
        base = 11 + 3 * (dia.weekday() == 0) - 3 * (dia.weekday() >= 5)
        base += int((dia - inicio).days / 60)
        for _ in range(max(3, int(rng.gauss(base, 2.5)))):
            n += 1
            apertura = dia + timedelta(minutes=rng.randint(7 * 60, 22 * 60))
            if apertura >= hoy:
                continue
            categoria = rng.choice(list(CATEGORIAS))
            equipos_cat, p_sla, plantillas = CATEGORIAS[categoria]
            prioridad = _elegir(rng, PESO_PRIORIDAD)
            sla = SLA_HORAS[prioridad]
            antiguedad_h = (hoy - apertura).total_seconds() / 3600
            dentro_sla = rng.random() < p_sla
            horas = sla * rng.uniform(0.15, 0.95) if dentro_sla else sla * rng.uniform(1.1, 4.0)
            # cuanto más reciente, más probable que siga abierta
            p_abierta = 0.6 if antiguedad_h < 48 else 0.25 if antiguedad_h < 24 * 7 else 0.02
            if horas > antiguedad_h or rng.random() < p_abierta:
                cierre, estatus = None, rng.choice(["Abierta", "En progreso"])
            else:
                cierre, estatus = apertura + timedelta(hours=horas), "Cerrada"
            incidencias.append({
                "id_incidencia": f"INC-{n:05d}",
                "fecha_apertura": apertura,
                "fecha_cierre": cierre,
                "prioridad": prioridad,
                "categoria": categoria,
                "equipo": rng.choice(equipos_cat),
                "estatus": estatus,
                "sla_horas": sla,
                "descripcion": _rellenar(rng, rng.choice(plantillas)),
            })
        dia += timedelta(days=1)

    # Ajuste tarjeta 2: P1 abiertas en exactamente 5 equipos, con conteos distintos y legibles
    objetivo_p1 = {"Mesa de Ayuda N1": 3, "Canal Digital": 6, "Punto de Venta": 4,
                   "Pagos y Premios": 7, "Infraestructura TI": 2, EQUIPO_SIN_P1_ABIERTAS: 0}
    for inc in incidencias:
        if inc["prioridad"] == "P1" and inc["estatus"] != "Cerrada":
            inc["estatus"] = "Cerrada"
            inc["fecha_cierre"] = inc["fecha_apertura"] + timedelta(hours=rng.uniform(1, 3.8))
            if inc["fecha_cierre"] > hoy:
                inc["fecha_cierre"] = hoy - timedelta(minutes=5)
    recientes = [i for i in incidencias if (hoy - i["fecha_apertura"]).days <= 10]
    for equipo, cantidad in objetivo_p1.items():
        candidatas = [i for i in recientes if i["equipo"] == equipo and i["prioridad"] != "P1"]
        for inc in rng.sample(candidatas, cantidad):
            inc.update(prioridad="P1", sla_horas=SLA_HORAS["P1"], estatus=rng.choice(["Abierta", "En progreso"]),
                       fecha_cierre=None)

    # ---------------- encuestas_satisfaccion ----------------
    encuestas = []
    for inc in incidencias:
        if inc["estatus"] != "Cerrada" or rng.random() > 0.5:
            continue
        cerro = inc["fecha_cierre"].date()
        horas = (inc["fecha_cierre"] - inc["fecha_apertura"]).total_seconds() / 3600
        media = 4.3 if horas <= inc["sla_horas"] else 2.9
        if inc["equipo"] == EQUIPO_CAIDA_SATISFACCION and mes_pasado <= cerro < _mes_anterior(fecha_taller, 0):
            media -= 1.4  # la caída de la tarjeta 6
        elif inc["equipo"] == EQUIPO_CAIDA_SATISFACCION and mes_antepasado <= cerro < mes_pasado:
            media += 0.3
        calificacion = max(1, min(5, round(rng.gauss(media, 0.8))))
        encuestas.append({
            "id_incidencia": inc["id_incidencia"],
            "calificacion": calificacion,
            "comentario": (_rellenar(rng, rng.choice(QUEJAS_POR_CATEGORIA[inc["categoria"]]))
                           if calificacion <= 2 and rng.random() < 0.7 else rng.choice(COMENTARIOS[calificacion])),
            "fecha_encuesta": cerro,
        })

    # ---------------- proyectos ----------------
    # 4 en riesgo (vencen en ≤30 días y avance < 50%), 3 vencen pronto pero van bien, resto fuera de ventana
    proyectos = []
    riesgo = {0: 22, 1: 35, 2: 41, 3: 15}
    pronto_ok = {4: 78, 5: 64, 6: 90}
    for i, nombre in enumerate(PROYECTOS):
        if i in riesgo:
            compromiso, avance = fecha_taller + timedelta(days=rng.randint(5, 28)), riesgo[i]
        elif i in pronto_ok:
            compromiso, avance = fecha_taller + timedelta(days=rng.randint(5, 28)), pronto_ok[i]
        elif i % 3 == 0:
            compromiso, avance = fecha_taller - timedelta(days=rng.randint(10, 120)), 100
        else:
            compromiso, avance = fecha_taller + timedelta(days=rng.randint(45, 240)), rng.randint(5, 70)
        inicio_p = compromiso - timedelta(days=rng.randint(90, 300))
        if avance == 100:
            estatus = "Completado"
        elif i in riesgo:
            estatus = "En riesgo"
        else:
            estatus = rng.choice(["En curso", "En curso", "En pausa"]) if avance < 100 else "Completado"
        proyectos.append({
            "id_proyecto": f"PRY-{i + 1:03d}",
            "nombre": nombre,
            "responsable": RESPONSABLES[i % len(RESPONSABLES)],
            "fecha_inicio": inicio_p,
            "fecha_compromiso": compromiso,
            "pct_avance": avance,
            "estatus": estatus,
        })

    tablas = {
        "equipos": equipos,
        "incidencias": incidencias,
        "encuestas_satisfaccion": encuestas,
        "proyectos": proyectos,
    }
    tablas.update(generar_reto(rng))
    return tablas


# ---------------- tablas del reto (Lab 3) ----------------
# Textos distintos a los de `incidencias` para que la "respuesta" no esté en las tablas visibles.
RETO_CLASIFICACION = [
    ("Pagos y premios", "Cobré mi premio de Kábala en la web y el dinero nunca llegó a mi cuenta de ahorros."),
    ("Pagos y premios", "Hice una recarga con Yape y el saldo no se refleja en mi billetera Tinka."),
    ("Pagos y premios", "Me cobraron una comisión que no aparece en los términos del retiro."),
    ("Pagos y premios", "Solicité el retiro hace 10 días y figura como 'en revisión'."),
    ("Pagos y premios", "El banco me devolvió la transferencia del premio por datos incorrectos."),
    ("Pagos y premios", "Quiero saber cuánto me descuentan de impuesto por un premio de S/ 5,000."),
    ("Acceso a cuenta", "Cambié de celular y ahora no puedo entrar porque no me llega el código."),
    ("Acceso a cuenta", "Me dice que mi usuario no existe, pero ayer jugué normal."),
    ("Acceso a cuenta", "Alguien cambió mi correo de la cuenta sin mi permiso."),
    ("Acceso a cuenta", "El enlace para restablecer la contraseña dice que ya expiró."),
    ("Acceso a cuenta", "No puedo registrarme porque el sistema no reconoce mi carné de extranjería."),
    ("Acceso a cuenta", "Me bloquearon la cuenta por 'actividad sospechosa' y no hice nada raro."),
    ("Canal digital", "Cada vez que abro la app en mi Android se queda en la pantalla blanca."),
    ("Canal digital", "En la web el botón de 'Jugar' no responde desde Chrome."),
    ("Canal digital", "La app me cobra pero la jugada no aparece en 'Mis jugadas'."),
    ("Canal digital", "Las notificaciones de la app llegan con un día de retraso."),
    ("Canal digital", "No puedo descargar la app desde la tienda de mi iPhone."),
    ("Canal digital", "La web se ve desordenada en el celular y no puedo elegir mis números."),
    ("Punto de venta", "El agente de mi barrio no puede vender Te Apuesto desde el lunes."),
    ("Punto de venta", "Mi ticket ganador está arrugado y la terminal no lo lee."),
    ("Punto de venta", "En la bodega me dijeron que ya no pagan premios mayores a S/ 500."),
    ("Punto de venta", "La impresora de la terminal sale en blanco."),
    ("Punto de venta", "El agente me vendió una jugada pero el ticket salió con otra fecha de sorteo."),
    ("Punto de venta", "La agencia de Trujillo cierra antes del horario publicado."),
    ("Infraestructura", "Los reportes de ventas por agencia no se generaron esta madrugada."),
    ("Infraestructura", "El enlace dedicado con la sede de Arequipa tiene pérdida de paquetes."),
    ("Infraestructura", "La consola de monitoreo marca CPU al 98% en el servidor de sorteos."),
    ("Infraestructura", "El correo corporativo no envía adjuntos de más de 5 MB."),
    ("Infraestructura", "El backup de la base de jugadores terminó con errores."),
    ("Infraestructura", "Se venció la licencia del antivirus en los equipos de la oficina central."),
]

# texto, canal, juego, monto_reclamado (None si no aplica)
RETO_EXTRACCION = [
    ("Hola, compré por la app una jugada de Tinka de S/ 10 y no aparece. Mi número es 987654321.", "app", "Tinka", 10.0),
    ("En la agencia de Surco me negaron el pago de mi premio de Kábala por S/ 350.", "punto de venta", "Kábala", 350.0),
    ("Desde la web intenté retirar S/ 1,200 de mi premio de Ganadiario y salió error.", "web", "Ganadiario", 1200.0),
    ("Llamé al call center porque mi apuesta de Te Apuesto de S/ 25 no se registró.", "call center", "Te Apuesto", 25.0),
    ("Por la app me cobraron S/ 40 por Kinelo dos veces, quiero que me devuelvan uno.", "app", "Kinelo", 40.0),
    ("Fui al punto de venta y la Raspadita premiada de S/ 100 no la quisieron pagar.", "punto de venta", "Raspaditas", 100.0),
    ("Escribo desde la web: mi jugada de Tinka del sábado no participó, pagué S/ 5.", "web", "Tinka", 5.0),
    ("Por WhatsApp me dijeron que el premio de Kábala de S/ 2,500 demora 15 días.", "whatsapp", "Kábala", 2500.0),
    ("En la app no puedo ver los resultados de Ganadiario, no reclamo dinero.", "app", "Ganadiario", None),
    ("Llamé al call center: la recarga de S/ 60 para jugar Te Apuesto no llegó.", "call center", "Te Apuesto", 60.0),
]

# Comentarios negativos para la ronda 3 (respuesta al cliente)
RETO_RESPUESTA = [
    "Pésimo servicio, gané en la Tinka hace dos semanas y sigo sin recibir mi premio.",
    "La app se cerró justo cuando pagaba mi jugada y me cobraron igual. Nadie me responde.",
    "El agente me trató mal y no quiso pagarme el ticket ganador.",
]


def generar_reto(rng):
    clasif = [{"id_reto": i + 1, "descripcion": d, "categoria_real": c} for i, (c, d) in enumerate(RETO_CLASIFICACION)]
    extr = [{"id_reto": i + 1, "texto": t, "canal": c, "juego": j, "monto_reclamado": m}
            for i, (t, c, j, m) in enumerate(RETO_EXTRACCION)]
    resp = [{"id_reto": i + 1, "comentario": c} for i, c in enumerate(RETO_RESPUESTA)]
    return {"reto_clasificacion_gold": clasif, "reto_extraccion_gold": extr, "reto_respuesta_casos": resp}
