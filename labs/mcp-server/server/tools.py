"""Tools del servidor MCP de la mesa de servicio.

El docstring de cada tool es lo que lee el LLM para decidir cuándo llamarla:
escríbelo como si le explicaras la tool a un colega nuevo.
"""

from datetime import date

from server import utils

# Horas comprometidas por prioridad (las mismas de la tabla incidencias).
SLA_HORAS = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}
ESCALAMIENTO = {
    "P1": "Gerente del equipo + guardia de Infraestructura TI",
    "P2": "Gerente del equipo",
    "P3": "Líder técnico del equipo",
    "P4": "Sin escalamiento",
}
JUEGOS = ["Tinka", "Kábala", "Ganadiario", "Te Apuesto", "Kinelo", "Raspaditas"]


def load_tools(mcp_server):
    @mcp_server.tool
    def health() -> dict:
        """Comprueba que el servidor MCP está activo. Úsala solo para diagnosticar la conexión."""
        return {"status": "healthy", "servidor": "mcp-mesa-servicio"}

    @mcp_server.tool
    def calcular_sla(prioridad: str, horas_abierta: float) -> dict:
        """Calcula el estado de SLA de una incidencia de la mesa de servicio.

        Úsala cuando necesites saber si una incidencia está dentro del SLA, en riesgo o
        vencida, cuántas horas le quedan y a quién hay que escalarla.

        Args:
            prioridad: P1, P2, P3 o P4.
            horas_abierta: horas que lleva abierta la incidencia.
        """
        p = prioridad.strip().upper()
        if p not in SLA_HORAS:
            return {"error": f"Prioridad desconocida '{prioridad}'. Usa P1, P2, P3 o P4."}
        sla = SLA_HORAS[p]
        consumo = horas_abierta / sla
        estado = "vencida" if consumo >= 1 else "en riesgo" if consumo >= 0.8 else "dentro del SLA"
        return {
            "prioridad": p,
            "sla_horas": sla,
            "horas_abierta": round(horas_abierta, 1),
            "pct_sla_consumido": round(consumo * 100, 1),
            "horas_restantes": round(max(sla - horas_abierta, 0), 1),
            "estado": estado,
            "escalar_a": ESCALAMIENTO[p] if estado != "dentro del SLA" else "No requiere",
        }

    @mcp_server.tool
    def estado_plataforma_juego(juego: str) -> dict:
        """Consulta el estado operativo de la plataforma de un juego de La Tinka.

        Simula una API interna de monitoreo. Úsala cuando el usuario pregunte si un juego
        (Tinka, Kábala, Ganadiario, Te Apuesto, Kinelo o Raspaditas) tiene una caída o
        degradación que explique un aumento de incidencias.

        Args:
            juego: nombre del juego.
        """
        nombre = next((j for j in JUEGOS if j.lower() == juego.strip().lower()), None)
        if not nombre:
            return {"error": f"Juego desconocido '{juego}'. Opciones: {', '.join(JUEGOS)}"}
        # Respuesta determinista: cambia por día y juego, sin depender de un servicio externo.
        semilla = (sum(map(ord, nombre)) + date.today().toordinal()) % 10
        estado = "degradado" if semilla in (0, 1) else "caído" if semilla == 2 else "operativo"
        return {
            "juego": nombre,
            "estado": estado,
            "latencia_p95_ms": 180 + semilla * 95,
            "fuente": "API interna de monitoreo (simulada)",
        }

    @mcp_server.tool
    def usuario_actual() -> dict:
        """Devuelve quién está llamando al servidor MCP (identidad del usuario final)."""
        try:
            me = utils.get_user_authenticated_workspace_client().current_user.me()
            return {"usuario": me.user_name, "nombre": me.display_name}
        except Exception as e:
            return {"error": str(e)}

    # RETO del Lab 2: pega aquí la función prioridad_sugerida (sección E del notebook), con esta misma sangría.
