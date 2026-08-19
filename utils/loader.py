"""
loader.py
---------
Lee el archivo Excel de parametrización y expone DataFrames listos para usar.
Toda la app consume estas funciones; si el Excel cambia, solo cambia este archivo.
"""

import pandas as pd
from pathlib import Path

EXCEL_PATH = Path(__file__).parent.parent / "config" / "Parametrizacion_Almacenamiento_MOD01.xlsx"

_cache: dict[str, pd.DataFrame] | None = None
_cache_mtime: float | None = None


def _cargar_excel() -> dict[str, pd.DataFrame]:
    """
    Carga todas las hojas relevantes del Excel en memoria. Se cachea en
    memoria del proceso y solo se vuelve a leer si el archivo cambió en
    disco desde la última carga (comparando su fecha de modificación), así
    una edición del Excel de parametrización se refleja sin necesidad de
    reiniciar la app.
    """
    global _cache, _cache_mtime

    mtime_actual = EXCEL_PATH.stat().st_mtime
    if _cache is not None and _cache_mtime == mtime_actual:
        return _cache

    hojas = {
        "modulos"     : "1_Modulos",
        "dimensiones" : "2_Dimensiones",
        "preguntas"   : "3_Preguntas",
        "opciones"    : "4_Opciones_Pesos",
        "estrategias" : "5_Estrategias",
    }
    _cache = {
        key: pd.read_excel(EXCEL_PATH, sheet_name=hoja, skiprows=2)
        for key, hoja in hojas.items()
    }
    _cache_mtime = mtime_actual
    return _cache


# ── Funciones públicas ────────────────────────────────────────────────────────

def get_modulos(solo_activos: bool = True) -> pd.DataFrame:
    """
    Devuelve el catálogo de módulos.
    Si solo_activos=True, filtra únicamente los que tienen 'Sí' en la columna Activo.
    """
    df = _cargar_excel()["modulos"].copy()
    df.columns = df.columns.str.strip()
    if solo_activos:
        df = df[df["Activo"].str.strip().str.lower() == "sí"]
    return df.reset_index(drop=True)


def get_dimensiones(id_modulo: str) -> pd.DataFrame:
    """
    Devuelve las dimensiones y subdimensiones de un módulo específico.
    Columnas relevantes: ID Dimensión, Nombre Dimensión, Peso Dimensión (%),
    Subdimensión, Peso Subdimensión (%)
    """
    df = _cargar_excel()["dimensiones"].copy()
    df.columns = df.columns.str.strip()
    return df[df["ID Módulo"].str.strip() == id_modulo].reset_index(drop=True)


def get_preguntas(id_modulo: str) -> pd.DataFrame:
    """
    Devuelve todas las preguntas de un módulo, ordenadas por ID Pregunta.
    Incluye a qué dimensión y subdimensión pertenece cada una.
    """
    df = _cargar_excel()["preguntas"].copy()
    df.columns = df.columns.str.strip()
    df = df[df["ID Módulo"].str.strip() == id_modulo]
    return df.sort_values("ID Pregunta").reset_index(drop=True)


def get_opciones(id_pregunta: str) -> pd.DataFrame:
    """
    Devuelve las 4 opciones de respuesta de una pregunta con sus puntajes.
    Columnas: ID Opción, Letra opción, Texto de la opción, Puntaje (0-100), Nivel de madurez
    """
    df = _cargar_excel()["opciones"].copy()
    df.columns = df.columns.str.strip()
    df = df[df["ID Pregunta"].str.strip() == id_pregunta]
    return df.sort_values("Letra opción").reset_index(drop=True)


def get_opciones_modulo(id_modulo: str) -> pd.DataFrame:
    """
    Devuelve todas las opciones de todas las preguntas de un módulo de una vez.
    Útil para no hacer N llamadas individuales al construir el cuestionario.
    """
    preguntas = get_preguntas(id_modulo)
    ids_preguntas = preguntas["ID Pregunta"].str.strip().tolist()

    df = _cargar_excel()["opciones"].copy()
    df.columns = df.columns.str.strip()
    return df[df["ID Pregunta"].str.strip().isin(ids_preguntas)].reset_index(drop=True)


def get_estrategias(id_pregunta: str, puntaje: float) -> pd.DataFrame:
    """
    Devuelve las estrategias que aplican para una pregunta dado el puntaje obtenido.
    Filtra por el rango [mín, máx] definido en el Excel.
    """
    df = _cargar_excel()["estrategias"].copy()
    df.columns = df.columns.str.strip()
    df = df[df["ID Pregunta"].str.strip() == id_pregunta]
    mascara = (df["Rango puntaje mín."] <= puntaje) & (df["Rango puntaje máx."] >= puntaje)
    return df[mascara].reset_index(drop=True)


def get_todas_estrategias_modulo(id_modulo: str, respuestas: dict) -> list[dict]:
    """
    Dado un dict {id_pregunta: puntaje}, devuelve la lista completa de estrategias
    que aplican para todo el módulo, enriquecidas con la subdimensión de cada pregunta.

    Parámetros
    ----------
    id_modulo  : str   → ej. "MOD-01"
    respuestas : dict  → ej. {"P-01": 33, "P-02": 100, ...}

    Retorna
    -------
    list[dict] con claves: id_pregunta, subdimension, puntaje, nivel_brecha,
                           estrategia, impacto, plazo
    """
    preguntas_df = get_preguntas(id_modulo)
    estrategias_df = _cargar_excel()["estrategias"].copy()
    estrategias_df.columns = estrategias_df.columns.str.strip()

    resultado = []
    for _, pregunta in preguntas_df.iterrows():
        id_p = pregunta["ID Pregunta"].strip()
        puntaje = respuestas.get(id_p, 100)  # si no respondió, asume óptimo

        est = estrategias_df[estrategias_df["ID Pregunta"].str.strip() == id_p]
        mascara = (est["Rango puntaje mín."] <= puntaje) & (est["Rango puntaje máx."] >= puntaje)
        for _, fila in est[mascara].iterrows():
            resultado.append({
                "id_pregunta"  : id_p,
                "subdimension" : pregunta["Subdimensión"],
                "puntaje"      : puntaje,
                "nivel_brecha" : fila["Nivel de brecha"],
                "estrategia"   : fila["Estrategia recomendada"],
                "impacto"      : fila["Impacto estimado"],
                "plazo"        : fila["Plazo sugerido"],
            })

    # Ordenar: primero las críticas, luego moderadas, luego leves
    orden_brecha = {"Crítica": 0, "Moderada": 1, "Leve": 2}
    resultado.sort(key=lambda x: orden_brecha.get(x["nivel_brecha"], 9))
    return resultado
