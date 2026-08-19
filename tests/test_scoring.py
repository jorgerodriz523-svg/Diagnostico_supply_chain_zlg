"""
tests/test_scoring.py
----------------------
Red de seguridad para utils/scoring.py: el motor de cálculo de madurez
(pregunta -> subdimensión -> dimensión -> score general).

Dos niveles de prueba:
  1. Unitarias con una parametrización sintética (vía monkeypatch de
     utils.scoring.get_preguntas/get_dimensiones): validan la aritmética
     de ponderación de forma aislada y determinística, incluyendo los
     casos límite que ya maneja _normalizar_pesos (pesos NaN, pesos que
     no suman 1.0).
  2. De regresión contra la parametrización real de MOD-01 (el Excel de
     config/): no fijan un número exacto de negocio (eso cambiaría cada
     vez que Zonalogística ajuste pesos/preguntas), sino invariantes que
     SIEMPRE deben cumplirse sin importar el contenido: todo-mínimo da 0,
     todo-máximo da 100, y nunca hay NaN ni valores fuera de [0, 100].
"""

import math

import pandas as pd
import pytest

from utils.loader import get_preguntas
from utils.scoring import (
    calcular_score_pregunta,
    calcular_scores,
    nivel_madurez,
    resumen_scores,
)


# ── Helpers de parametrización sintética ────────────────────────────────────

def _preguntas_df(filas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(filas)


def _dimensiones_df(filas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(filas)


def _patch_parametrizacion(monkeypatch, preguntas_df, dimensiones_df):
    """Hace que calcular_scores() use la parametrización sintética dada,
    sin importar qué id_modulo se le pase."""
    monkeypatch.setattr("utils.scoring.get_preguntas", lambda id_modulo: preguntas_df)
    monkeypatch.setattr("utils.scoring.get_dimensiones", lambda id_modulo: dimensiones_df)


# Módulo sintético de referencia para la mayoría de los tests:
#   DIM-A (peso 0.6)
#     SubA1 (peso 0.7): Q1 (peso 0.5), Q2 (peso 0.5)
#     SubA2 (peso 0.3): Q3 (peso 1.0)
#   DIM-B (peso 0.4)
#     SubB1 (peso 1.0): Q4 (peso 1.0)
PREGUNTAS_REF = _preguntas_df([
    {"ID Pregunta": "Q1", "ID Dimensión": "DIM-A", "Subdimensión": "SubA1",
     "Peso pregunta en dimensión (%)": 0.5},
    {"ID Pregunta": "Q2", "ID Dimensión": "DIM-A", "Subdimensión": "SubA1",
     "Peso pregunta en dimensión (%)": 0.5},
    {"ID Pregunta": "Q3", "ID Dimensión": "DIM-A", "Subdimensión": "SubA2",
     "Peso pregunta en dimensión (%)": 1.0},
    {"ID Pregunta": "Q4", "ID Dimensión": "DIM-B", "Subdimensión": "SubB1",
     "Peso pregunta en dimensión (%)": 1.0},
])
DIMENSIONES_REF = _dimensiones_df([
    {"ID Dimensión": "DIM-A", "Nombre Dimensión": "Dimensión A", "Peso Dimensión (%)": 0.6,
     "Subdimensión": "SubA1", "Peso Subdimensión (%)": 0.7},
    {"ID Dimensión": "DIM-A", "Nombre Dimensión": "Dimensión A", "Peso Dimensión (%)": 0.6,
     "Subdimensión": "SubA2", "Peso Subdimensión (%)": 0.3},
    {"ID Dimensión": "DIM-B", "Nombre Dimensión": "Dimensión B", "Peso Dimensión (%)": 0.4,
     "Subdimensión": "SubB1", "Peso Subdimensión (%)": 1.0},
])


@pytest.fixture
def parametrizacion_ref(monkeypatch):
    _patch_parametrizacion(monkeypatch, PREGUNTAS_REF, DIMENSIONES_REF)


# ── calcular_scores: ponderación con pesos completos ────────────────────────

def test_calcular_scores_pondera_correctamente(parametrizacion_ref):
    respuestas = {"Q1": 80, "Q2": 60, "Q3": 100, "Q4": 40}
    scores = calcular_scores("MOD-TEST", respuestas)

    assert scores["dimensiones"]["DIM-A"]["subdimensiones"]["SubA1"] == pytest.approx(70.0)
    assert scores["dimensiones"]["DIM-A"]["subdimensiones"]["SubA2"] == pytest.approx(100.0)
    assert scores["dimensiones"]["DIM-A"]["score"] == pytest.approx(79.0)
    assert scores["dimensiones"]["DIM-B"]["score"] == pytest.approx(40.0)
    assert scores["score_general"] == pytest.approx(63.4)


def test_calcular_scores_pregunta_sin_responder_cuenta_como_cero(parametrizacion_ref):
    # Q2 no aparece en `respuestas`: calcular_scores debe tratarla como 0,
    # no lanzar KeyError ni ignorarla del promedio ponderado.
    respuestas = {"Q1": 80, "Q3": 100, "Q4": 40}
    scores = calcular_scores("MOD-TEST", respuestas)

    assert scores["dimensiones"]["DIM-A"]["subdimensiones"]["SubA1"] == pytest.approx(40.0)  # 0.5*80 + 0.5*0


def test_calcular_scores_respuestas_vacias_da_cero(parametrizacion_ref):
    scores = calcular_scores("MOD-TEST", {})
    assert scores["score_general"] == pytest.approx(0.0)
    for dim in scores["dimensiones"].values():
        assert dim["score"] == pytest.approx(0.0)


def test_calcular_scores_todo_maximo_da_100(parametrizacion_ref):
    respuestas = {"Q1": 100, "Q2": 100, "Q3": 100, "Q4": 100}
    scores = calcular_scores("MOD-TEST", respuestas)
    assert scores["score_general"] == pytest.approx(100.0)


def test_calcular_scores_modulo_sin_dimensiones_no_lanza(monkeypatch):
    # Un módulo sin filas coincidentes en el Excel llega aquí como un
    # DataFrame vacío pero con las columnas esperadas (get_preguntas()
    # filtra por "ID Módulo" sobre un DataFrame que ya las tiene).
    preguntas_vacio = pd.DataFrame(columns=list(PREGUNTAS_REF.columns))
    dimensiones_vacio = pd.DataFrame(columns=list(DIMENSIONES_REF.columns))
    _patch_parametrizacion(monkeypatch, preguntas_vacio, dimensiones_vacio)
    scores = calcular_scores("MOD-VACIO", {})
    assert scores["score_general"] == 0.0
    assert scores["dimensiones"] == {}


# ── _normalizar_pesos (vía calcular_scores): casos límite de pesos ──────────

PREGUNTAS_UN_DIM = _preguntas_df([
    {"ID Pregunta": "Q1", "ID Dimensión": "DIM-X", "Subdimensión": "SubX",
     "Peso pregunta en dimensión (%)": float("nan")},
    {"ID Pregunta": "Q2", "ID Dimensión": "DIM-X", "Subdimensión": "SubX",
     "Peso pregunta en dimensión (%)": 0.9},
])
DIMENSIONES_UN_DIM = _dimensiones_df([
    {"ID Dimensión": "DIM-X", "Nombre Dimensión": "Dimensión X", "Peso Dimensión (%)": 1.0,
     "Subdimensión": "SubX", "Peso Subdimensión (%)": 1.0},
])


def test_peso_pregunta_nan_cae_a_reparto_equitativo(monkeypatch):
    # Si CUALQUIER peso del grupo viene NaN/vacío en el Excel,
    # _normalizar_pesos reparte por igual entre TODAS las preguntas de esa
    # subdimensión (no solo la que falta) — se documenta explícitamente
    # ese comportamiento porque no es obvio a partir del nombre de la función.
    _patch_parametrizacion(monkeypatch, PREGUNTAS_UN_DIM, DIMENSIONES_UN_DIM)
    scores = calcular_scores("MOD-TEST", {"Q1": 80, "Q2": 20})
    assert scores["score_general"] == pytest.approx(50.0)  # (80+20)/2, no 0.9-ponderado


PREGUNTAS_PESOS_NO_SUMAN_1 = _preguntas_df([
    {"ID Pregunta": "Q1", "ID Dimensión": "DIM-X", "Subdimensión": "SubX",
     "Peso pregunta en dimensión (%)": 0.2},
    {"ID Pregunta": "Q2", "ID Dimensión": "DIM-X", "Subdimensión": "SubX",
     "Peso pregunta en dimensión (%)": 0.4},
])


def test_pesos_que_no_suman_1_se_normalizan_proporcionalmente(monkeypatch):
    # 0.2 y 0.4 (suman 0.6, no 1.0) deben normalizarse a 1/3 y 2/3.
    _patch_parametrizacion(monkeypatch, PREGUNTAS_PESOS_NO_SUMAN_1, DIMENSIONES_UN_DIM)
    scores = calcular_scores("MOD-TEST", {"Q1": 90, "Q2": 30})
    assert scores["score_general"] == pytest.approx(50.0)  # 1/3*90 + 2/3*30


# ── calcular_score_pregunta ──────────────────────────────────────────────────

@pytest.mark.parametrize("nivel,esperado", [(0, 0), (1, 20), (2, 40), (3, 60), (4, 80), (5, 100)])
def test_calcular_score_pregunta_mapea_nivel_a_puntaje(nivel, esperado):
    assert calcular_score_pregunta(nivel) == esperado


@pytest.mark.parametrize("nivel_invalido", [-1, 6, 10, None])
def test_calcular_score_pregunta_rechaza_nivel_invalido(nivel_invalido):
    with pytest.raises(ValueError):
        calcular_score_pregunta(nivel_invalido)


# ── nivel_madurez ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("score,etiqueta_esperada", [
    (0, "Básico"), (64, "Básico"),
    (65, "En desarrollo"), (85, "En desarrollo"),
    (86, "Maduro"), (100, "Maduro"),
])
def test_nivel_madurez_umbrales(score, etiqueta_esperada):
    assert nivel_madurez(score)["etiqueta"] == etiqueta_esperada


# ── resumen_scores ────────────────────────────────────────────────────────

def test_resumen_scores_aplana_dimensiones_y_subdimensiones(parametrizacion_ref):
    scores = calcular_scores("MOD-TEST", {"Q1": 80, "Q2": 60, "Q3": 100, "Q4": 40})
    filas = resumen_scores(scores)

    subdims_encontradas = {f["subdimension"] for f in filas}
    assert subdims_encontradas == {"SubA1", "SubA2", "SubB1"}
    fila_suba1 = next(f for f in filas if f["subdimension"] == "SubA1")
    assert fila_suba1["dimension"] == "Dimensión A"
    assert fila_suba1["score"] == pytest.approx(70.0)
    assert fila_suba1["nivel"] == "En desarrollo"  # nivel_madurez: 65-85 -> "En desarrollo"


# ── Regresión contra la parametrización real de MOD-01 (Excel de config/) ──
# No fijan un score exacto (cambia si Zonalogística ajusta pesos/preguntas):
# solo protegen invariantes que SIEMPRE deben cumplirse.

def test_mod01_real_respuestas_vacias_da_cero():
    scores = calcular_scores("MOD-01", {})
    assert scores["score_general"] == pytest.approx(0.0, abs=0.01)
    assert len(scores["dimensiones"]) > 0
    for dim in scores["dimensiones"].values():
        assert dim["score"] == pytest.approx(0.0, abs=0.01)


def test_mod01_real_todo_maximo_da_100():
    ids_preguntas = get_preguntas("MOD-01")["ID Pregunta"].str.strip().tolist()
    respuestas = {id_p: 100 for id_p in ids_preguntas}
    scores = calcular_scores("MOD-01", respuestas)
    assert scores["score_general"] == pytest.approx(100.0, abs=0.01)
    for dim in scores["dimensiones"].values():
        assert dim["score"] == pytest.approx(100.0, abs=0.01)


def test_mod01_real_scores_siempre_en_rango_0_100():
    ids_preguntas = get_preguntas("MOD-01")["ID Pregunta"].str.strip().tolist()
    # Mezcla de niveles reales (0, 20, 40, ..., 100) por pregunta
    niveles = [0, 20, 40, 60, 80, 100]
    respuestas = {id_p: niveles[i % len(niveles)] for i, id_p in enumerate(ids_preguntas)}
    scores = calcular_scores("MOD-01", respuestas)

    assert not math.isnan(scores["score_general"])
    assert 0.0 <= scores["score_general"] <= 100.0
    for dim in scores["dimensiones"].values():
        assert not math.isnan(dim["score"])
        assert 0.0 <= dim["score"] <= 100.0
        for sub_score in dim["subdimensiones"].values():
            assert not math.isnan(sub_score)
            assert 0.0 <= sub_score <= 100.0
