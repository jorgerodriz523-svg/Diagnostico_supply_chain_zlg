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
import unicodedata
from datetime import datetime
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
                observacion      TEXT,
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
                observacion      TEXT,
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
        "estado": "TEXT", "actualizado_en": "TEXT",
        "correo_normalizado": "TEXT", "empresa_normalizado": "TEXT",
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

    # Columna "observacion" en respuestas: si la BD ya existía sin ella
    # (bases creadas antes de habilitar las observaciones por pregunta),
    # se agrega sin borrar datos.
    if _USANDO_POSTGRES:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'respuestas'
        """)
        columnas_respuestas = {fila["column_name"] for fila in cursor.fetchall()}
    else:
        cursor.execute("PRAGMA table_info(respuestas)")
        columnas_respuestas = {fila[1] for fila in cursor.fetchall()}

    if "observacion" not in columnas_respuestas:
        cursor.execute("ALTER TABLE respuestas ADD COLUMN observacion TEXT")

    # Índice único que habilita el upsert (ON CONFLICT) de respuestas por
    # pregunta: permite guardar cada respuesta en el momento en que se
    # responde, sin esperar al final del cuestionario.
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_respuestas_diag_pregunta
        ON respuestas (id_diagnostico, id_pregunta)
    """)

    conn.commit()
    conn.close()


def _normalizar(texto: str) -> str:
    """Normaliza texto (trim + minúsculas + sin tildes) para comparar de
    forma consistente el mismo cliente aunque varíe cómo escribe su
    correo/empresa entre una sesión y otra."""
    texto = (texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


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
    LEGACY: ya no se usa en el flujo normal de la app (que ahora crea el
    diagnóstico al inicio y lo guarda de forma incremental — ver
    crear_o_reabrir_diagnostico / guardar_respuesta_incremental /
    marcar_diagnostico_completo). Se conserva por si algún script interno
    todavía depende de un guardado en un solo paso.

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


def crear_o_reabrir_diagnostico(
    empresa: str,
    responsable: str,
    sector: str,
    correo: str,
    cargo: str = "",
    celular: str = "",
    pais: str = "",
    ciudad: str = "",
    modulos_seleccionados: list[str] | None = None,
) -> int:
    """
    Crea un diagnóstico en estado 'en_progreso', o si el mismo cliente
    (correo + empresa normalizados) ya tiene uno abierto, lo reabre y
    fusiona los módulos seleccionados con los que ya tenía. Retorna el
    id_diagnostico a usar durante todo el cuestionario.
    """
    modulos_seleccionados = modulos_seleccionados or []
    correo_norm   = _normalizar(correo)
    empresa_norm  = _normalizar(empresa)
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hoy   = datetime.now().strftime("%Y-%m-%d")

    conn = _conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(_sql("""
            SELECT id_diagnostico, modulos_aplicados FROM diagnosticos
            WHERE estado = 'en_progreso'
              AND correo_normalizado = ? AND empresa_normalizado = ?
            ORDER BY id_diagnostico DESC LIMIT 1
        """), (correo_norm, empresa_norm))
        fila = cursor.fetchone()

        if fila:
            fila = dict(fila)
            id_diag = fila["id_diagnostico"]
            modulos_previos = json.loads(fila["modulos_aplicados"] or "[]")
            modulos_fusionados = list(dict.fromkeys(modulos_previos + modulos_seleccionados))
            cursor.execute(_sql("""
                UPDATE diagnosticos
                SET modulos_aplicados = ?, actualizado_en = ?
                WHERE id_diagnostico = ?
            """), (json.dumps(modulos_fusionados), ahora, id_diag))
        else:
            insert = _sql("""
                INSERT INTO diagnosticos
                    (empresa, responsable, sector, fecha, modulos_aplicados,
                     estado, cargo, celular, correo, pais, ciudad,
                     correo_normalizado, empresa_normalizado, actualizado_en)
                VALUES (?, ?, ?, ?, ?, 'en_progreso', ?, ?, ?, ?, ?, ?, ?, ?)
            """)
            params = (
                empresa, responsable, sector, hoy, json.dumps(modulos_seleccionados),
                cargo, celular, correo, pais, ciudad,
                correo_norm, empresa_norm, ahora,
            )
            if _USANDO_POSTGRES:
                cursor.execute(insert + " RETURNING id_diagnostico", params)
                id_diag = cursor.fetchone()["id_diagnostico"]
            else:
                cursor.execute(insert, params)
                id_diag = cursor.lastrowid

        conn.commit()
        return id_diag

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def buscar_diagnostico_en_progreso(correo: str, empresa: str) -> dict | None:
    """
    Busca si el cliente (correo + empresa normalizados) tiene un
    diagnóstico 'en_progreso'. La usa inicio.py para el atajo "retomar"
    sin obligar a reescribir los 8 campos de identificación.
    """
    correo_norm  = _normalizar(correo)
    empresa_norm = _normalizar(empresa)

    conn = _conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(_sql("""
            SELECT id_diagnostico, empresa, responsable, sector, cargo,
                   celular, correo, pais, ciudad, modulos_aplicados
            FROM diagnosticos
            WHERE estado = 'en_progreso'
              AND correo_normalizado = ? AND empresa_normalizado = ?
            ORDER BY id_diagnostico DESC LIMIT 1
        """), (correo_norm, empresa_norm))
        fila = cursor.fetchone()
        if not fila:
            return None
        fila = dict(fila)
        fila["modulos_aplicados"] = json.loads(fila["modulos_aplicados"] or "[]")
        return fila
    finally:
        conn.close()


def buscar_diagnostico_completado(correo: str, empresa: str) -> dict | None:
    """
    Busca el diagnóstico 'completo' más reciente del cliente (correo +
    empresa normalizados). La usa inicio.py para permitir recuperar y
    volver a descargar los resultados del último diagnóstico finalizado,
    sin importar si el cliente cerró la pantalla de resultados o inició
    uno nuevo después.
    """
    correo_norm  = _normalizar(correo)
    empresa_norm = _normalizar(empresa)

    conn = _conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(_sql("""
            SELECT id_diagnostico, empresa, responsable, sector, cargo,
                   celular, correo, pais, ciudad, modulos_aplicados
            FROM diagnosticos
            WHERE estado = 'completo'
              AND correo_normalizado = ? AND empresa_normalizado = ?
            ORDER BY id_diagnostico DESC LIMIT 1
        """), (correo_norm, empresa_norm))
        fila = cursor.fetchone()
        if not fila:
            return None
        fila = dict(fila)
        fila["modulos_aplicados"] = json.loads(fila["modulos_aplicados"] or "[]")
        return fila
    finally:
        conn.close()


def buscar_borrador_modulo(
    correo: str, empresa: str, id_modulo: str, total_preguntas_modulo: int
) -> dict | None:
    """
    Si el cliente (correo + empresa) tiene un diagnóstico en_progreso con
    respuestas incompletas para id_modulo, retorna
    {"id_diagnostico", "respondidas", "total"}. Si no hay borrador, o el
    módulo no tiene ninguna respuesta, o ya está completo, retorna None
    (el módulo debe arrancar en blanco sin ofrecer nada).
    """
    correo_norm  = _normalizar(correo)
    empresa_norm = _normalizar(empresa)

    conn = _conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(_sql("""
            SELECT id_diagnostico FROM diagnosticos
            WHERE estado = 'en_progreso'
              AND correo_normalizado = ? AND empresa_normalizado = ?
            ORDER BY id_diagnostico DESC LIMIT 1
        """), (correo_norm, empresa_norm))
        fila = cursor.fetchone()
        if not fila:
            return None
        id_diag = dict(fila)["id_diagnostico"]

        cursor.execute(_sql("""
            SELECT COUNT(*) AS n FROM respuestas
            WHERE id_diagnostico = ? AND id_modulo = ?
        """), (id_diag, id_modulo))
        respondidas = dict(cursor.fetchone())["n"]

        if 0 < respondidas < total_preguntas_modulo:
            return {"id_diagnostico": id_diag, "respondidas": respondidas,
                    "total": total_preguntas_modulo}
        return None
    finally:
        conn.close()


def guardar_respuesta_incremental(
    id_diagnostico: int,
    id_pregunta: str,
    id_modulo: str,
    id_dimension: str,
    subdimension: str,
    opcion: str,
    puntaje: int,
    observacion: str = "",
) -> None:
    """
    Guarda (o actualiza si ya existía) la respuesta de una pregunta en el
    momento exacto en que se responde, sin esperar a que termine el
    cuestionario. Upsert vía ON CONFLICT sobre el índice único
    (id_diagnostico, id_pregunta).
    """
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(_sql("""
            INSERT INTO respuestas
                (id_diagnostico, id_modulo, id_dimension, subdimension,
                 id_pregunta, opcion_elegida, puntaje, observacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id_diagnostico, id_pregunta) DO UPDATE SET
                id_modulo      = excluded.id_modulo,
                id_dimension   = excluded.id_dimension,
                subdimension   = excluded.subdimension,
                opcion_elegida = excluded.opcion_elegida,
                puntaje        = excluded.puntaje,
                observacion    = excluded.observacion
        """), (id_diagnostico, id_modulo, id_dimension, subdimension,
               id_pregunta, opcion, puntaje, observacion))

        cursor.execute(_sql("""
            UPDATE diagnosticos SET actualizado_en = ? WHERE id_diagnostico = ?
        """), (ahora, id_diagnostico))

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def obtener_respuestas_diagnostico(id_diagnostico: int) -> dict:
    """
    Reconstruye el dict de respuestas con la misma forma que usa
    st.session_state["respuestas"] en el cuestionario, para poder
    retomar un diagnóstico en_progreso justo donde se dejó.
    """
    conn = _conectar()
    cursor = conn.cursor()
    cursor.execute(_sql("""
        SELECT id_pregunta, id_modulo, id_dimension, subdimension,
               opcion_elegida, puntaje, observacion
        FROM respuestas WHERE id_diagnostico = ?
    """), (id_diagnostico,))
    filas = [dict(r) for r in cursor.fetchall()]
    conn.close()

    respuestas = {}
    for fila in filas:
        try:
            nivel = int(fila["opcion_elegida"])
        except (TypeError, ValueError):
            nivel = 0
        respuestas[fila["id_pregunta"]] = {
            "nivel"       : nivel,
            "puntaje"     : fila["puntaje"],
            "id_modulo"   : fila["id_modulo"],
            "id_dimension": fila["id_dimension"],
            "subdimension": fila["subdimension"],
            "opcion"      : fila["opcion_elegida"],
            "observacion" : fila.get("observacion") or "",
        }
    return respuestas


def marcar_diagnostico_completo(
    id_diagnostico: int,
    scores_por_modulo: dict[str, dict],   # {id_modulo: resultado de calcular_scores()}
    score_general: float,
    fecha: str,
) -> None:
    """
    Cierra el diagnóstico: lo marca 'completo', fija el score general
    (ya agregado por el caller entre todos los módulos evaluados) y
    reemplaza los scores por dimensión de cada módulo. Sustituye el
    INSERT único que antes hacía guardar_diagnostico al final del
    cuestionario.
    """
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(_sql("""
            UPDATE diagnosticos
            SET estado = 'completo', score_general = ?, fecha = ?, actualizado_en = ?
            WHERE id_diagnostico = ?
        """), (score_general, fecha, ahora, id_diagnostico))

        # Se reemplazan (no se acumulan) por si el diagnóstico se cierra
        # más de una vez tras una reapertura.
        cursor.execute(_sql("""
            DELETE FROM scores_dimensiones WHERE id_diagnostico = ?
        """), (id_diagnostico,))

        for id_modulo, scores in scores_por_modulo.items():
            for id_dim, data in scores["dimensiones"].items():
                cursor.execute(_sql("""
                    INSERT INTO scores_dimensiones
                        (id_diagnostico, id_modulo, id_dimension, nombre_dimension, score)
                    VALUES (?, ?, ?, ?, ?)
                """), (
                    id_diagnostico,
                    id_modulo,
                    id_dim,
                    data["nombre"],
                    data["score"],
                ))

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def descartar_diagnostico(id_diagnostico: int) -> None:
    """
    Marca un diagnóstico en_progreso como descartado porque el usuario
    eligió "Comenzar de nuevo" sobre un borrador. No borra nada, se
    conserva para trazabilidad.
    """
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _conectar()
    cursor = conn.cursor()
    cursor.execute(_sql("""
        UPDATE diagnosticos SET estado = 'descartado', actualizado_en = ?
        WHERE id_diagnostico = ?
    """), (ahora, id_diagnostico))
    conn.commit()
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
