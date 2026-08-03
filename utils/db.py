"""
db.py
-----
Gestiona todas las operaciones con la base de datos.

Motor (autodetectado en cada import):
  - Si existe la variable de entorno DATABASE_URL: PostgreSQL
    (producción, p.ej. Streamlit Community Cloud).
  - Si no existe: SQLite local en database/diagnosticos.db (desarrollo).

Esquema:
  diagnosticos  → un registro por diagnóstico completo
  respuestas    → una fila por cada pregunta respondida
"""

import os
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "diagnosticos.db"

_USANDO_POSTGRES = bool(os.environ.get("DATABASE_URL"))


def _conectar():
    if _USANDO_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(
            os.environ["DATABASE_URL"],
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        return conn

    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row  # permite acceder columnas por nombre
    return conn


def _sql(query: str) -> str:
    """Traduce los placeholders `?` (estilo sqlite3) a `%s` (estilo psycopg2)."""
    return query.replace("?", "%s") if _USANDO_POSTGRES else query


def inicializar_bd() -> None:
    """
    Crea las tablas si no existen.
    Debe llamarse una vez al iniciar la app (en app.py).
    """
    conn = _conectar()
    cursor = conn.cursor()

    if _USANDO_POSTGRES:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnosticos (
                id_diagnostico   SERIAL PRIMARY KEY,
                empresa          TEXT NOT NULL,
                responsable      TEXT NOT NULL,
                sector           TEXT,
                fecha            TEXT NOT NULL,
                modulos_aplicados TEXT NOT NULL,   -- JSON: ["MOD-01", "MOD-02"]
                score_general    REAL,
                creado_en        TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                cargo            TEXT,
                celular          TEXT,
                correo           TEXT,
                pais             TEXT,
                ciudad           TEXT
            );

            CREATE TABLE IF NOT EXISTS respuestas (
                id_respuesta     SERIAL PRIMARY KEY,
                id_diagnostico   INTEGER NOT NULL,
                id_modulo        TEXT NOT NULL,
                id_dimension     TEXT NOT NULL,
                subdimension     TEXT NOT NULL,
                id_pregunta      TEXT NOT NULL,
                opcion_elegida   TEXT NOT NULL,    -- Letra: A, B, C o D
                puntaje          INTEGER NOT NULL,
                FOREIGN KEY (id_diagnostico) REFERENCES diagnosticos(id_diagnostico)
            );

            CREATE TABLE IF NOT EXISTS scores_dimensiones (
                id               SERIAL PRIMARY KEY,
                id_diagnostico   INTEGER NOT NULL,
                id_modulo        TEXT NOT NULL,
                id_dimension     TEXT NOT NULL,
                nombre_dimension TEXT NOT NULL,
                score            REAL NOT NULL,
                FOREIGN KEY (id_diagnostico) REFERENCES diagnosticos(id_diagnostico)
            );
        """)
    else:
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS diagnosticos (
                id_diagnostico   INTEGER PRIMARY KEY AUTOINCREMENT,
                empresa          TEXT NOT NULL,
                responsable      TEXT NOT NULL,
                sector           TEXT,
                fecha            TEXT NOT NULL,
                modulos_aplicados TEXT NOT NULL,   -- JSON: ["MOD-01", "MOD-02"]
                score_general    REAL,
                creado_en        TEXT DEFAULT (datetime('now','localtime')),
                cargo            TEXT,
                celular          TEXT,
                correo           TEXT,
                pais             TEXT,
                ciudad           TEXT
            );

            CREATE TABLE IF NOT EXISTS respuestas (
                id_respuesta     INTEGER PRIMARY KEY AUTOINCREMENT,
                id_diagnostico   INTEGER NOT NULL,
                id_modulo        TEXT NOT NULL,
                id_dimension     TEXT NOT NULL,
                subdimension     TEXT NOT NULL,
                id_pregunta      TEXT NOT NULL,
                opcion_elegida   TEXT NOT NULL,    -- Letra: A, B, C o D
                puntaje          INTEGER NOT NULL,
                FOREIGN KEY (id_diagnostico) REFERENCES diagnosticos(id_diagnostico)
            );

            CREATE TABLE IF NOT EXISTS scores_dimensiones (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                id_diagnostico   INTEGER NOT NULL,
                id_modulo        TEXT NOT NULL,
                id_dimension     TEXT NOT NULL,
                nombre_dimension TEXT NOT NULL,
                score            REAL NOT NULL,
                FOREIGN KEY (id_diagnostico) REFERENCES diagnosticos(id_diagnostico)
            );
        """)

    # Columnas nuevas: si la BD ya existía sin ellas, se agregan sin borrar datos.
    # Ni SQLite ni esta ruta de PostgreSQL usan "ADD COLUMN IF NOT EXISTS"
    # (SQLite no lo soporta), así que en ambos motores se verifica primero
    # cuáles columnas ya existen antes de intentar agregarlas.
    columnas_nuevas = {
        "cargo": "TEXT", "celular": "TEXT", "correo": "TEXT",
        "pais": "TEXT", "ciudad": "TEXT",
    }

    if _USANDO_POSTGRES:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'diagnosticos'
        """)
        columnas_existentes = {fila["column_name"] for fila in cursor.fetchall()}
    else:
        cursor.execute("PRAGMA table_info(diagnosticos)")
        columnas_existentes = {fila[1] for fila in cursor.fetchall()}

    for nombre, tipo in columnas_nuevas.items():
        if nombre not in columnas_existentes:
            cursor.execute(f"ALTER TABLE diagnosticos ADD COLUMN {nombre} {tipo}")

    conn.commit()
    conn.close()


def guardar_diagnostico(
    empresa: str,
    responsable: str,
    sector: str,
    fecha: str,
    modulos_aplicados: list[str],
    respuestas: dict,          # {id_pregunta: {"opcion": "B", "puntaje": 33, ...}}
    scores: dict,              # resultado de calcular_scores()
    preguntas_df,              # DataFrame de get_preguntas()
    cargo: str = "",
    celular: str = "",
    correo: str = "",
    pais: str = "",
    ciudad: str = "",
) -> int:
    """
    Guarda el diagnóstico completo en la BD y retorna el id_diagnostico generado.

    Parámetros
    ----------
    respuestas : dict con estructura
        {
          "P-01": {"opcion": "B", "puntaje": 33, "id_dimension": "DIM-01",
                   "subdimension": "Recibo", "id_modulo": "MOD-01"},
          ...
        }
    scores     : dict resultado de scoring.calcular_scores()
    """
    conn = _conectar()
    cursor = conn.cursor()

    try:
        # 1. Insertar cabecera del diagnóstico
        insert_diag = _sql("""
            INSERT INTO diagnosticos
                (empresa, responsable, sector, fecha, modulos_aplicados, score_general,
                 cargo, celular, correo, pais, ciudad)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """)
        params_diag = (
            empresa,
            responsable,
            sector,
            fecha,
            json.dumps(modulos_aplicados),
            scores["score_general"],
            cargo,
            celular,
            correo,
            pais,
            ciudad,
        )

        if _USANDO_POSTGRES:
            # psycopg2 no tiene cursor.lastrowid: se obtiene el id con RETURNING.
            cursor.execute(insert_diag + " RETURNING id_diagnostico", params_diag)
            id_diag = cursor.fetchone()["id_diagnostico"]
        else:
            cursor.execute(insert_diag, params_diag)
            id_diag = cursor.lastrowid

        # 2. Insertar respuesta por pregunta
        for id_pregunta, datos in respuestas.items():
            cursor.execute(_sql("""
                INSERT INTO respuestas
                    (id_diagnostico, id_modulo, id_dimension, subdimension,
                     id_pregunta, opcion_elegida, puntaje)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """), (
                id_diag,
                datos.get("id_modulo", ""),
                datos.get("id_dimension", ""),
                datos.get("subdimension", ""),
                id_pregunta,
                datos.get("opcion", ""),
                datos.get("puntaje", 0),
            ))

        # 3. Insertar scores por dimensión
        for id_dim, data in scores["dimensiones"].items():
            cursor.execute(_sql("""
                INSERT INTO scores_dimensiones
                    (id_diagnostico, id_modulo, id_dimension, nombre_dimension, score)
                VALUES (?, ?, ?, ?, ?)
            """), (
                id_diag,
                modulos_aplicados[0] if modulos_aplicados else "",
                id_dim,
                data["nombre"],
                data["score"],
            ))

        conn.commit()
        return id_diag

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_historico(limite: int = 50) -> list[dict]:
    """
    Retorna los últimos diagnósticos registrados (para uso interno de Zonalogística).
    """
    conn = _conectar()
    cursor = conn.cursor()
    cursor.execute(_sql("""
        SELECT id_diagnostico, empresa, responsable, sector,
               fecha, score_general, creado_en
        FROM diagnosticos
        ORDER BY id_diagnostico DESC
        LIMIT ?
    """), (limite,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_diagnostico_completo(id_diagnostico: int) -> dict:
    """
    Retorna un diagnóstico completo con sus respuestas y scores.
    Útil para consultas históricas o regenerar el HTML.
    """
    conn = _conectar()
    cursor = conn.cursor()

    cursor.execute(_sql("SELECT * FROM diagnosticos WHERE id_diagnostico = ?"), (id_diagnostico,))
    cab = dict(cursor.fetchone() or {})

    cursor.execute(_sql("SELECT * FROM respuestas WHERE id_diagnostico = ?"), (id_diagnostico,))
    resp = [dict(r) for r in cursor.fetchall()]

    cursor.execute(_sql("SELECT * FROM scores_dimensiones WHERE id_diagnostico = ?"), (id_diagnostico,))
    scores = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"cabecera": cab, "respuestas": resp, "scores": scores}
