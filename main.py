from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
from datetime import datetime
import os, csv, sqlite3, json

# ------------------ Config básica ------------------
APP_NAME = "STARLINX Protoapp"
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CSV_PATH = DATA_DIR / "registro.csv"

ADMIN_KEY = os.getenv("ADMIN_KEY", "starlinx123")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

# DB: fallback a SQLite en /tmp si no está definido DATABASE_URL o no es sqlite
RAW_DB_URL = os.getenv("DATABASE_URL", "").strip()
if RAW_DB_URL.startswith("sqlite:///"):
    SQLITE_PATH = RAW_DB_URL.replace("sqlite:///", "")
elif RAW_DB_URL:
    # DATABASE_URL definida pero no soportada (p.ej. postgres sin driver): forzamos fallback
    SQLITE_PATH = "/tmp/starlinx.db"
else:
    # no definida
    SQLITE_PATH = "/tmp/starlinx.db"

def get_conn():
    # solo SQLite para este build
    return sqlite3.connect(SQLITE_PATH)

def ensure_table():
    with get_conn() as conn:
        conn.execute("""
          CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            nombre TEXT NOT NULL,
            documento TEXT NOT NULL,
            telefono TEXT NOT NULL
          )
        """)

# crear CSV si no existe
if not CSV_PATH.exists():
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["timestamp","nombre","documento","telefono"])

# ------------------ App ------------------
app = FastAPI(title=APP_NAME)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"],
)

# ------------------ HTML simples ------------------
HOME_HTML = """<!doctype html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Registro STARLINX</title>
<style>
:root{--bg:#f6f7fb;--card:#fff;--accent:#0b5ed7;--muted:#6b7280}
body{margin:0;background:var(--bg);font-family:Inter,system-ui,Arial,sans-serif}
.container{max-width:840px;margin:28px auto;padding:20px}
.card{background:var(--card);border-radius:14px;box-shadow:0 6px 18px rgba(0,0,0,.06);padding:20px}
h1{margin:0 0 8px}
.btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;padding:10px 14px;border-radius:10px;margin-right:8px}
.btn.muted{background:#e5e7eb;color:#111}
form{display:grid;gap:10px;max-width:420px;margin-top:14px}
input{padding:10px;border:1px solid #e5e7eb;border-radius:8px}
</style>
</head><body><div class="container">
<div class="card">
  <h1>Registro de Conductores</h1>
  <p class="muted">Demo con CSV + SQLite fallback.</p>
  <form method="post" action="/registro">
    <input name="nombre" placeholder="Nombre" required />
    <input name="documento" placeholder="Documento" required />
    <input name="telefono" placeholder="Teléfono" required />
    <button class="btn" type="submit">Enviar</button>
    <a class="btn muted" href="/panel">Panel</a>
  </form>
</div>
</div></body></html>"""

PANEL_HTML = """<!doctype html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Panel STARLINX</title>
<style>
body{margin:0;background:#0b5ed70d;font-family:Inter,system-ui,Arial}
.container{max-width:960px;margin:28px auto;padding:20px}
.card{background:#fff;border-radius:14px;box-shadow:0 6px 18px rgba(0,0,0,.06);padding:20px}
h1{margin:0 0 12px}
a.btn{display:inline-block;background:#0b5ed7;color:#fff;text-decoration:none;padding:8px 12px;border-radius:10px;margin-right:8px}
.btn.gray{background:#e5e7eb;color:#111}
table{border-collapse:collapse;width:100%;margin-top:14px}
th,td{border:1px solid #eee;padding:8px;font-size:14px}
</style>
</head><body><div class="container">
<div class="card">
  <h1>Panel administrador</h1>
  <p>Rutas rápidas:</p>
  <p>
    <a class="btn" href="/export/csv">Exportar CSV</a>
    <a class="btn" href="/export/json">Exportar JSON</a>
    <a class="btn gray" href="/">Inicio</a>
  </p>
  <div id="info"></div>
</div>
</div>
<script>
async function load(){
  try{
    const r = await fetch("/admin/db-count?k=${encodeURIComponent("%s")}");
    const j = await r.json();
    document.getElementById("info").innerHTML = "<p><b>Filas en BD:</b> " + (j.count ?? "?") + "</p>";
  }catch(e){
    document.getElementById("info").innerHTML = "<p>(No se pudo leer db-count)</p>";
  }
}
load();
</script>
</body></html>""" % ADMIN_KEY

# ------------------ Helpers ------------------
def requires_key(k: str):
    if k != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="clave inválida")

def csv_append(ts, nombre, documento, telefono):
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([ts, nombre, documento, telefono])

def db_insert(ts, nombre, documento, telefono):
    ensure_table()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO registros (ts,nombre,documento,telefono) VALUES (?,?,?,?)",
            (ts, nombre, documento, telefono),
        )

def db_count():
    ensure_table()
    with get_conn() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM registros")
        (n,) = cur.fetchone()
        return int(n)

# ------------------ Rutas públicas ------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return HOME_HTML

@app.get("/health")
def health():
    return {"status":"ok","service":"starlinx-protoapp"}

@app.get("/ping")
def ping():
    return {"pong": True}

@app.get("/registro", response_class=HTMLResponse)
def reg_get():
    return HOME_HTML

@app.post("/registro", response_class=HTMLResponse)
def reg_post(nombre: str = Form(...), documento: str = Form(...), telefono: str = Form(...)):
    ts = datetime.now().isoformat(timespec="seconds")
    # CSV
    csv_append(ts, nombre, documento, telefono)
    # DB (siempre SQLite fallback disponible)
    try:
        db_insert(ts, nombre, documento, telefono)
    except Exception as e:
        # No rompemos el flujo si el insert falla
        pass

    html = f"""<!doctype html><html><head>
    <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Registro recibido</title>
    <style>body{{font-family:Inter,system-ui,Arial;margin:0;background:#f6f7fb}}
    .container{{max-width:720px;margin:28px auto;padding:20px}}
    .card{{background:#fff;border-radius:14px;box-shadow:0 6px 18px rgba(0,0,0,.06);padding:20px}}
    a.btn{{display:inline-block;background:#0b5ed7;color:#fff;text-decoration:none;padding:8px 12px;border-radius:10px;margin-right:8px}}</style>
    </head><body><div class="container"><div class="card">
    <h2>Registro recibido</h2>
    <p><b>Nombre:</b> {nombre}<br><b>Documento:</b> {documento}<br><b>Teléfono:</b> {telefono}</p>
    <a class="btn" href="/registro">Nuevo registro</a>
    <a class="btn" href="/">Inicio</a>
    </div></div></body></html>"""
    return HTMLResponse(html)

# ------------------ Panel / export ------------------
@app.get("/panel", response_class=HTMLResponse)
def panel():
    return PANEL_HTML

@app.get("/registros", response_class=HTMLResponse)
def ver_registros():
    # Renderizar el CSV
    rows = []
    with CSV_PATH.open("r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows: 
        rows = [["timestamp","nombre","documento","telefono"]]
    thead = "<tr>" + "".join(f"<th>{h}</th>" for h in rows[0]) + "</tr>"
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows[1:])
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Registros (CSV)</title>
    <style>table{{border-collapse:collapse}}td,th{{border:1px solid #ddd;padding:6px}}</style></head>
    <body style="font-family:Arial;margin:20px">
    <h2>Registros (CSV)</h2><p><a href="/">Inicio</a></p>
    <table>{thead}{trs}</table></body></html>"""
    return HTMLResponse(html)

@app.get("/export/csv")
def export_csv():
    return Response(CSV_PATH.read_bytes(), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=registro.csv"})

@app.get("/export/json")
def export_json():
    rows = []
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        for r in reader:
            rows.append(dict(zip(header, r)))
    return JSONResponse(rows)

# ------------------ Admin (con clave) ------------------
@app.get("/admin/db-init")
def admin_db_init(k: str):
    requires_key(k)
    try:
        ensure_table()
        return {"ok": True, "msg": "tabla creada (IF NOT EXISTS)", "driver":"sqlite", "path": SQLITE_PATH}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/db-test")
def admin_db_test(k: str):
    requires_key(k)
    # Solo retornamos info sqlite
    return {"driver":"sqlite", "path": SQLITE_PATH}

@app.get("/admin/db-count")
def admin_db_count(k: str):
    requires_key(k)
    try:
        n = db_count()
        return {"count": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Compat: rutas fix siguen funcionando igual (alias)
@app.get("/admin/fix/db-init")
def fix_db_init(k: str):
    return admin_db_init(k)

@app.get("/admin/fix/db-test")
def fix_db_test(k: str):
    return admin_db_test(k)

@app.get("/admin/fix/db-count")
def fix_db_count(k: str):
    return admin_db_count(k)
