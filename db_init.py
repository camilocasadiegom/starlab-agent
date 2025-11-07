import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL no está definido (Render lo inyecta).")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

DDL = '''
CREATE TABLE IF NOT EXISTS conductores (
  id SERIAL PRIMARY KEY,
  nombre TEXT NOT NULL,
  documento TEXT NOT NULL,
  telefono TEXT,
  email TEXT,
  ciudad TEXT,
  tipo_vehiculo TEXT,
  ts TIMESTAMP DEFAULT NOW()
);
'''
with engine.begin() as conn:
    conn.execute(text(DDL))
    now = conn.execute(text("SELECT now()")).scalar_one()
    print("DB OK. Tabla 'conductores' lista.", now)
