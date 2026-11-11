# Solución · Lab 2 · Reto: agregar una tool de negocio al MCP
#
# Es la misma función de la sección E.1 del notebook del Lab 2. Pégala al final de server/tools.py,
# debajo del comentario "# RETO del Lab 2", con 4 espacios de sangría, y corre la celda E.3.

    @mcp_server.tool
    def prioridad_sugerida(descripcion: str) -> dict:
        """Sugiere la prioridad (P1 a P4) de un reclamo nuevo de la mesa de servicio a partir de su texto.

        Úsala cuando alguien describa un problema y pregunte qué prioridad debería tener o qué tan
        urgente es. Devuelve la prioridad, las horas de SLA que le corresponden y la regla aplicada.

        Args:
            descripcion: texto del reclamo tal como lo escribió el usuario o el agente de venta.
        """
        texto = descripcion.lower()
        reglas = [
            ("P1", ("caído", "caido", "no vende", "no puedo vender", "premio", "no llegó el pago", "rechaza pagos"),
             "Afecta ventas o el pago de premios"),
            ("P2", ("error", "no puedo", "no carga", "rechazada", "pendiente"),
             "Falla que impide una operación del usuario"),
            ("P3", ("lento", "demora", "notificación", "historial"),
             "Degradación o funcionalidad secundaria"),
        ]
        for prioridad, palabras, motivo in reglas:
            encontradas = [p for p in palabras if p in texto]
            if encontradas:
                return {"prioridad": prioridad, "sla_horas": SLA_HORAS[prioridad],
                        "regla": motivo, "palabras_clave": encontradas}
        return {"prioridad": "P4", "sla_horas": SLA_HORAS["P4"], "regla": "Consulta o pedido sin impacto operativo",
                "palabras_clave": []}
