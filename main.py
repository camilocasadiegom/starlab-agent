from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
import csv, os, io, json
from datetime import datetime

app = FastAPI(title="STARLINX • Registro + Acceso")

# --- Sesiones (cookie) ---
SECRET_KEY = os.getenv("SECRET_KEY", "starlab_dev_secret_change_me")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CSV_PATH = DATA_DIR / "registro.csv"

# crea encabezados si no existe
if not CSV_PATH.exists():
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["timestamp","nombre","documento","telefono"])

ADMIN_KEY = os.getenv("ADMIN_KEY", "starlab123")  # cambia esto luego

# ----------------- VISTAS -----------------
HTML_FORM = """
<html>
  <head><meta charset="utf-8"><title>Registro STARLINX</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"></head>
  <body style="font-family:Arial, sans-serif; margin:30px; max-width:720px">
    <h1>Registro de Conductores</h1>
    <form method="post" action="/register" style="display:grid; gap:10px; max-width:420px">
      <label>Nombre <input name="nombre" required></label>
      <label>Documento <input name="documento" required></label>
      <label>Teléfono <input name="telefono" required></label>
      <button type="submit">Enviar</button>
    </form>
    <p style="margin-top:14px"><a href="/acceso">Acceso admin</a> · <a href="/docs">API Docs</a></p>
  </body></html>
"""

HTML_LOGIN = """
<html>
<head><meta charset="utf-8"><title>Acceso</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:Arial, sans-serif; margin:30px; max-width:520px">
  <h1>Acceso administrador</h1>
  <form method="post" action="/acceso" style="display:grid; gap:10px; max-width:320px">
    <label>Clave <input name="clave" type="password" required></label>
    <button type="submit">Entrar</button>
  </form>
  <p style="color:#666; margin-top:12px">Usa la clave de admin configurada en <code>ADMIN_KEY</code>.</p>
  <p><a href="/">Volver</a></p>
</body></html>
"""

def count_rows():
    if not CSV_PATH.exists(): return 0
    with CSV_PATH.open("r", encoding="utf-8") as f:
        r = list(csv.reader(f))
    return max(0, len(r)-1)

# ----------------- RUTAS PÚBLICAS -----------------
@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_FORM

@app.post("/register")
def register(nombre: str = Form(...), documento: str = Form(...), telefono: str = Form(...)):
    ts = datetime.now().isoformat(timespec="seconds")
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([ts, nombre, documento, telefono])
    return JSONResponse({"ok": True, "ts": ts, "nombre": nombre})

@app.get("/ping")
def ping():
    return JSONResponse({"pong": True})

@app.get("/health")
def health():
    return {"status": "ok", "service": "starlinx-protoapp"}

# ----------------- ACCESO / PANEL -----------------
from fastapi.responses import RedirectResponse

@app.get("/acceso", response_class=HTMLResponse)
def acceso_get(request: Request):
    if request.session.get("auth") is True:
        return RedirectResponse("/panel", status_code=303)
    return HTML_LOGIN

@app.post("/acceso")
def acceso_post(request: Request, clave: str = Form(...)):
    if clave == ADMIN_KEY:
        request.session["auth"] = True
        return RedirectResponse("/panel", status_code=303)
    return HTMLResponse("<h3>Clave inválida</h3><p><a href='/acceso'>Volver</a></p>", status_code=401)

@app.get("/salir")
def salir(request: Request):
    request.session.clear()
    return RedirectResponse("/acceso", status_code=303)

@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request):
    if request.session.get("auth") is not True:
        return RedirectResponse("/acceso", status_code=303)
    total = count_rows()
    html = f"""
    <html><head><meta charset='utf-8'><title>Panel</title></head>
    <body style="font-family:Arial, sans-serif; margin:30px; max-width:720px">
      <h1>Panel administrador</h1>
      <p>Registros guardados: <b>{total}</b></p>
      <p><a href="/registros">Ver registros</a> · <a href="/export.csv">Exportar CSV</a> · <a href="/export.json">Exportar JSON</a> · <a href="/salir">Salir</a></p>
    </body></html>
    """
    return HTMLResponse(html)

@app.get("/registros", response_class=HTMLResponse)
def registros(request: Request, k: str | None = None):
    # Permite ver si hay sesión o si se pasa ?k=<ADMIN_KEY> (compatibilidad)
    if not (request.session.get("auth") is True or (k == ADMIN_KEY)):
        return RedirectResponse("/acceso", status_code=303)
    rows = []
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    thead = "<tr>" + "".join(f"<th>{h}</th>" for h in rows[0]) + "</tr>"
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows[1:])
    html = f"""<html><head><meta charset="utf-8"><title>Registros</title>
    <style>table{{border-collapse:collapse}} td,th{{border:1px solid #ddd;padding:6px}}</style></head>
    <body style="font-family:Arial; margin:20px"><h2>Registros</h2>
    <p><a href="/panel">Volver al panel</a></p>
    <table>{thead}{trs}</table></body></html>"""
    return HTMLResponse(html)

# ----------------- EXPORTS (protegidos) -----------------
def _require_admin(request: Request, k: str | None):
    if request.session.get("auth") is True: 
        return True
    if k == ADMIN_KEY:
        return True
    return False

@app.get("/export.csv")
def export_csv(request: Request, k: str | None = None):
    if not _require_admin(request, k):
        raise HTTPException(status_code=401, detail="no autorizado")
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        content = f.read()
    # Forzar descarga
    headers = {"Content-Disposition": 'attachment; filename="registro.csv"'}
    return Response(content, media_type="text/csv; charset=utf-8", headers=headers)

@app.get("/export.json")
def export_json(request: Request, k: str | None = None):
    if not _require_admin(request, k):
        raise HTTPException(status_code=401, detail="no autorizado")
    out = []
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        out = list(reader)
    return JSONResponse(out)
