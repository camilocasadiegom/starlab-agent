from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.datastructures import URL
from pathlib import Path
import csv, os, math, html
from datetime import datetime

APP_TITLE = "STARLINX • Protoapp"
app = FastAPI(title=APP_TITLE)

# ==== Config ====
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CSV_PATH = DATA_DIR / "registro.csv"
FIELDS = ["timestamp","ip","nombre","documento","telefono","email","ciudad","vehiculo"]

ADMIN_KEY = os.getenv("ADMIN_KEY", "starlab123")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Crear CSV con encabezados si no existe
if not CSV_PATH.exists():
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(FIELDS)

# ==== Utilidades ====
def is_admin(request: Request, k: str | None) -> bool:
    if request.session.get("admin_ok"):
        return True
    if k and k == ADMIN_KEY:
        return True
    return False

def require_admin(request: Request, k: str | None):
    if not is_admin(request, k):
        raise HTTPException(status_code=401, detail="no autorizado")

def read_rows():
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)

def append_row(row: dict):
    # Asegurar orden de campos
    out = [row.get(h, "") for h in FIELDS]
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(out)

def h(s: str) -> str:
    return html.escape(str(s), quote=True)

# ==== UI base ====
BASE_CSS = """
<style>
:root{--bg:#f6f7fb;--card:#fff;--accent:#0b5ed7;--muted:#6b7280}
*{box-sizing:border-box} body{margin:0;font-family:Inter,system-ui,Arial,sans-serif;background:var(--bg);color:#111827}
.container{max-width:920px;margin:24px auto;padding:0 16px}
.card{background:var(--card);border-radius:14px;box-shadow:0 8px 24px rgba(0,0,0,.06);padding:22px}
a{color:var(--accent);text-decoration:none} a:hover{text-decoration:underline}
.btn{display:inline-block;background:var(--accent);color:#fff;padding:10px 14px;border-radius:10px;font-weight:600}
.btn.muted{background:#e5e7eb;color:#111827}
.grid{display:grid;gap:16px}
@media(min-width:720px){.grid.cols-2{grid-template-columns:1fr 1fr}}
label{display:block;font-size:14px;color:#111827;margin-bottom:6px}
input,select{width:100%;padding:10px 12px;border:1px solid #e5e7eb;border-radius:10px;font-size:14px;background:#fff}
table{border-collapse:collapse;width:100%} th,td{border:1px solid #e5e7eb;padding:8px 10px;font-size:14px}
th{background:#fafafa;text-align:left}
.pager{display:flex;gap:8px;margin-top:14px}
.badge{background:#eef2ff;color:#1f3a8a;padding:2px 8px;border-radius:999px;font-size:12px}
.muted{color:var(--muted)}
</style>
"""

def page(title: str, body_html: str) -> HTMLResponse:
    html_doc = f"""<!doctype html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{h(title)}</title>
{BASE_CSS}
</head><body>
<div class="container">
  <div class="card">
    <h1 style="margin-top:0">{h(title)}</h1>
    {body_html}
  </div>
  <p class="muted" style="margin-top:12px">{h(APP_TITLE)}</p>
</div>
</body></html>"""
    return HTMLResponse(html_doc)

# ==== Rutas públicas ====
@app.get("/", response_class=HTMLResponse)
def home():
    body = f"""
    <div class="grid cols-2">
      <div>
        <h2>Bienvenido</h2>
        <p>Usa el formulario para registrar conductores. El panel es solo para administradores.</p>
        <div style="display:flex; gap:10px; flex-wrap:wrap">
          <a class="btn" href="/registro">Registrar conductor</a>
          <a class="btn muted" href="/acceso">Acceso admin</a>
          <a class="btn muted" href="/panel">Panel</a>
        </div>
      </div>
      <div>
        <div class="badge">Atajo</div>
        <p><a href="/docs">Ver API docs</a></p>
      </div>
    </div>
    """
    return page("Inicio", body)

@app.get("/registro", response_class=HTMLResponse)
def registro_form():
    body = f"""
    <form method="post" action="/registro" class="grid">
      <div class="grid cols-2">
        <div><label>Nombre</label><input name="nombre" required></div>
        <div><label>Documento</label><input name="documento" required></div>
      </div>
      <div class="grid cols-2">
        <div><label>Teléfono</label><input name="telefono" required></div>
        <div><label>Email</label><input name="email" type="email"></div>
      </div>
      <div class="grid cols-2">
        <div><label>Ciudad</label><input name="ciudad"></div>
        <div><label>Tipo de vehículo</label>
          <select name="vehiculo">
            <option value="">(selecciona)</option>
            <option>Sedan</option><option>SUV</option><option>Van</option>
            <option>Premium</option><option>Otro</option>
          </select>
        </div>
      </div>
      <div><button class="btn" type="submit">Enviar registro</button></div>
    </form>
    """
    return page("Registro de Conductores", body)

@app.post("/registro")
def registro_submit(request: Request,
    nombre: str = Form(...),
    documento: str = Form(...),
    telefono: str = Form(...),
    email: str = Form(""),
    ciudad: str = Form(""),
    vehiculo: str = Form("")
):
    ts = datetime.now().isoformat(timespec="seconds")
    ip = request.client.host if request.client else "-"
    row = {
        "timestamp": ts,
        "ip": ip,
        "nombre": nombre.strip(),
        "documento": documento.strip(),
        "telefono": telefono.strip(),
        "email": email.strip(),
        "ciudad": ciudad.strip(),
        "vehiculo": vehiculo.strip(),
    }
    append_row(row)
    return page("Registro recibido", f"""
      <p><b>¡Gracias!</b> Tu registro fue guardado.</p>
      <p><a class='btn' href='/registro'>Nuevo registro</a>
         <a class='btn muted' href='/'>Inicio</a></p>
    """)

# Salud y ping (para pruebas / uptime)
@app.get("/health")
def health():
    return {"ok": True, "service": "starlinx-protoapp"}

@app.get("/ping")
def ping():
    return JSONResponse({"pong": True})

# ==== Acceso admin (sesión) ====
@app.get("/acceso", response_class=HTMLResponse)
def acceso_form():
    body = """
    <form method="post" action="/acceso" class="grid">
      <div><label>Clave de administrador</label><input name="k" type="password" required></div>
      <div><button class="btn" type="submit">Entrar</button></div>
    </form>
    """
    return page("Acceso administrador", body)

@app.post("/acceso")
def acceso_login(request: Request, k: str = Form(...)):
    if k == ADMIN_KEY:
        request.session["admin_ok"] = True
        return RedirectResponse("/panel", status_code=303)
    return page("Acceso administrador", "<p>Clave inválida.</p>" +
                "<p><a class='btn muted' href='/acceso'>Volver</a></p>")

@app.get("/salir")
def salir(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

# ==== Panel y registros (admin) ====
@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request, k: str | None = None):
    # permite sesión o ?k=
    if not is_admin(request, k):
        return page("Panel administrador", """
          <p>Necesitas iniciar sesión o pasar la clave por URL.</p>
          <p><a class='btn' href='/acceso'>Iniciar sesión</a></p>
        """)
    rows = read_rows()
    body = f"""
      <p>Registros guardados: <b>{len(rows)}</b></p>
      <p>
        <a class="btn" href="/registros">Ver registros</a>
        <a class="btn muted" href="/export/csv">Exportar CSV</a>
        <a class="btn muted" href="/export/json">Exportar JSON</a>
        <a class="btn muted" href="/salir">Salir</a>
      </p>
    """
    return page("Panel administrador", body)

@app.get("/registros", response_class=HTMLResponse)
def registros(request: Request, k: str | None = None, q: str | None = None, page_i: int | None = None, page: int = 1):
    require_admin(request, k)
    rows = read_rows()

    # Búsqueda simple (en cualquier campo)
    q = (q or "").strip().lower()
    if q:
        def match(r):
            return any(q in (r.get(c,"").lower()) for c in FIELDS)
        rows = list(filter(match, rows))

    # Paginación
    per = 20
    total = len(rows)
    pages = max(1, math.ceil(total/per))
    page = max(1, min(page, pages))
    start = (page-1)*per
    page_rows = rows[start:start+per]

    # Tabla
    headers_html = "".join(f"<th>{h(col)}</th>" for col in FIELDS)
    trs = []
    for r in page_rows:
        tds = "".join(f"<td>{h(r.get(c,''))}</td>" for c in FIELDS)
        trs.append(f"<tr>{tds}</tr>")
    table_html = f"<table><thead><tr>{headers_html}</tr></thead><tbody>{''.join(trs) or '<tr><td colspan=\"99\">(sin datos)</td></tr>'}</tbody></table>"

    # Paginador
    base = str(URL(str(request.url)).replace_query_params())
    def link(num): 
        return str(URL(base).include_query_params(page=num))
    pager = "<div class='pager'>" + " ".join(
        f"<a class='btn muted' href='{h(link(i))}'>{i}</a>" for i in range(1, pages+1)
    ) + "</div>"

    body = f"""
      <form method="get" class="grid" style="margin-bottom:10px">
        <input type="hidden" name="page" value="1">
        <div class="grid cols-2">
          <div>
            <label>Buscar (cualquier campo)</label>
            <input name="q" value="{h(q)}" placeholder="nombre, documento, teléfono, email...">
          </div>
          <div style="align-self:end"><button class="btn" type="submit">Filtrar</button></div>
        </div>
      </form>
      <p class="muted">Total: {total}</p>
      {table_html}
      {pager}
      <p style="margin-top:12px">
        <a class="btn muted" href="/export/csv">Exportar CSV</a>
        <a class="btn muted" href="/export/json">Exportar JSON</a>
        <a class="btn" href="/panel">Volver</a>
      </p>
    """
    return page("Registros", body)

# ==== Exportaciones ====
@app.get("/export/csv")
def export_csv(request: Request, k: str | None = None):
    require_admin(request, k)
    with CSV_PATH.open("r", encoding="utf-8") as f:
        content = f.read()
    return PlainTextResponse(content, media_type="text/csv", headers={
        "Content-Disposition": 'attachment; filename="registros.csv"'
    })

@app.get("/export/json")
def export_json(request: Request, k: str | None = None):
    require_admin(request, k)
    return JSONResponse(read_rows())
# --------- [AUTO-ADD] Admin DB utilities (no rompe la UI existente) ----------
try:
    import os
    from fastapi import HTTPException
    from sqlalchemy import create_engine, text

    _ADMIN_KEY = os.getenv("ADMIN_KEY", "starlab123")

    def _get_engine():
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL no definido")
        return create_engine(url, pool_pre_ping=True)

    def _ensure_table():
        eng = _get_engine()
        with eng.begin() as cx:
            cx.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS conductores(
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                    nombre TEXT NOT NULL,
                    documento TEXT NOT NULL,
                    telefono TEXT NOT NULL
                )
            """)
        return True

    @app.get("/admin/db-init")
    def admin_db_init(k: str):
        if k != _ADMIN_KEY:
            raise HTTPException(status_code=401, detail="no autorizado")
        try:
            ok = _ensure_table()
            return {"ok": ok, "msg": "tabla conductores lista"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/admin/db-test")
    def admin_db_test(k: str):
        if k != _ADMIN_KEY:
            raise HTTPException(status_code=401, detail="no autorizado")
        url = os.getenv("DATABASE_URL")
        if not url:
            raise HTTPException(status_code=400, detail="DATABASE_URL no está definido")
        eng = _get_engine()
        with eng.connect() as c:
            ver = c.execute(text("select version()")).scalar_one()
        return {"ok": True, "version": ver}
except Exception as _e:
    # No interrumpir la app si falta SQLAlchemy o no hay DB todavía.
    pass
# ------------------------------------------------------------------------------
# == STARLINX ADMIN DB ENDPOINTS (idempotente) ==
from fastapi import HTTPException
import os, sqlite3

ADMIN_KEY = os.getenv("ADMIN_KEY", "starlab123")

def _get_conn():
    dburl = os.getenv("DATABASE_URL", "")
    # Si hay Postgres, úsalo
    if dburl.startswith("postgres://") or dburl.startswith("postgresql://"):
        import psycopg
        return psycopg.connect(dburl)
    # Fallback sqlite temporal (ej. en Render /tmp)
    return sqlite3.connect("/tmp/starlinx.db")

@app.get("/admin/db-init")
def admin_db_init(k: str):
    if k != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="no autorizado")
    con = _get_conn()
    try:
        cur = con.cursor()
        try:
            # DDL compatible Postgres
            cur.execute("""
            CREATE TABLE IF NOT EXISTS registros(
              id SERIAL PRIMARY KEY,
              ts TIMESTAMP DEFAULT NOW(),
              nombre TEXT,
              documento TEXT,
              telefono TEXT
            )
            """)
        except Exception:
            # Fallback sqlite
            cur.execute("""
            CREATE TABLE IF NOT EXISTS registros(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts TEXT,
              nombre TEXT,
              documento TEXT,
              telefono TEXT
            )
            """)
        con.commit()
        return {"ok": True, "action": "db-init"}
    finally:
        con.close()

@app.get("/admin/db-test")
def admin_db_test(k: str):
    if k != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="no autorizado")
    con = _get_conn()
    try:
        try:
            ver = con.execute("select version()").fetchone()[0]
        except Exception:
            ver = "sqlite/" + sqlite3.sqlite_version
        return {"ok": True, "version": ver}
    finally:
        con.close()

@app.get("/admin/db-count")
def admin_db_count(k: str):
    if k != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="no autorizado")
    con = _get_conn()
    try:
        cur = con.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM registros")
        except Exception:
            return {"count": 0, "note": "tabla no existe aún; ejecuta /admin/db-init"}
        n = cur.fetchone()[0]
        return {"count": n}
    finally:
        con.close()
# == /STARLINX ADMIN ==
# === STARLINX DB FIX ROUTES ===
from fastapi import APIRouter, HTTPException, Depends, Request
from starlette.responses import JSONResponse
import os

try:
    import db_fix
except Exception as e:
    # fallback por si el import falla
    db_fix = None

admin_fix = APIRouter(prefix="/admin/fix", tags=["admin-fix"])

def _auth_ok(req: Request):
    # acepta ?k=... o header X-Admin-Key (compatible con lo que ya usas)
    kq = req.query_params.get("k")
    kh = req.headers.get("X-Admin-Key")
    admin_key = os.getenv("ADMIN_KEY", "starlab123")
    return (kq == admin_key) or (kh == admin_key)

@admin_fix.get("/db-init")
def db_init_fix(request: Request):
    if not _auth_ok(request):
        raise HTTPException(status_code=401, detail="unauthorized")
    if db_fix is None:
        raise HTTPException(status_code=500, detail="db_fix import failed")
    try:
        con = db_fix.connect_sqlite()
        db_fix.ensure_table(con)
        con.close()
        return {"ok": True, "msg": "tabla creada (IF NOT EXISTS)", "driver": "sqlite", "path": db_fix.get_sqlite_path()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_fix.get("/db-test")
def db_test_fix(request: Request):
    if not _auth_ok(request):
        raise HTTPException(status_code=401, detail="unauthorized")
    if db_fix is None:
        raise HTTPException(status_code=500, detail="db_fix import failed")
    try:
        path = db_fix.get_sqlite_path()
        return {"driver": "sqlite", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_fix.get("/db-count")
def db_count_fix(request: Request):
    if not _auth_ok(request):
        raise HTTPException(status_code=401, detail="unauthorized")
    if db_fix is None:
        raise HTTPException(status_code=500, detail="db_fix import failed")
    try:
        con = db_fix.connect_sqlite()
        n = db_fix.count_rows(con)
        if n is None:
            # crear tabla automáticamente
            db_fix.ensure_table(con)
            n = 0
        con.close()
        return {"count": int(n)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Montar router en la app principal
try:
    app.include_router(admin_fix)
except Exception:
    pass
# === /STARLINX DB FIX ROUTES ===
# === STARLINX ADMIN ALIASES ===
from fastapi import Request, HTTPException

def _path_registered(app, path, method):
    try:
        for r in app.router.routes:
            if getattr(r, "path", None) == path and method.upper() in getattr(r, "methods", set()):
                return True
    except Exception:
        pass
    return False

if not _path_registered(app, "/admin/db-init", "GET"):
    @app.get("/admin/db-init", tags=["admin"])
    def _admin_db_init_alias(request: Request):
        return db_init_fix(request)

if not _path_registered(app, "/admin/db-test", "GET"):
    @app.get("/admin/db-test", tags=["admin"])
    def _admin_db_test_alias(request: Request):
        return db_test_fix(request)

if not _path_registered(app, "/admin/db-count", "GET"):
    @app.get("/admin/db-count", tags=["admin"])
    def _admin_db_count_alias(request: Request):
        return db_count_fix(request)
# === /STARLINX ADMIN ALIASES ===
# === STARLINX ADMIN FORCE OVERRIDE ===
# Fuerza a que /admin/* llamen a los handlers robustos de /admin/fix/*
from fastapi import Request

# Nos aseguramos de que existen los fix handlers (db_init_fix, db_test_fix, db_count_fix).
# Si no están importados aún, el bloque de 'admin_fix' previo los define.

@app.get("/admin/db-init", include_in_schema=False, tags=["admin"])
def __admin_db_init_force__(request: Request):
    return db_init_fix(request)

@app.get("/admin/db-test", include_in_schema=False, tags=["admin"])
def __admin_db_test_force__(request: Request):
    return db_test_fix(request)

@app.get("/admin/db-count", include_in_schema=False, tags=["admin"])
def __admin_db_count_force__(request: Request):
    return db_count_fix(request)
# === /STARLINX ADMIN FORCE OVERRIDE ===
