from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware
import os, csv, sqlite3
from pathlib import Path
from datetime import datetime

app = FastAPI(title="STARLINX Protoapp")

# --- Config ---
ADMIN_KEY = os.getenv("ADMIN_KEY", "starlinx123")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Paths: CSV y DB
IS_RENDER = bool(os.getenv("RENDER"))
BASE_DIR = Path("/tmp") if IS_RENDER else Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CSV_PATH = DATA_DIR / "registro.csv"

DB_PATH = (BASE_DIR / "starlinx.db")
DB_URL  = f"sqlite:///{DB_PATH}"  # informativo
# Crear CSV si no existe
if not CSV_PATH.exists():
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["timestamp","nombre","documento","telefono"])

# --- Helpers DB (sqlite3) ---
def db_conn():
    # check_same_thread=False para uvicorn workers
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)

def ensure_table():
    with db_conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                nombre TEXT NOT NULL,
                documento TEXT NOT NULL,
                telefono TEXT NOT NULL
            )
        """)
        con.commit()

def db_exec(sql, params=()):
    with db_conn() as con:
        cur = con.execute(sql, params)
        con.commit()
        return cur.rowcount

def db_query(sql, params=()):
    with db_conn() as con:
        cur = con.execute(sql, params)
        cols = [c[0] for c in cur.description]
        out = [dict(zip(cols, row)) for row in cur.fetchall()]
        return out

# --- Admin guard ---
def _check_admin(request: Request, k: str | None):
    if k == ADMIN_KEY:
        return
    hdr = request.headers.get("X-Admin-Key")
    if hdr == ADMIN_KEY:
        return
    raise HTTPException(status_code=401, detail="no autorizado")

# --- UI mínima ---
HOME_HTML = """
<!doctype html>
<html><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>STARLINX Registro</title>
<style>
:root{--bg:#f6f7fb;--card:#fff;--accent:#0b5ed7;--muted:#6b7280}
body{margin:0;font-family:Inter,Arial,sans-serif;background:var(--bg);color:#111827}
.container{max-width:720px;margin:24px auto;padding:16px}
.card{background:var(--card);border-radius:14px;box-shadow:0 6px 20px rgba(0,0,0,.07);padding:18px}
h1{margin:0 0 10px;font-size:20px}
.form{display:grid;gap:10px;max-width:420px}
input,button{padding:10px;border-radius:10px;border:1px solid #e5e7eb;font-size:15px}
button{background:var(--accent);color:#fff;border:none;cursor:pointer}
.btn{display:inline-block;margin-right:8px;margin-top:8px;padding:8px 12px;background:#eef2ff;border-radius:10px;color:#1e3a8a;text-decoration:none}
.muted{background:#f1f5f9;color:#475569}
</style>
</head>
<body>
<div class="container">
  <div class="card">
    <h1>Registro de Conductores</h1>
    <form class="form" method="post" action="/registro">
      <input name="nombre" placeholder="Nombre" required />
      <input name="documento" placeholder="Documento" required />
      <input name="telefono" placeholder="Teléfono" required />
      <button type="submit">Enviar</button>
    </form>
    <div>
      <a class="btn" href="/registros">Registros (CSV)</a>
      <a class="btn muted" href="/health">Health</a>
      <a class="btn muted" href="/ping">Ping</a>
    </div>
  </div>
</div>
</body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return HOME_HTML

# --- Salud ---
@app.get("/health")
def health():
    return {"status":"ok","service":"starlinx-protoapp"}

@app.get("/ping")
def ping():
    return JSONResponse({"pong": True})

# --- Registro (CSV + DB) ---
@app.get("/registro", response_class=HTMLResponse)
def registro_form():
    return HOME_HTML

@app.post("/registro", response_class=HTMLResponse)
def registro_post(nombre: str = Form(...), documento: str = Form(...), telefono: str = Form(...)):
    ts = datetime.now().isoformat(timespec="seconds")

    # CSV
    try:
        with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([ts, nombre, documento, telefono])
    except Exception as e:
        # No romper si CSV falla
        pass

    # DB
    try:
        ensure_table()
        db_exec(
            "INSERT INTO registros (timestamp, nombre, documento, telefono) VALUES (?, ?, ?, ?)",
            (ts, nombre, documento, telefono)
        )
    except Exception as e:
        # No romper la respuesta al usuario; log en stderr
        import sys
        print(f"[WARN] DB insert failed: {type(e).__name__}: {e}", file=sys.stderr)

    # Respuesta simple
    return HTMLResponse(f"""<!doctype html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Registro recibido</title>
<style>:root{{--bg:#f6f7fb;--card:#fff;--accent:#0b5ed7;--muted:#6b7280}}body{{margin:0;font-family:Inter,Arial,sans-serif;background:var(--bg);color:#111827}}
.container{{max-width:720px;margin:24px auto;padding:16px}}
.card{{background:var(--card);border-radius:14px;box-shadow:0 6px 20px rgba(0,0,0,.07);padding:18px}}
h1{{margin:0 0 10px;font-size:20px}}
.btn{{display:inline-block;margin-right:8px;margin-top:8px;padding:8px 12px;background:#eef2ff;border-radius:10px;color:#1e3a8a;text-decoration:none}}
.btn.muted{{background:#f1f5f9;color:#475569}}</style></head>
<body><div class="container"><div class="card">
<h1>¡Registro recibido!</h1>
<p><b>{nombre}</b> / {documento} / {telefono}</p>
<a class="btn" href="/registro">Nuevo registro</a>
<a class="btn muted" href="/">Inicio</a>
</div></div></body></html>""")

# --- Vistas sencillas CSV (públicas mínimas) ---
@app.get("/registros", response_class=HTMLResponse)
def ver_registros():
    rows = []
    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
    if not rows:
        rows = [["timestamp","nombre","documento","telefono"]]
    thead = "<tr>" + "".join(f"<th>{h}</th>" for h in rows[0]) + "</tr>"
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows[1:])
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Registros CSV</title>
    <style>table{{border-collapse:collapse}} td,th{{border:1px solid #ddd;padding:6px}}</style></head>
    <body style="font-family:Arial; margin:20px"><h2>Registros CSV</h2>
    <table>{thead}{trs}</table></body></html>"""
    return HTMLResponse(html)

@app.get("/export/csv")
def export_csv():
    if not CSV_PATH.exists():
        return PlainTextResponse("", media_type="text/csv")
    with CSV_PATH.open("r", encoding="utf-8") as f:
        content = f.read()
    return PlainTextResponse(content, media_type="text/csv")

@app.get("/export/json")
def export_json():
    out = []
    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            out = list(reader)
    return JSONResponse(out)

# --- Admin DB ---
@app.get("/admin/db-test")
def admin_db_test(request: Request, k: str | None = None):
    _check_admin(request, k)
    driver = "sqlite"
    return {"ok": True, "driver": driver, "url": DB_URL}

@app.get("/admin/db-init")
def admin_db_init(request: Request, k: str | None = None):
    _check_admin(request, k)
    try:
        ensure_table()
        return {"ok": True, "msg": "tabla creada (IF NOT EXISTS)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

@app.get("/admin/db-count")
def admin_db_count(request: Request, k: str | None = None):
    _check_admin(request, k)
    try:
        ensure_table()
        rows = db_query("SELECT COUNT(*) AS cnt FROM registros")
        return {"count": rows[0]["cnt"] if rows else 0}
    except Exception as e:
        # si la tabla no existe aún (caso raro), devuelve 0
        return {"count": 0}

# --- Fix tools ---
@app.get("/admin/fix/insert")
def admin_fix_insert(request: Request, k: str | None = None, nombre: str = "Fix Test", documento: str = "DOC-FIX", telefono: str = "000"):
    _check_admin(request, k)
    ensure_table()
    try:
        db_exec(
            "INSERT INTO registros (timestamp, nombre, documento, telefono) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), nombre, documento, telefono)
        )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

@app.get("/admin/fix/list")
def admin_fix_list(request: Request, k: str | None = None, limit: int = 5):
    _check_admin(request, k)
    ensure_table()
    try:
        rows = db_query("SELECT timestamp, nombre, documento, telefono FROM registros ORDER BY id DESC LIMIT ?", (limit,))
        return {"rows": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
