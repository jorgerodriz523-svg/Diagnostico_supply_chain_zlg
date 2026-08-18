"""
scoring.py
----------
Calcula los scores de madurez a partir de las respuestas del cliente.

Escala de respuesta: 0–5  →  convertida a puntaje 0–100 por la tabla:
    0 → 0    (Inexistente)
    1 → 20   (Muy incipiente)
    2 → 40   (Básico)
    3 → 60   (En desarrollo)
    4 → 80   (Avanzado)
    5 → 100  (Óptimo)

Lógica de cálculo (los pesos vienen del Excel de parametrización):
  - Score pregunta     → puntaje 0-100 correspondiente al nivel 0-5 elegido
  - Score subdimensión → promedio ponderado de sus preguntas, según
                          "Peso pregunta en dimensión (%)" (hoja 3_Preguntas;
                          el peso está definido por subdimensión: suma 1.0
                          entre las preguntas de una misma subdimensión)
  - Score dimensión    → promedio ponderado de sus subdimensiones, según
                          "Peso Subdimensión (%)" (hoja 2_Dimensiones; suma
                          1.0 entre las subdimensiones de una misma dimensión)
  - Score general      → promedio ponderado de las dimensiones, según
                          "Peso Dimensión (%)" (hoja 2_Dimensiones; el valor
                          se repite en cada fila de subdimensión de una misma
                          dimensión y suma 1.0 entre las dimensiones de un
                          mismo módulo)
"""

import pandas as pd
from utils.loader import get_preguntas, get_dimensiones

# Conversión nivel 0-5 → puntaje 0-100
ESCALA_A_PUNTAJE = {0: 0, 1: 20, 2: 40, 3: 60, 4: 80, 5: 100}


def calcular_scores(id_modulo: str, respuestas: dict) -> dict:
    """
    Calcula el score completo de un diagnóstico a partir de las respuestas.

    Parámetros
    ----------
    id_modulo  : str  → ej. "MOD-01"
    respuestas : dict → {id_pregunta: puntaje}  ej. {"P-01": 33, "P-02": 100, ...}

    Retorna
    -------
    dict con estructura:
    {
        "score_general": float,
        "dimensiones": {
            "DIM-01": {
                "nombre": str,
                "score": float,
                "subdimensiones": {
                    "Recibo": float,
                    "Almacenamiento": float,
                    ...
                }
            },
            ...
        }
    }
    """
    preguntas_df = get_preguntas(id_modulo)
    dimensiones_df = get_dimensiones(id_modulo)

    scores_dim = {}

    # Agrupar preguntas por dimensión
    for id_dim, grupo_dim in preguntas_df.groupby("ID Dimensión"):
        nombre_dim = _nombre_dimension(dimensiones_df, id_dim)

        # Agrupar preguntas de esa dimensión por subdimensión
        scores_subdim = {}
        for subdim, grupo_subdim in grupo_dim.groupby("Subdimensión"):
            pesos_preg = _pesos_preguntas(grupo_subdim)
            score_subdim = sum(
                respuestas.get(row["ID Pregunta"].strip(), 0)
                * pesos_preg[row["ID Pregunta"].strip()]
                for _, row in grupo_subdim.iterrows()
            )
            scores_subdim[subdim] = round(score_subdim, 2)

        # Score de la dimensión = promedio ponderado de sus subdimensiones
        pesos_subdim = _pesos_subdimensiones(dimensiones_df, id_dim)
        score_dim = sum(
            score * pesos_subdim.get(subdim, 1 / len(scores_subdim))
            for subdim, score in scores_subdim.items()
        )

        scores_dim[id_dim] = {
            "nombre"        : nombre_dim,
            "score"         : round(score_dim, 2),
            "subdimensiones": scores_subdim,
        }

    # Score general = promedio ponderado de las dimensiones
    if scores_dim:
        pesos_dim = _pesos_dimensiones(dimensiones_df)
        score_general = round(
            sum(
                data["score"] * pesos_dim.get(id_dim, 1 / len(scores_dim))
                for id_dim, data in scores_dim.items()
            ),
            2,
        )
    else:
        score_general = 0.0

    return {
        "score_general": score_general,
        "dimensiones"  : scores_dim,
    }


def calcular_score_pregunta(nivel: int) -> int:
    """
    Convierte el nivel elegido (0-5) al puntaje 0-100 correspondiente.
    Es lo que Streamlit llama antes de guardar cada respuesta.
    """
    if nivel not in ESCALA_A_PUNTAJE:
        raise ValueError(
            f"Nivel inválido: {nivel}. Debe ser un entero entre 0 y 5.")
    return ESCALA_A_PUNTAJE[nivel]


def nivel_madurez(score: float) -> dict:
    """
    Devuelve la etiqueta y color del nivel de madurez según el semáforo definido.

    Rojo    : 0  – 64  → Básico / Inexistente
    Amarillo: 65 – 85  → En desarrollo
    Verde   : 86 – 100 → Maduro
    """
    if score <= 64:
        return {"etiqueta": "Básico",        "color": "#FF0303", "emoji": "🔴"}
    elif score <= 85:
        return {"etiqueta": "En desarrollo", "color": "#FFCB03", "emoji": "🟡"}
    else:
        return {"etiqueta": "Maduro",        "color": "#A8DC00", "emoji": "🟢"}


def resumen_scores(scores: dict) -> list[dict]:
    """
    Aplana el resultado de calcular_scores() en una lista plana ordenada,
    útil para mostrar en tablas o gráficas de Streamlit.

    Retorna lista de dicts con: dimensión, subdimensión, score, nivel
    """
    filas = []
    for id_dim, data in scores["dimensiones"].items():
        for subdim, score_subdim in data["subdimensiones"].items():
            filas.append({
                "id_dimension" : id_dim,
                "dimension"    : data["nombre"],
                "subdimension" : subdim,
                "score"        : score_subdim,
                "nivel"        : nivel_madurez(score_subdim)["etiqueta"],
            })
    return filas


# ── Helpers privados ──────────────────────────────────────────────────────────

def _nombre_dimension(dimensiones_df: pd.DataFrame, id_dim: str) -> str:
    fila = dimensiones_df[dimensiones_df["ID Dimensión"].str.strip() == id_dim]
    if fila.empty:
        return id_dim
    return fila.iloc[0]["Nombre Dimensión"]


def _normalizar_pesos(pesos: dict) -> dict:
    """
    Si algún peso es NaN o una fórmula no resuelta en el Excel, distribuye
    equitativamente entre las claves. Luego normaliza para que la suma
    de todos los pesos sea 1.0 (por si en el Excel no suman exactamente 100%).
    """
    if any(v is None for v in pesos.values()):
        n = len(pesos)
        pesos = {k: 1 / n for k in pesos}

    total = sum(pesos.values())
    if total == 0:
        n = len(pesos)
        return {k: 1 / n for k in pesos}
    return {k: v / total for k, v in pesos.items()}


def _pesos_preguntas(grupo_subdim: pd.DataFrame) -> dict:
    """
    Peso de cada pregunta dentro de su subdimensión, según la columna
    "Peso pregunta en dimensión (%)" de la hoja 3_Preguntas (a pesar del
    nombre, el valor está definido por subdimensión: las preguntas de una
    misma subdimensión suman 1.0 entre ellas).
    """
    pesos = {}
    for _, row in grupo_subdim.iterrows():
        id_p = row["ID Pregunta"].strip()
        peso = row["Peso pregunta en dimensión (%)"]
        try:
            peso = float(peso)
            pesos[id_p] = None if pd.isna(peso) else peso
        except (TypeError, ValueError):
            pesos[id_p] = None

    return _normalizar_pesos(pesos)


def _pesos_dimensiones(dimensiones_df: pd.DataFrame) -> dict:
    """
    Peso de cada dimensión dentro del score general, según la columna
    "Peso Dimensión (%)" de la hoja 2_Dimensiones (el valor se repite en
    cada fila de subdimensión de una misma dimensión; los pesos de las
    distintas dimensiones de un mismo módulo suman 1.0 entre ellas).
    """
    dims_unicas = dimensiones_df.drop_duplicates(subset="ID Dimensión")[
        ["ID Dimensión", "Peso Dimensión (%)"]
    ]

    pesos = {}
    for _, row in dims_unicas.iterrows():
        id_dim = row["ID Dimensión"].strip()
        peso = row["Peso Dimensión (%)"]
        try:
            peso = float(peso)
            pesos[id_dim] = None if pd.isna(peso) else peso
        except (TypeError, ValueError):
            pesos[id_dim] = None

    return _normalizar_pesos(pesos)


def _pesos_subdimensiones(dimensiones_df: pd.DataFrame, id_dim: str) -> dict:
    """
    Peso de cada subdimensión dentro de su dimensión, según la columna
    "Peso Subdimensión (%)" de la hoja 2_Dimensiones (cada fila de esa hoja
    es una subdimensión; sus pesos suman 1.0 dentro de cada dimensión).
    """
    filas = dimensiones_df[dimensiones_df["ID Dimensión"].str.strip() == id_dim]

    pesos = {}
    for _, row in filas.iterrows():
        subdim = row["Subdimensión"]
        peso = row["Peso Subdimensión (%)"]
        try:
            peso = float(peso)
            pesos[subdim] = None if pd.isna(peso) else peso
        except (TypeError, ValueError):
            pesos[subdim] = None

    return _normalizar_pesos(pesos)
