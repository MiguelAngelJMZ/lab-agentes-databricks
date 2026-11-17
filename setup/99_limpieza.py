# Databricks notebook source
# MAGIC %md
# MAGIC # Laboratorio de Agentes – La Tinka · Limpieza
# MAGIC
# MAGIC Borra lo que crearon los participantes durante el lab. Primero corre en modo **simular** para ver la lista; después cambia a **borrar**.
# MAGIC
# MAGIC Cada recurso se identifica por su **nombre exacto** y se **comprueba** con una marca que solo deja el lab. Lo que no pasa la comprobación no se borra: aparece en la lista de omitidos con el motivo.
# MAGIC
# MAGIC | Se borra | Comprobación |
# MAGIC |---|---|
# MAGIC | App del agente `agent-bricks-ag-<usuario>` | Su código está en `agentbricks_deployments/agent-bricks-ag-<usuario>` y su `agent.toml` usa el schema `<catálogo>.ag_<usuario>` |
# MAGIC | Stores de memoria y sesiones, experimento de trazas del agente | Solo los nombres **exactos** que declara ese `agent.toml` |
# MAGIC | Experimento de trazas de los labs `lab-agentes-trazas` | Su ruta exacta: `/Users/<correo>/lab-agentes-trazas` (lo crea `Includes/Setup-Lab`) |
# MAGIC | Código desplegado del agente | La carpeta `agentbricks_deployments/agent-bricks-ag-<usuario>` del mismo `agent.toml` |
# MAGIC | App del MCP `mcp-<usuario>` | Su código está en `lab-agentes/mcp-server` o tiene la descripción que le pone el Lab 2 |
# MAGIC | Schema `ag_<usuario>` (CASCADE) | Tiene el comentario que le pone el lab ("Espacio de … en el lab de agentes") |
# MAGIC | Carpeta `Lab Agentes La Tinka` (del usuario y de Shared) | Contiene `Includes/_config.py`, que escribe el setup |
# MAGIC | Dentro de `lab-agentes`: `mcp-server` y el proyecto `ag-<usuario>` | `mcp-server` trae el servidor del lab; el proyecto usa el schema del lab. `lab-agentes` solo se borra si queda vacía |
# MAGIC
# MAGIC **Nunca** borra: el catálogo, los datos de `mesa_servicio`, el Genie, el warehouse, otras apps, otros schemas ni otras carpetas.

# COMMAND ----------

dbutils.widgets.text("catalogo", "la_tinka_taller", "1. Catálogo")
dbutils.widgets.text("esquema_datos", "mesa_servicio", "2. Esquema de datos (nunca se borra)")
dbutils.widgets.text("grupo_participantes", "lab_agentes", "3. Grupo de participantes")
dbutils.widgets.dropdown("modo", "simular", ["simular", "borrar"], "4. Modo")

# COMMAND ----------

import re
import tomllib
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
CATALOGO = dbutils.widgets.get("catalogo").strip()
ESQUEMA_DATOS = dbutils.widgets.get("esquema_datos").strip()
GRUPO = dbutils.widgets.get("grupo_participantes").strip()
BORRAR = dbutils.widgets.get("modo") == "borrar"
CARPETA_LAB = "Lab Agentes La Tinka"
DESCRIPCION_MCP = "MCP de la mesa de servicio (lab de agentes)"  # la pone el Lab 2 al crear la app


def slug(usuario):
    """Mismo cálculo que labs/Includes/Setup-Lab: parte local del correo en minúsculas."""
    return re.sub(r"[^a-z0-9]+", "_", usuario.split("@")[0].lower()).strip("_")[:40]


def existe(ruta):
    try:
        w.workspace.get_status(ruta)
        return True
    except Exception:
        return False


def leer(ruta):
    try:
        return w.workspace.download(ruta).read().decode("utf-8")
    except Exception:
        return None


def hijos(ruta):
    """Contenido de una carpeta, o None si no se pudo listar (entonces no se borra)."""
    try:
        return [o.path for o in w.workspace.list(ruta)]
    except Exception:
        return None


def listar_stores(tipo):
    """memory-stores o session-stores, paginado de a 100 (el máximo de la API)."""
    items, token = [], None
    while True:
        query = {"page_size": 100, **({"page_token": token} if token else {})}
        r = w.api_client.do("GET", f"/api/2.0/agents/{tipo}", query=query)
        items += next((v for v in r.values() if isinstance(v, list)), [])
        token = r.get("next_page_token")
        if not token:
            return items


def ruta_codigo(app):
    d = getattr(app, "active_deployment", None) or getattr(app, "pending_deployment", None)
    return (d.source_code_path if d else None) or app.default_source_code_path


grupo = next(iter(w.groups.list(filter=f'displayName eq "{GRUPO}"', attributes="id")), None)
assert grupo, f"No encuentro el grupo {GRUPO}"
usuarios = [w.users.get(m.value).user_name for m in (w.groups.get(grupo.id).members or []) if m.ref and m.ref.startswith("Users/")]
print(f"{len(usuarios)} participantes en {GRUPO}")

# COMMAND ----------

# MAGIC %md ## 1. Qué se borraría

# COMMAND ----------

apps = {a.name: a for a in w.apps.list()}
stores = {}
for tipo in ("memory-stores", "session-stores"):
    try:
        for st in listar_stores(tipo):
            stores[st.get("display_name") or st["name"].split("/", 1)[1]] = st["name"]
    except Exception as e:
        print(f"⚠ No pude listar {tipo}: {str(e)[:120]}")

PLAN, OMITIDOS = [], []  # (usuario, recurso, función) · (usuario, recurso, motivo)


def borrar(u, recurso, funcion):
    PLAN.append((u, recurso, funcion))


def omitir(u, recurso, motivo):
    OMITIDOS.append((u, recurso, motivo))


for u in usuarios:
    s = slug(u)
    esquema = f"ag_{s}"
    marca_esquema = f"{CATALOGO}.{esquema}."
    agente = f"ag-{s.replace('_', '-')}"[:17].rstrip("-")
    app_agente, app_mcp = f"agent-bricks-{agente}", f"mcp-{s.replace('_', '-')}"[:30].rstrip("-")
    casa = f"/Workspace/Users/{u}"
    despliegue, trabajo = f"{casa}/agentbricks_deployments/{app_agente}", f"{casa}/lab-agentes"

    # Agente: el agent.toml del despliegue (o del proyecto de 03B) dice qué recursos son suyos.
    toml_txt = leer(f"{despliegue}/agent.toml") or leer(f"{trabajo}/{agente}/agent.toml")
    del_lab = bool(toml_txt) and marca_esquema in toml_txt
    if app_agente in apps:
        if del_lab and ruta_codigo(apps[app_agente]) == despliegue:
            borrar(u, f"app {app_agente}", lambda n=app_agente: w.apps.delete(n))
        else:
            omitir(u, f"app {app_agente}", "su código o su agent.toml no son los del lab")
    if del_lab:
        cfg = tomllib.loads(toml_txt)
        for clave in ("memory_store", "session_store"):
            nombre = cfg.get(clave, {}).get("name")
            if nombre in stores:
                borrar(u, f"store {nombre}", lambda r=stores[nombre]: w.api_client.do("DELETE", f"/api/2.0/agents/{r}"))
        experimento = cfg.get("tracing", {}).get("experiment_name")
        if experimento and experimento.startswith(f"/Shared/agentbricks_traces/{agente}-"):
            exp = w.experiments.get_by_name(experimento).experiment if existe(experimento) else None
            if exp:
                borrar(u, f"experimento {experimento}", lambda i=exp.experiment_id: w.experiments.delete_experiment(i))
        if existe(despliegue):
            borrar(u, f"carpeta {despliegue}", lambda c=despliegue: w.workspace.delete(c, recursive=True))
    elif existe(despliegue):
        omitir(u, f"carpeta {despliegue}", "su agent.toml no usa el schema del lab")

    # MCP del Lab 2
    if app_mcp in apps:
        a = apps[app_mcp]
        if ruta_codigo(a) == f"{trabajo}/mcp-server" or (a.description or "") == DESCRIPCION_MCP:
            borrar(u, f"app {app_mcp}", lambda n=app_mcp: w.apps.delete(n))
        else:
            omitir(u, f"app {app_mcp}", "no la creó el Lab 2 (código y descripción distintos)")

    # Schema del participante
    if esquema == ESQUEMA_DATOS or not esquema.startswith("ag_"):
        omitir(u, f"schema {CATALOGO}.{esquema}", "nombre protegido")
    else:
        try:
            comentario = w.schemas.get(f"{CATALOGO}.{esquema}").comment or ""
            if comentario.startswith("Espacio de ") and comentario.endswith("en el lab de agentes"):
                n_obj = len(list(w.tables.list(CATALOGO, esquema))) + len(list(w.functions.list(CATALOGO, esquema)))
                borrar(u, f"schema {CATALOGO}.{esquema} (CASCADE, {n_obj} tablas/funciones)",
                       lambda e=esquema: spark.sql(f"DROP SCHEMA IF EXISTS `{CATALOGO}`.`{e}` CASCADE"))
            else:
                omitir(u, f"schema {CATALOGO}.{esquema}", f"no tiene el comentario del lab ({comentario[:60]!r})")
        except Exception:
            pass  # no existe

    # Experimento de trazas del lab (lo crea Includes/Setup-Lab)
    exp_lab = f"{casa}/lab-agentes-trazas"
    if existe(exp_lab):
        e_lab = w.experiments.get_by_name(exp_lab).experiment
        borrar(u, f"experimento {exp_lab}", lambda i=e_lab.experiment_id: w.experiments.delete_experiment(i))

    # Carpetas
    carpeta_lab = f"{casa}/{CARPETA_LAB}"
    if existe(carpeta_lab):
        if existe(f"{carpeta_lab}/Includes/_config.py"):
            borrar(u, f"carpeta {carpeta_lab}", lambda c=carpeta_lab: w.workspace.delete(c, recursive=True))
        else:
            omitir(u, f"carpeta {carpeta_lab}", "no tiene Includes/_config.py del setup")
    if existe(trabajo):
        del_trabajo = []
        mcp_dir, proyecto = f"{trabajo}/mcp-server", f"{trabajo}/{agente}"
        if existe(mcp_dir) and "mcp-mesa-servicio" in (leer(f"{mcp_dir}/server/tools.py") or ""):
            del_trabajo.append(mcp_dir)
        if existe(proyecto) and marca_esquema in (leer(f"{proyecto}/agent.toml") or ""):
            del_trabajo.append(proyecto)
        for c in del_trabajo:
            borrar(u, f"carpeta {c}", lambda c=c: w.workspace.delete(c, recursive=True))
        contenido = hijos(trabajo)
        resto = None if contenido is None else [h for h in contenido if h not in del_trabajo]
        if resto is None:
            omitir(u, f"carpeta {trabajo}", "no pude listar su contenido")
        elif resto:
            omitir(u, f"carpeta {trabajo}", f"tiene otro contenido: {', '.join(h.rsplit('/', 1)[-1] for h in resto)[:120]}")
        else:
            borrar(u, f"carpeta {trabajo} (queda vacía)", lambda c=trabajo: w.workspace.delete(c, recursive=True))

compartida = f"/Workspace/Shared/{CARPETA_LAB}"
if existe(compartida):
    if existe(f"{compartida}/Includes/_config.py"):
        borrar("Shared", f"carpeta {compartida}", lambda: w.workspace.delete(compartida, recursive=True))
    else:
        omitir("Shared", f"carpeta {compartida}", "no tiene Includes/_config.py del setup")

filas = "".join(f"<tr><td>{u}</td><td><code>{r}</code></td></tr>" for u, r, _ in PLAN) or "<tr><td colspan=2>Nada que borrar</td></tr>"
filas_om = "".join(f"<tr><td>{u}</td><td><code>{r}</code></td><td>{m}</td></tr>" for u, r, m in OMITIDOS)
displayHTML(f"""<div style="font-family:-apple-system,Segoe UI,sans-serif;font-size:14px;color:#1B3139">
<h3 style="margin:0 0 6px">{'Se borrará' if not BORRAR else 'Borrando'} ({len(PLAN)})</h3>
<table style="border-collapse:collapse">{filas}</table>
{f'<h3 style="margin:16px 0 6px;color:#B26B00">Omitidos: no se tocan ({len(OMITIDOS)})</h3><table style="border-collapse:collapse">{filas_om}</table>' if OMITIDOS else ''}
</div>""")

# COMMAND ----------

# MAGIC %md ## 2. Borrar (solo en modo `borrar`)

# COMMAND ----------

if not BORRAR:
    print("Modo simular: no se borró nada. Revisa la lista, cambia 'modo' a 'borrar' y vuelve a correr el notebook.")
else:
    errores = 0
    for u, recurso, funcion in PLAN:
        try:
            funcion()
            print(f"🗑  {u}: {recurso}")
        except Exception as e:
            errores += 1
            print(f"⚠  {u}: {recurso} → {str(e)[:160]}")
    print(f"\n✓ Listo: {len(PLAN) - errores} borrados, {errores} con error, {len(OMITIDOS)} omitidos.")
