"""Genera los notebooks de labs/ a partir de las fuentes compactas de herramientas/fuentes/*.nb.

Formato de una fuente:
    === md            celda markdown (pasa a %md-sandbox si tiene HTML o macros)
    === py            celda Python
    === sql           celda SQL (%sql)
    === pip           celda %pip (una línea con los paquetes)
    === run <ruta>    celda %run

Macros dentro de una celda md (una por línea):
    ::pill LECTURA | DEMO | RETO | UI     etiqueta de color junto al título de la celda
    ::nota <título> | <texto>            recuadro informativo
    ::alerta <título> | <texto>          recuadro de advertencia
    ::docs <texto del link> | <url>      línea de documentación

Uso:  python3 herramientas/construir_notebooks.py
"""

import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "herramientas" / "fuentes"
DESTINO = RAIZ / "labs"

PILLS = {"LECTURA": "#5A6F77", "DEMO": "#2E7D32", "RETO": "#FF3621", "UI": "#2272B4"}

PILL_JS = """<script>
(function() {{
  var TEXT='{texto}', ACCENT='{color}';
  var base='display:inline-block; border-radius:4px; padding:3px 10px; font-size:11px; font-weight:700; letter-spacing:0.06em; margin-left:10px; vertical-align:middle;';
  var el=document.currentScript, h=null;
  while (el && !h) {{ h = el.querySelector ? el.querySelector('h1,h2,h3,h4,h5,h6') : null; if (!h) el=el.parentElement; }}
  if (!h || h.querySelector('[data-pill]')) return;
  var span=document.createElement('span');
  span.setAttribute('data-pill','1');
  span.style.cssText=base+'background:'+ACCENT+'; color:#ffffff;';
  span.textContent=TEXT;
  h.appendChild(span);
}})();
</script>"""

CAJA = """<div style="border:1px solid #DCE0E2; border-left:4px solid {borde}; border-radius:10px; background:{fondo}; padding:12px 16px; margin:12px 0; color:#0B2026; font-size:14px; line-height:1.55;">
<strong style="color:{borde};">{titulo}</strong><br>{texto}
</div>"""


def macro(linea):
    m = re.match(r"::(\w+)\s+(.*)", linea.strip())
    if not m:
        return linea
    tipo, resto = m.group(1), m.group(2)
    if tipo == "pill":
        texto = resto.strip()
        return PILL_JS.format(texto=texto, color=PILLS[texto])
    partes = [p.strip() for p in resto.split("|", 1)] + [""]
    if tipo == "nota":
        return CAJA.format(borde="#1B5162", fondo="#F9F7F4", titulo=partes[0], texto=partes[1])
    if tipo == "alerta":
        return CAJA.format(borde="#FF3621", fondo="#FFF5F3", titulo=partes[0], texto=partes[1])
    if tipo == "docs":
        return (f'<p style="font-size:13px; color:#5A6F77;"><strong>Documentación:</strong> '
                f'<a href="{partes[1]}" target="_blank" style="color:#2272B4;">{partes[0]}</a></p>')
    raise ValueError(f"Macro desconocida: {linea}")


def celda(tipo, cuerpo):
    lineas = cuerpo.strip("\n").split("\n")
    if tipo == "py":
        return "\n".join(lineas)
    if tipo == "pip":
        return f"# MAGIC %pip install -q {lineas[0].strip()}"
    if tipo.startswith("run "):
        return f"# MAGIC %run {tipo[4:].strip()}"
    if tipo == "sql":
        return "\n".join(["# MAGIC %sql"] + [f"# MAGIC {l}".rstrip() for l in lineas])
    if tipo == "md":
        expandidas = []
        for l in lineas:
            expandidas.extend(macro(l).split("\n") if l.strip().startswith("::") else [l])
        sandbox = any("<" in l and ">" in l for l in expandidas)
        cabecera = "# MAGIC %md-sandbox" if sandbox else "# MAGIC %md"
        return "\n".join([cabecera] + [f"# MAGIC {l}".rstrip() for l in expandidas])
    raise ValueError(f"Tipo de celda desconocido: {tipo}")


def construir(fuente):
    texto = fuente.read_text(encoding="utf-8")
    nombre = texto.split("\n", 1)[0].removeprefix("#!").strip()
    bloques = re.split(r"^=== (.+)$", texto.split("\n", 1)[1], flags=re.M)[1:]
    celdas = [celda(bloques[i].strip(), bloques[i + 1]) for i in range(0, len(bloques), 2)]
    salida = "# Databricks notebook source\n" + "\n\n# COMMAND ----------\n\n".join(celdas) + "\n"
    destino = DESTINO / f"{nombre}.py"
    destino.write_text(salida, encoding="utf-8")
    print(f"✓ {destino.relative_to(RAIZ)} ({len(celdas)} celdas)")


if __name__ == "__main__":
    for f in sorted(FUENTES.glob("*.nb")):
        construir(f)
