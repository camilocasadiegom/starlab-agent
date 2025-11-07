import os, re, sqlite3, pathlib, time

def _db_from_env():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        # default en Render: usar /tmp
        return ("sqlite", "/tmp/starlinx.db")
    # Soportar sqlite:////abs y sqlite:///abs
    if url.startswith("sqlite:"):
        path = re.sub(r"^sqlite:(/+)", "/", url)  # normaliza prefijo
        # tras normalizar, path debe ser absoluto
        if not path.startswith("/"):
            # fallback seguro
            path = "/tmp/starlinx.db"
        return ("sqlite", path)
    # Si en el futuro usamos Postgres, adaptar aquí (psycopg/SQLAlchemy)
    return ("unknown", url)

def get_sqlite_path():
    driver, path = _db_from_env()
    if driver != "sqlite":
        raise RuntimeError(f"Unsupported driver in DATABASE_URL: {driver}")
    # Asegurar carpeta
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)

def connect_sqlite():
    path = get_sqlite_path()
    # check writable
    parent = pathlib.Path(path).parent
    testfile = parent / (".touch_" + str(int(time.time())))
    try:
        with open(testfile, "w") as f:
            f.write("ok")
    finally:
        try:
            testfile.unlink(missing_ok=True)
        except Exception:
            pass
    con = sqlite3.connect(path, timeout=10, isolation_level=None)
    return con

def ensure_table(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            nombre TEXT NOT NULL,
            documento TEXT NOT NULL,
            telefono TEXT NOT NULL
        )
    """)

def count_rows(con):
    try:
        cur = con.execute("SELECT COUNT(*) FROM registros")
        (n,) = cur.fetchone()
        return n
    except sqlite3.OperationalError:
        # tabla no existe
        return None
