"""
db.py
-----
Gestiona todas las operaciones con la base de datos SQLite.

Esquema:
  diagnosticos  → un registro por diagnóstico completo
  respuestas    → una fila por cada pregunta respondida
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "diagnosticos.db"


def _conectar() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # permite acceder columnas por nombre
    return conn


def inicializar_bd() -> None:
    """
    Crea las tablas si no existen.
    Debe llamarse una vez al iniciar la app (en app.py).
    """
    conn = _conectar()
    cursor = conn.cursor()

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
    # SQLite no soporta "ADD COLUMN IF NOT EXISTS", así que se verifica primero
    # con PRAGMA table_info() antes de intentar agregar cada columna.
    cursor.execute("PRAGMA table_info(diagnosticos)")
    columnas_existentes = {fila[1] for fila in cursor.fetchall()}
    columnas_nuevas = {
        "cargo": "TEXT", "celular": "TEXT", "correo": "TEXT",
        "pais": "TEXT", "ciudad": "TEXT",
    }
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
        cursor.execute("""
            INSERT INTO diagnosticos
                (empresa, responsable, sector, fecha, modulos_aplicados, score_general,
                 cargo, celular, correo, pais, ciudad)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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
        ))
        id_diag = cursor.lastrowid

        # 2. Insertar respuesta por pregunta
        for id_pregunta, datos in respuestas.items():
            cursor.execute("""
                INSERT INTO respuestas
                    (id_diagnostico, id_modulo, id_dimension, subdimension,
                     id_pregunta, opcion_elegida, puntaje)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
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
            cursor.execute("""
                INSERT INTO scores_dimensiones
                    (id_diagnostico, id_modulo, id_dimension, nombre_dimension, score)
                VALUES (?, ?, ?, ?, ?)
            """, (
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
    cursor.execute("""
        SELECT id_diagnostico, empresa, responsable, sector,
               fecha, score_general, creado_en
        FROM diagnosticos
        ORDER BY id_diagnostico DESC
        LIMIT ?
    """, (limite,))
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

    cursor.execute("SELECT * FROM diagnosticos WHERE id_diagnostico = ?", (id_diagnostico,))
    cab = dict(cursor.fetchone() or {})

    cursor.execute("SELECT * FROM respuestas WHERE id_diagnostico = ?", (id_diagnostico,))
    resp = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM scores_dimensiones WHERE id_diagnostico = ?", (id_diagnostico,))
    scores = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"cabecera": cab, "respuestas": resp, "scores": scores}
