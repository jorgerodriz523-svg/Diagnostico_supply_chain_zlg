"""
modules/resultados.py
---------------------
Pantalla 4: Resultados del diagnóstico.
- Calcula scores y guarda en SQLite
- Muestra preview de scores por dimensión
- Ofrece descarga del HTML, PPTX y matriz de priorización
"""

import logging
import math
import streamlit as st
from datetime import datetime
from pathlib import Path

from utils.scoring  import calcular_scores, nivel_madurez, resumen_scores
from utils.loader   import get_preguntas, get_todas_estrategias_modulo
from utils.db       import inicializar_bd, marcar_diagnostico_completo
from generar_datos  import (
    construir_payload, validar_payload,
    generar_html_bytes, generar_pptx_bytes, generar_matriz_bytes,
)
from modules.layout import render_sidebar, render_content_header, NOMBRE_MODULO
from modules.seleccion_modulos import MODULO_META

logger = logging.getLogger(__name__)

LOGO_ZL   = str(Path(__file__).parent.parent / "assets" / "logo_zonalogistica.png")
TEMPLATE  = str(Path(__file__).parent.parent / "assets" / "dashboard_template.html")

NIVEL_COLOR = {
    "Básico"        : ("#FF0303", "#FEF2F2"),
    "En desarrollo" : ("#FFCB03", "#FFFDE7"),
    "Maduro"        : ("#A8DC00", "#F0FDF4"),
}


def _gauge_svg(value: float, titulo: str) -> str:
    """Mini gauge SVG para el preview de Streamlit: arco tricolor fijo
    (rojo/amarillo/verde) con aguja indicando la posición del puntaje."""
    import math
    # Proteger contra NaN, None o valores fuera de rango
    try:
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            value = 0.0
    except (TypeError, ValueError):
        value = 0.0
    value = max(0.0, min(100.0, value))

    def punto_arco(pct, cx, cy, r):
        ang = math.radians(180 - (pct / 100 * 180))
        return cx + r * math.cos(ang), cy - r * math.sin(ang)

    cx, cy, r = 100, 90, 70
    grosor = 14

    # Puntos de transición
    x0, y0     = cx - r, cy                  # 0%   - extremo izquierdo
    x64, y64   = punto_arco(64, cx, cy, r)    # 64%
    x85, y85   = punto_arco(85, cx, cy, r)    # 85%
    x100, y100 = cx + r, cy                   # 100% - extremo derecho

    # Aguja
    xv, yv = punto_arco(value, cx, cy, r)

    # HTML en una sola línea por elemento, sin líneas en blanco: el parser de
    # Markdown de Streamlit corta el bloque HTML en la primera línea vacía y
    # el resto queda como texto suelto fuera del <svg>.
    svg = (
        '<svg viewBox="0 0 200 115" xmlns="http://www.w3.org/2000/svg">'
        f'<path d="M{x0},{cy} A{r},{r} 0 0,1 {x100},{cy}" fill="none" stroke="#E5E7EB" stroke-width="{grosor}" stroke-linecap="round"/>'
        f'<path d="M{x0},{cy} A{r},{r} 0 0,1 {x64:.2f},{y64:.2f}" fill="none" stroke="#FF0303" stroke-width="{grosor}" stroke-linecap="round"/>'
        f'<path d="M{x64:.2f},{y64:.2f} A{r},{r} 0 0,1 {x85:.2f},{y85:.2f}" fill="none" stroke="#FFCB03" stroke-width="{grosor}" stroke-linecap="round"/>'
        f'<path d="M{x85:.2f},{y85:.2f} A{r},{r} 0 0,1 {x100},{cy}" fill="none" stroke="#A8DC00" stroke-width="{grosor}" stroke-linecap="round"/>'
        f'<line x1="{cx}" y1="{cy}" x2="{xv:.2f}" y2="{yv:.2f}" stroke="#003049" stroke-width="3" stroke-linecap="round"/>'
        f'<circle cx="{cx}" cy="{cy}" r="5" fill="#003049"/>'
        f'<text x="{cx}" y="82" text-anchor="middle" font-family="Poppins,Arial" font-size="22" font-weight="700" fill="#003049">{value:.1f}%</text>'
        f'<text x="{cx}" y="108" text-anchor="middle" font-family="Poppins,Arial" font-size="8.5" fill="#6B7280">{titulo}</text>'
        '</svg>'
    )
    return svg


def _puntajes_del_modulo(respuestas: dict, id_modulo: str) -> dict:
    """Extrae {id_pregunta: puntaje} solo de las preguntas que pertenecen a
    id_modulo, usando el id_modulo que cada respuesta ya trae guardado
    (ver modules/cuestionario.py::_registrar_respuesta)."""
    return {
        id_p: datos.get("puntaje", 0)
        for id_p, datos in respuestas.items()
        if datos.get("id_modulo") == id_modulo
    }


def render():
    st.markdown("""
    <style>
    .zl-semaforo {
        height: 5px;
        background: linear-gradient(to right, #FF0303 33%, #FFCB03 33% 66%, #A8DC00 66%);
        margin: 0 0 2rem 0;
        border-radius: 3px;
    }

    /* Demarcación pronunciada entre los bloques de resultados de cada
       módulo, cuando el diagnóstico evaluó más de uno */
    .zl-modulo-separador {
        height: 5px;
        background: linear-gradient(to right, #FF0303 33%, #FFCB03 33% 66%, #A8DC00 66%);
        margin: 3rem 0 1.5rem 0;
        border-radius: 3px;
    }
    .zl-modulo-tag {
        display: inline-block;
        background: #003049; color: #A8DC00;
        font-family: 'Poppins', sans-serif; font-size: 0.8rem; font-weight: 700;
        padding: 4px 16px; border-radius: 20px; margin-bottom: 1rem;
        letter-spacing: 0.05em; text-transform: uppercase;
    }

    /* Hero score */
    .zl-hero {
        background: #003049; border-radius: 16px;
        padding: 2rem 2rem 1.5rem 2rem; text-align: center;
        margin-bottom: 1.5rem;
    }
    .zl-hero-empresa {
        color: #A8DC00; font-family: 'Poppins',sans-serif;
        font-size: 0.85rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.1em; margin-bottom: 0.3rem;
    }
    .zl-hero-titulo {
        color: #ffffff; font-family: 'Poppins',sans-serif;
        font-size: 1.1rem; font-weight: 400; margin-bottom: 0;
    }

    /* Cards dimensiones */
    .zl-dim-card {
        background: #ffffff; border-radius: 14px;
        padding: 1.2rem 1.3rem;
        box-shadow: 0 2px 8px rgba(0,48,73,0.07);
        text-align: center;
        height: 100%;
    }
    .zl-dim-nombre {
        font-family: 'Poppins',sans-serif; font-size: 0.82rem;
        font-weight: 600; color: #003049; margin-bottom: 0.5rem;
    }
    .zl-dim-nivel {
        display: inline-block;
        font-family: 'Poppins',sans-serif; font-size: 0.74rem;
        font-weight: 700; padding: 2px 10px; border-radius: 20px;
        margin-top: 0.3rem;
    }

    /* Sección estrategias */
    .zl-seccion-titulo {
        font-family: 'Poppins',sans-serif; font-size: 1.1rem;
        font-weight: 700; color: #003049; margin: 1.5rem 0 0.5rem 0;
    }
    .estrategia-card {
        background: #ffffff; border-radius: 12px;
        padding: 1rem 1.2rem; margin-bottom: 0.75rem;
        border-left: 4px solid #003049;
        box-shadow: 0 1px 4px rgba(0,48,73,0.06);
    }
    .estrategia-card.critica  { border-left-color: #FF0303; }
    .estrategia-card.moderada { border-left-color: #FFCB03; }
    .estrategia-card.leve     { border-left-color: #A8DC00; }
    .est-header {
        display: flex; align-items: center; gap: 8px; margin-bottom: 0.3rem;
    }
    .est-badge {
        font-family: 'Poppins',sans-serif; font-size: 0.7rem;
        font-weight: 700; padding: 1px 8px; border-radius: 20px;
    }
    .est-badge.critica  { background: #FEE2E2; color: #991B1B; }
    .est-badge.moderada { background: #FEF9C3; color: #854D0E; }
    .est-badge.leve     { background: #DCFCE7; color: #14532D; }
    .est-subdim {
        font-family: 'Poppins',sans-serif; font-size: 0.72rem;
        color: #9AA1AC; font-weight: 500;
    }
    .est-texto {
        font-family: 'Poppins',sans-serif; font-size: 0.86rem;
        color: #1F2937; line-height: 1.5;
    }
    .est-meta {
        font-family: 'Poppins',sans-serif; font-size: 0.75rem;
        color: #9AA1AC; margin-top: 0.3rem;
    }

    /* Sección descargas (una por módulo: la clave incluye el id_modulo,
       por eso se usa selector por substring — mismo patrón que
       modules/layout.py usa para claves dinámicas por ítem) */
    [class*="st-key-zl_descarga_seccion_"] {
        background: #ffffff; border-radius: 16px;
        padding: 1.5rem 1.75rem; margin-top: 1.5rem;
        box-shadow: 0 2px 8px rgba(0,48,73,0.07);
    }
    .zl-descarga-titulo {
        font-family: 'Poppins',sans-serif; font-size: 1rem;
        font-weight: 700; color: #003049; margin-bottom: 1rem;
    }

    /* Botones de descarga */
    .stDownloadButton > button {
        font-family: 'Poppins',sans-serif !important;
        font-weight: 600 !important; font-size: 0.88rem !important;
        border-radius: 10px !important; width: 100% !important;
        padding: 0.6rem 1rem !important;
    }
    [class*="st-key-dl_html_"] .stDownloadButton > button {
        background: #003049 !important; color: #ffffff !important;
        border: none !important;
    }
    [class*="st-key-dl_pptx_"] .stDownloadButton > button {
        background: #C84B31 !important; color: #ffffff !important;
        border: none !important;
    }
    [class*="st-key-dl_matriz_"] .stDownloadButton > button {
        background: #0056A6 !important; color: #ffffff !important;
        border: none !important;
    }

    /* Botón nuevo diagnóstico */
    .st-key-btn_nuevo .stButton > button {
        background: transparent !important; color: #003049 !important;
        border: 2px solid #003049 !important; border-radius: 10px !important;
        font-family: 'Poppins',sans-serif !important; font-weight: 600 !important;
        width: 100% !important; margin-top: 1rem !important;
    }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
    """, unsafe_allow_html=True)

    empresa    = st.session_state.get("empresa", "")
    responsable= st.session_state.get("responsable", "")
    sector     = st.session_state.get("sector", "")
    cargo      = st.session_state.get("cargo", "")
    celular    = st.session_state.get("celular", "")
    correo     = st.session_state.get("correo", "")
    pais       = st.session_state.get("pais", "")
    ciudad     = st.session_state.get("ciudad", "")
    modulos    = st.session_state.get("modulos_seleccionados", ["MOD-01"])
    respuestas = st.session_state.get("respuestas", {})
    fecha      = datetime.now().strftime("%Y-%m-%d")

    # ── Sidebar + header de contenido ────────────────────────────────────────
    render_sidebar("resultados")
    render_content_header("Resultados")

    st.markdown('<div class="zl-semaforo"></div>', unsafe_allow_html=True)

    # ── Paso 1: calcular los scores de TODOS los módulos seleccionados ────────
    # (siempre se recalcula, para evitar NaN cacheado entre reruns)
    scores_por_modulo = {}
    for id_m in modulos:
        respuestas_puntaje_m = _puntajes_del_modulo(respuestas, id_m)
        if not respuestas_puntaje_m:
            # Si no hay respuestas para este módulo, poner 0 en todas sus preguntas
            for _, row in get_preguntas(id_m).iterrows():
                respuestas_puntaje_m[row["ID Pregunta"].strip()] = 0
        scores_por_modulo[id_m] = calcular_scores(id_m, respuestas_puntaje_m)

    # Módulos cuyo id ya no tiene parametrización activa (p.ej. un
    # diagnóstico antiguo hecho sobre un módulo que luego se desactivó) no
    # aportan dimensiones que graficar.
    modulos_validos = [m for m in modulos if scores_por_modulo[m]["dimensiones"]]

    if not modulos_validos:
        st.error(
            "⚠ No encontramos resultados disponibles para este diagnóstico: "
            "los módulos evaluados ya no están activos. Contacte a soporte si "
            "cree que esto es un error.")
        if st.button("← Volver al inicio"):
            st.session_state["pantalla"] = "inicio"
            st.rerun()
        st.stop()

    # ── Paso 2: cerrar el diagnóstico en BD (solo una vez, no en cada
    # rerun/descarga). Las respuestas ya se guardaron de forma incremental
    # durante el cuestionario; aquí solo se marca como completo y se fija
    # el score general (promedio simple entre los módulos válidos). ───────────
    if not st.session_state.get("diagnostico_guardado"):
        id_diagnostico = st.session_state.get("id_diagnostico")
        try:
            inicializar_bd()
            score_general_combinado = round(
                sum(scores_por_modulo[m]["score_general"] for m in modulos_validos)
                / len(modulos_validos), 2)
            if id_diagnostico:
                marcar_diagnostico_completo(
                    id_diagnostico=id_diagnostico,
                    scores_por_modulo=scores_por_modulo,
                    score_general=score_general_combinado,
                    fecha=fecha,
                )
            st.session_state["diagnostico_guardado"] = True
        except Exception as e:
            logger.exception(
                "Error cerrando diagnóstico en BD (id_diagnostico=%s)", id_diagnostico)
            st.warning(f"No se pudo guardar en la base de datos: {e}")

    # ── Paso 3: un bloque completo de resultados por cada módulo evaluado ─────
    for idx, id_m in enumerate(modulos):
        scores        = scores_por_modulo[id_m]
        nombre_modulo = NOMBRE_MODULO.get(id_m, id_m)

        if not scores["dimensiones"]:
            st.warning(
                f"⚠ El módulo **{nombre_modulo}** ya no está activo en la "
                "parametrización actual: no se muestran resultados para él.")
            continue

        # Demarcación pronunciada entre bloques cuando hay más de un módulo
        if idx > 0:
            st.markdown('<div class="zl-modulo-separador"></div>', unsafe_allow_html=True)
        icono_modulo = MODULO_META.get(id_m, {}).get("icono", "📋")
        st.markdown(
            f'<span class="zl-modulo-tag">{icono_modulo} {nombre_modulo}</span>',
            unsafe_allow_html=True)

        score_general = scores["score_general"]
        try:
            score_general = float(score_general)
            if math.isnan(score_general) or math.isinf(score_general):
                score_general = 0.0
        except (TypeError, ValueError):
            score_general = 0.0
        score_general = round(max(0.0, min(100.0, score_general)), 1)
        nm_general    = nivel_madurez(score_general)

        # ── Hero: gauge general ───────────────────────────────────────────────
        st.markdown(f"""
        <div class="zl-hero">
            <p class="zl-hero-empresa">{empresa}</p>
            <p class="zl-hero-titulo">Diagnóstico de Supply Chain · {nombre_modulo}</p>
        </div>
        """, unsafe_allow_html=True)

        col_g, col_info = st.columns([1, 1])
        with col_g:
            st.markdown(_gauge_svg(score_general, "Madurez General"), unsafe_allow_html=True)
        with col_info:
            color_nm, bg_nm = NIVEL_COLOR.get(nm_general["etiqueta"], ("#003049", "#F4F5F7"))
            st.markdown(f"""
            <div style="padding: 1.5rem 0;">
                <div style="font-family:Poppins,sans-serif; font-size:0.82rem;
                            color:#9AA1AC; font-weight:600; text-transform:uppercase;
                            letter-spacing:0.06em; margin-bottom:0.5rem;">
                    Nivel de madurez
                </div>
                <div style="background:{bg_nm}; border-radius:12px; padding:1rem 1.2rem;">
                    <span style="font-family:Poppins,sans-serif; font-size:1.4rem;
                                 font-weight:700; color:{color_nm};">
                        {nm_general['emoji']} {nm_general['etiqueta']}
                    </span>
                    <p style="font-family:Poppins,sans-serif; font-size:0.83rem;
                              color:#6B7280; margin-top:0.5rem; margin-bottom:0;">
                        Responsable: {responsable}<br>
                        Sector: {sector}<br>Fecha: {fecha}
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Gauges por dimensión ───────────────────────────────────────────────
        dimensiones = scores["dimensiones"]
        cols_dim    = st.columns(len(dimensiones))
        for col, (id_dim, data) in zip(cols_dim, dimensiones.items()):
            nm    = nivel_madurez(data["score"])
            c_txt, c_bg = NIVEL_COLOR.get(nm["etiqueta"], ("#003049", "#F4F5F7"))
            with col:
                st.markdown(_gauge_svg(data["score"], data["nombre"]), unsafe_allow_html=True)
                st.markdown(
                    f'<div style="text-align:center">'
                    f'<span class="zl-dim-nivel" style="background:{c_bg};color:{c_txt};">'
                    f'{nm["emoji"]} {nm["etiqueta"]}</span></div>',
                    unsafe_allow_html=True)

        st.markdown("---")

        # ── Estrategias recomendadas ───────────────────────────────────────────
        st.markdown('<p class="zl-seccion-titulo">📋 Estrategias recomendadas</p>',
                    unsafe_allow_html=True)
        st.markdown(
            '<p style="font-family:Poppins,sans-serif;font-size:0.84rem;'
            'color:#6B7280;margin-bottom:1rem;">'
            'Las siguientes acciones están priorizadas según las brechas identificadas '
            'en su evaluación.</p>',
            unsafe_allow_html=True)

        respuestas_puntaje_m = _puntajes_del_modulo(respuestas, id_m)
        estrategias = get_todas_estrategias_modulo(id_m, respuestas_puntaje_m)

        if estrategias:
            for est in estrategias:
                brecha   = est["nivel_brecha"].lower()
                css_cls  = {"crítica": "critica", "moderada": "moderada", "leve": "leve"}.get(
                    brecha, "leve")
                st.markdown(f"""
                <div class="estrategia-card {css_cls}">
                    <div class="est-header">
                        <span class="est-badge {css_cls}">{est['nivel_brecha']}</span>
                        <span class="est-subdim">{est['subdimension']}</span>
                    </div>
                    <p class="est-texto">{est['estrategia']}</p>
                    <p class="est-meta">
                        Impacto: {est['impacto']} &nbsp;·&nbsp; Plazo: {est['plazo']}
                    </p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No se encontraron estrategias para las respuestas registradas.")

        # ── Sección de descargas ───────────────────────────────────────────────
        with st.container(key=f"zl_descarga_seccion_{id_m}"):
            st.markdown('<p class="zl-descarga-titulo">📥 Descargar resultados</p>',
                        unsafe_allow_html=True)

            payload = construir_payload(
                id_modulo      = id_m,
                empresa        = empresa,
                scores         = scores,
                ruta_logo_zona = LOGO_ZL if Path(LOGO_ZL).exists() else None,
            )
            validar_payload(payload)

            col_d1, col_d2, col_d3 = st.columns(3)

            # Dashboard HTML
            with col_d1:
                try:
                    html_bytes = generar_html_bytes(payload, template=TEMPLATE)
                    with st.container(key=f"dl_html_{id_m}"):
                        st.download_button(
                            label="🌐 Dashboard interactivo (.html)",
                            data=html_bytes,
                            file_name=f"Diagnostico_{empresa}_{nombre_modulo}_{fecha}.html",
                            mime="text/html",
                            key=f"btn_dl_html_{id_m}",
                        )
                except FileNotFoundError:
                    logger.error(
                        "Template HTML no encontrado en assets/ (id_modulo=%s)", id_m)
                    st.warning("Template HTML no encontrado en assets/.")

            # PowerPoint
            with col_d2:
                try:
                    pptx_bytes = generar_pptx_bytes(
                        payload, id_modulo=id_m, ruta_logo_zona=LOGO_ZL)
                    with st.container(key=f"dl_pptx_{id_m}"):
                        st.download_button(
                            label="📊 Presentación (.pptx)",
                            data=pptx_bytes,
                            file_name=f"Presentacion_{empresa}_{nombre_modulo}_{fecha}.pptx",
                            mime="application/vnd.openxmlformats-officedocument"
                                 ".presentationml.presentation",
                            key=f"btn_dl_pptx_{id_m}",
                        )
                except RuntimeError as e:
                    logger.warning(
                        "Kaleido no pudo generar el PPTX (id_modulo=%s): %s", id_m, e)
                    st.warning(str(e))
                except Exception as e:
                    logger.exception(
                        "Error inesperado generando el PPTX (id_modulo=%s)", id_m)
                    st.warning(f"No se pudo generar el PowerPoint: {e}")

            # Matriz de priorización
            with col_d3:
                try:
                    n = len(estrategias)
                    labels    = [str(i+1) for i in range(n)]
                    impacto   = [10 if e["impacto"]=="Alto" else 7 if e["impacto"]=="Medio" else 4
                                 for e in estrategias]
                    urgencia  = [10 if e["nivel_brecha"]=="Crítica" else
                                 7  if e["nivel_brecha"]=="Moderada" else 5
                                 for e in estrategias]
                    inversion = [3 if e["plazo"]=="Largo plazo" else
                                 2 if e["plazo"]=="Mediano plazo" else 1
                                 for e in estrategias]
                    descripciones = [est["estrategia"] for est in estrategias]
                    if n > 0:
                        matriz_bytes = generar_matriz_bytes(
                            labels, impacto, urgencia, inversion, descripciones)
                        with st.container(key=f"dl_matriz_{id_m}"):
                            st.download_button(
                                label="🎯 Matriz de priorización (.html)",
                                data=matriz_bytes,
                                file_name=f"Matriz_{empresa}_{nombre_modulo}_{fecha}.html",
                                mime="text/html",
                                key=f"btn_dl_matriz_{id_m}",
                            )
                except Exception as e:
                    logger.exception(
                        "Error generando la matriz de priorización (id_modulo=%s)", id_m)
                    st.warning(f"No se pudo generar la matriz: {e}")

    # ── Nuevo diagnóstico ─────────────────────────────────────────────────────
    with st.container(key="btn_nuevo"):
        if st.button("↩ Realizar otro diagnóstico"):
            keys_a_limpiar = [
                # Datos de identificación
                "empresa", "responsable", "sector",
                "cargo", "celular", "correo", "pais", "ciudad",
                # Datos del diagnóstico
                "modulos_seleccionados", "supply_chain_activo",
                "respuestas", "scores_calculados",
                "modulo_actual_idx", "pregunta_actual_idx",
                "id_modulo_calc", "diagnostico_guardado", "id_diagnostico",
            ]
            for key in keys_a_limpiar:
                st.session_state.pop(key, None)

            # Limpiar también sliders, selectboxes, niveles y
            # observaciones guardados por pregunta
            for k in list(st.session_state.keys()):
                if (k.startswith("nivel_") or
                        k.startswith("slider_") or
                        k.startswith("select_") or
                        k.startswith("obs_") or
                        k.startswith("cb_MOD")):
                    del st.session_state[k]
            st.session_state["pantalla"] = "inicio"
            st.rerun()
