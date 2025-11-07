import os, csv, time
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.middleware.sessions import SessionMiddleware

# === Config ===
ADMIN_KEY = os.getenv("ADMIN_KEY", "starlinx123")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    # fallback estable: SQLite en /tmp para Render Free
    DATABASE_URL = "sqlite:////tmp/starlinx.db"

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CSV_PATH = DATA_DIR / "registro.csv"

# === SQLAlchemy (modo 2.x) ===
from sqlalchemy import create_engine, text

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)

def db_exec(sql: str, params: dict | None = None):
    with engine.begin() as conn:
        return conn.execute(text(sql), params or {})

def ensure_table():
    db_exec("""
    CREATE TABLE IF NOT EXISTS registros (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT NOT NULL,
      nombre TEXT NOT NULL,
      documento TEXT NOT NULL,
      telefono TEXT NOT NULL
    )
    """)

# arranque: crear tabla si no existe
try:
    ensure_table()
except Exception as e:
    # no levantamos excepción para no tumbar el /health; admin verá el error en db-test
    pass

app = FastAPI(title="STARLINX Protoapp - DB + CSV")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# ---- UI mínima ----
HOME = """
<!doctype html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Registro STARLINX</title>
<style>
:root{--bg:#f6f7fb;--card:#fff;--accent:#0b5ed7;--muted:#6b7280}
*{box-sizing:border-box} body{font-family:Arial,Helvetica,sans-serif;background:var(--bg);margin:0;padding:24px}
.card{max-width:660px;margin:auto;background:var(--card);padding:22px;border-radius:14px;box-shadow:0 10px 30px rgba(0,0,0,.07)}
h1{margin:0 0 10px} .muted{color:var(--muted)}
.form{display:grid;gap:12px;margin-top:16px}
input{width:100%;padding:10px;border:1px solid #e5e7eb;border-radius:8px}
.btn{display:inline-block;background:var(--accent);color:#fff;padding:10px 14px;border-radius:10px;text-decoration:none;border:0;cursor:pointer}
.btn.muted{background:#eef2ff;color:#1e40af}
.row{display:flex;gap:10px;flex-wrap:wrap}
</style>
</head><body>
<div class="card">
  <h1>Registro de Conductores</h1>
  <p class="muted">Guarda en CSV y Base de Datos.</p>
  <form method="post" action="/registro" class="form">
    <div><label>Nombre<br><input name="nombre" required></label></div>
    <div class="row">
      <div style="flex:1 1 220px"><label>Documento<br><input name="documento" required></label></div>
      <div style="flex:1 1 220px"><label>Teléfono<br><input name="telefono" required></label></div>
    </div>
    <div class="row">
      <button class="btn" type="submit">Enviar</button>
      <a class="btn muted" href="/panel">Panel</a>
    </div>
  </form>
</div>
</body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return HOME

@app.get("/health")
def health():
    return {"status":"ok","service":"starlinx-protoapp"}

@app.get("/ping")
def ping():
    return JSONResponse({"pong": True})

# --- Panel simple ---
@app.get("/panel", response_class=HTMLResponse)
def panel():
    return """
    <!doctype html><html><head><meta charset="utf-8"><meta name=viewport content=width=device-width,initial-scale=1>
    <title>Panel</title></head><body style="font-family:Arial;margin:24px">
    <h2>Panel administrador</h2>
    <ul>
      <li><a href="/registros">Ver registros (CSV)</a></li>
      <li><a href="/export/csv">Exportar CSV</a> · <a href="/export/json">Exportar JSON</a></li>
      <li>Admin: <code>/admin/db-test</code> · <code>/admin/db-init</code> · <code>/admin/db-count</code></li>
    </ul>
    </body></html>
    """

# --- Registro: guarda CSV + inserta en BD ---
@app.post("/registro")
def registro(nombre: str = Form(...), documento: str = Form(...), telefono: str = Form(...)):
    ts = datetime.now().isoformat(timespec="seconds")

    # CSV
    new_file = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp","nombre","documento","telefono"])
        w.writerow([ts, nombre, documento, telefono])

    # BD
    try:
        ensure_table()
        db_exec(
            "INSERT INTO registros (ts,nombre,documento,telefono) VALUES (:ts,:n,:d,:t)",
            {"ts": ts, "n": nombre, "d": documento, "t": telefono}
        )
    except Exception as e:
        # devolvemos 200 igual (no romper UX), pero con nota en JSON
        return HTMLResponse(f"""
        <!doctype html><html><head><meta charset="utf-8"><title>Registro recibido</title>
        <meta name=viewport content=width=device-width,initial-scale=1></head>
        <body style="font-family:Arial;margin:24px">
        <h3>Registro recibido (CSV ok)</h3>
        <p><b>Nota:</b> No se pudo escribir en BD: <code>{type(e).__name__}</code></p>
        <a class="btn" href="/registro">Nuevo registro</a> · <a class="btn" href="/">Inicio</a>
        </body></html>
        """, status_code=200)

    # OK
    return HTMLResponse("""
    <!doctype html><html><head><meta charset="utf-8"><title>Registro recibido</title>
    <meta name=viewport content=width=device-width,initial-scale=1>
    <style>.btn{display:inline-block;background:#0b5ed7;color:#fff;padding:8px 12px;border-radius:10px;text-decoration:none;margin-right:8px}</style>
    </head><body style="font-family:Arial;margin:24px">
    <h3>Registro recibido</h3>
    <a class="btn" href="/registro">Nuevo registro</a>
    <a class="btn" href="/">Inicio</a>
    </body></html>
    """, status_code=200)

@app.get("/registro", response_class=HTMLResponse)
def registro_form():
    return HOME

# --- Vistas CSV/JSON (lectura del CSV local) ---
@app.get("/registros", response_class=HTMLResponse)
def registros_view():
    rows = []
    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
    thead = "<tr>" + "".join(f"<th>{h}</th>" for h in (rows[0] if rows else ["timestamp","nombre","documento","telefono"])) + "</tr>"
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows[1:])
    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"><title>Registros</title>
    <style>table{{border-collapse:collapse}} td,th{{border:1px solid #ddd;padding:6px}}</style></head>
    <body style="font-family:Arial; margin:20px"><h2>Registros (CSV)</h2>
    <table>{thead}{trs}</table></body></html>
    """)

@app.get("/export/csv")
def export_csv():
    if not CSV_PATH.exists():
        return Response("", media_type="text/csv")
    return Response(CSV_PATH.read_text(encoding="utf-8"), media_type="text/csv",
                    headers={"Content-Disposition":"attachment; filename=registros.csv"})

@app.get("/export/json")
def export_json():
    rows = []
    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    return JSONResponse(rows)

# --- Admin (con clave por query o header) ---
def _check_admin(request: Request, k: str | None):
    header = request.headers.get("X-Admin-Key")
    key = k or header
    if key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="no autorizado")

@app.get("/admin/db-test")
def admin_db_test(request: Request, k: str | None = None):
    _check_admin(request, k)
    try:
        r = db_exec("SELECT 1 as ok")
        driver = "sqlite" if DATABASE_URL.startswith("sqlite") else "other"
        return {"ok": True, "driver": driver, "url": DATABASE_URL}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/db-init")
def admin_db_init(request: Request, k: str | None = None):
    _check_admin(request, k)
    try:
        ensure_table()
        return {"ok": True, "msg": "tabla creada (IF NOT EXISTS)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/db-count")
def admin_db_count(request: Request, k: str | None = None):
    _check_admin(request, k)
    try:
        r = db_exec("SELECT COUNT(*) AS n FROM registros").first()
        c = int(r[0]) if r else 0
        return {"count": c}
    except Exception:
        # Si no hay tabla
        return {"count": 0, "note":"tabla no existe aún; ejecuta /admin/db-init"}
