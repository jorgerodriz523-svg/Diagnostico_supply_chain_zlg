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

Lógica de cálculo:
  - Score pregunta     → puntaje 0-100 correspondiente al nivel 0-5 elegido
  - Score subdimensión → promedio simple de las preguntas que la componen
  - Score dimensión    → promedio de sus subdimensiones
  - Score general      → promedio ponderado de las dimensiones (peso del Excel)
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

    # Mapa de peso por dimensión (normalizado a suma 1.0)
    pesos_dim = _calcular_pesos_dimensiones(dimensiones_df)

    scores_dim = {}

    # Agrupar preguntas por dimensión
    for id_dim, grupo_dim in preguntas_df.groupby("ID Dimensión"):
        nombre_dim = _nombre_dimension(dimensiones_df, id_dim)

        # Agrupar preguntas de esa dimensión por subdimensión
        scores_subdim = {}
        for subdim, grupo_subdim in grupo_dim.groupby("Subdimensión"):
            puntajes = [
                respuestas.get(row["ID Pregunta"].strip(), 0)
                for _, row in grupo_subdim.iterrows()
            ]
            scores_subdim[subdim] = round(sum(puntajes) / len(puntajes), 2)

        # Score de la dimensión = promedio de sus subdimensiones
        score_dim = round(sum(scores_subdim.values()) / len(scores_subdim), 2)

        scores_dim[id_dim] = {
            "nombre"        : nombre_dim,
            "score"         : score_dim,
            "subdimensiones": scores_subdim,
        }

    # Score general = promedio ponderado de dimensiones
    score_general = _score_ponderado(scores_dim, pesos_dim)

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


def _calcular_pesos_dimensiones(dimensiones_df: pd.DataFrame) -> dict:
    """
    Lee los pesos del Excel y los normaliza a suma 1.0.
    Si los pesos son fórmulas no resueltas, usa distribución equitativa.
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
            pesos[id_dim] = None  # fórmula no resuelta → equitativo

    # Si algún peso es None (fórmula sin resolver), distribuir equitativamente
    if any(v is None for v in pesos.values()):
        n = len(pesos)
        pesos = {k: 1 / n for k in pesos}

    # Normalizar a suma 1.0
    total = sum(pesos.values())
    return {k: v / total for k, v in pesos.items()}


def _score_ponderado(scores_dim: dict, pesos_dim: dict) -> float:
    total = 0.0
    peso_acumulado = 0.0
    for id_dim, data in scores_dim.items():
        peso = pesos_dim.get(id_dim, 1 / len(scores_dim))
        total += data["score"] * peso
        peso_acumulado += peso
    if peso_acumulado == 0:
        return 0.0
    return round(total / peso_acumulado, 2)
