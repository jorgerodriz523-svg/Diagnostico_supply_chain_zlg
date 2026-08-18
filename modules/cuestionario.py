"""
modules/cuestionario.py
-----------------------
Pantalla 3: Cuestionario pregunta a pregunta con escala 0–5.
Navega módulo por módulo; al terminar todos pasa a resultados.
"""

import logging

import streamlit as st
from utils.loader import get_preguntas, get_opciones_modulo
from utils.scoring import calcular_score_pregunta
from utils.db import guardar_respuesta_incremental
from modules.layout import render_sidebar, render_content_header

logger = logging.getLogger(__name__)

NIVEL_LABELS = {
    0: ("0 — Inexistente",      "#FF0303", "🔴"),
    1: ("1 — Muy incipiente",   "#FF6B35", "🟠"),
    2: ("2 — Básico",           "#FFCB03", "🟡"),
    3: ("3 — En desarrollo",    "#7BC67E", "🟢"),
    4: ("4 — Avanzado",         "#2E7D32", "🟢"),
    5: ("5 — Óptimo",           "#003049", "⭐"),
}

# Color del indicador de nivel debajo del selectbox de calificación
NIVEL_COLOR_INDICADOR = {
    0: "#FF0303", 1: "#FF0303",
    2: "#FFCB03",
    3: "#7BC67E",
    4: "#003049", 5: "#003049",
}


def _registrar_respuesta(respuestas, id_pregunta, id_modulo, id_dimension, subdimension, nivel, observacion=""):
    """
    Fija la respuesta en session_state (como ya hacía la app) y además la
    autoguarda en la BD de inmediato, para no perder el avance si el
    usuario sale antes de terminar el cuestionario.
    """
    puntaje = calcular_score_pregunta(nivel)
    respuestas[id_pregunta] = {
        "nivel"       : nivel,
        "puntaje"     : puntaje,
        "id_modulo"   : id_modulo,
        "id_dimension": id_dimension,
        "subdimension": subdimension,
        "opcion"      : str(nivel),
        "observacion" : observacion,
    }
    st.session_state["respuestas"] = respuestas

    id_diagnostico = st.session_state.get("id_diagnostico")
    if id_diagnostico:
        try:
            guardar_respuesta_incremental(
                id_diagnostico=id_diagnostico,
                id_pregunta=id_pregunta,
                id_modulo=id_modulo,
                id_dimension=id_dimension,
                subdimension=subdimension,
                opcion=str(nivel),
                puntaje=puntaje,
                observacion=observacion,
            )
        except Exception as e:
            logger.exception(
                "Error guardando respuesta incremental (id_diagnostico=%s, id_pregunta=%s)",
                id_diagnostico, id_pregunta)
            st.warning(f"No se pudo guardar automáticamente la respuesta: {e}")

    return puntaje


def render():
    st.markdown("""
    <style>
    .zl-semaforo {
        height: 5px;
        background: linear-gradient(to right, #FF0303 33%, #FFCB03 33% 66%, #A8DC00 66%);
        margin: 0 0 1.5rem 0;
        border-radius: 3px;
    }

    /* Módulo y progreso */
    .zl-modulo-tag {
        display: inline-block;
        background: #003049; color: #A8DC00;
        font-family: 'Poppins', sans-serif; font-size: 0.75rem; font-weight: 700;
        padding: 3px 14px; border-radius: 20px; margin-bottom: 0.5rem;
        letter-spacing: 0.05em; text-transform: uppercase;
    }
    .zl-prog-info {
        font-family: 'Poppins', sans-serif; font-size: 0.82rem;
        color: #6B7280; margin-bottom: 0.25rem;
    }
    .zl-prog-bar-bg {
        background: #E5E7EB; border-radius: 99px; height: 6px;
        margin-bottom: 1.5rem;
    }
    .zl-prog-bar-fill {
        background: linear-gradient(to right, #003049, #A8DC00);
        border-radius: 99px; height: 6px; transition: width 0.4s;
    }

    /* Card de pregunta */
    .st-key-zl_q_card {
        background: #ffffff; border-radius: 16px;
        padding: 2rem 2rem 1.5rem 2rem;
        box-shadow: 0 2px 8px rgba(0,48,73,0.08), 0 0 0 1px rgba(0,48,73,0.06);
        margin-bottom: 1.25rem;
    }
    .zl-q-num {
        font-family: 'Poppins', sans-serif; font-size: 0.78rem; font-weight: 700;
        color: #9AA1AC; text-transform: uppercase; letter-spacing: 0.08em;
        margin-bottom: 0.5rem;
    }
    .zl-q-texto {
        font-family: 'Poppins', sans-serif; font-size: 1.08rem; font-weight: 600;
        color: #003049; line-height: 1.5; margin-bottom: 0.5rem;
    }
    .zl-q-subdim {
        display: inline-block;
        background: #F0F4F8; color: #4B6278;
        font-family: 'Poppins', sans-serif; font-size: 0.74rem; font-weight: 600;
        padding: 2px 10px; border-radius: 20px; margin-bottom: 1.25rem;
    }

    /* Columna de calificación */
    .zl-q-calif-label {
        font-family: 'Poppins', sans-serif; font-size: 0.72rem; font-weight: 700;
        color: #9AA1AC; text-transform: uppercase; letter-spacing: 0.06em;
        margin-bottom: 0.4rem;
    }
    .zl-nivel-indicador {
        font-family: 'Poppins', sans-serif; font-size: 0.82rem; font-weight: 600;
        margin-top: 0.5rem; margin-bottom: 0;
    }

    /* Selectbox de calificación */
    .stSelectbox > div > div {
        border: 1.5px solid #003049 !important;
        border-radius: 8px !important;
        font-family: 'Poppins', sans-serif !important;
        color: #003049 !important;
        background: #ffffff !important;
        width: 100% !important;
    }
    .stSelectbox > div > div:focus-within {
        box-shadow: 0 0 0 3px rgba(0,48,73,0.12) !important;
    }

    /* Tabla de guías de calificación (todos los niveles) */
    .zl-guia-tabla {
        border-radius: 12px;
        overflow: hidden;
        margin-top: 1rem;
        border: 1px solid #E5E7EB;
    }
    .zl-guia-tabla-header {
        background: #003049; color: #ffffff;
        padding: 0.5rem 1rem;
        font-family: 'Poppins', sans-serif;
        font-size: 0.82rem; font-weight: 600;
    }
    .zl-guia-fila {
        display: flex;
        padding: 0.6rem 1rem;
        border-bottom: 1px solid #E5E7EB;
    }
    .zl-guia-fila:last-child { border-bottom: none; }
    .zl-guia-fila-sel {
        background: #EEF3F6;
        border-left: 4px solid #003049;
    }
    .zl-guia-fila-normal {
        background: #F9FAFB;
    }
    .zl-guia-col-nivel {
        flex: 0 0 80px; width: 80px;
        font-family: 'Poppins', sans-serif;
        font-weight: 700; font-size: 0.82rem;
    }
    .zl-guia-col-texto {
        flex: 1;
        font-family: 'Poppins', sans-serif;
        font-size: 0.81rem; color: #374151; line-height: 1.45;
        font-weight: 400;
    }
    .zl-guia-fila-sel .zl-guia-col-texto {
        font-weight: 700;
    }

    /* Bloque de observaciones del cliente */
    .zl-obs-box {
        border-radius: 12px 12px 0 0;
        overflow: hidden;
        margin-top: 1rem;
        border: 1px solid #E5E7EB;
        border-bottom: none;
    }
    .zl-obs-box-header {
        background: #003049; color: #ffffff;
        padding: 0.5rem 1rem;
        font-family: 'Poppins', sans-serif;
        font-size: 0.82rem; font-weight: 600;
    }
    .st-key-zl_obs_wrap {
        border: 1px solid #E5E7EB; border-top: none;
        border-radius: 0 0 12px 12px;
        background: #F9FAFB;
        padding: 0.75rem 1rem 0.9rem 1rem;
    }
    .st-key-zl_obs_wrap .stTextArea textarea {
        border: 1.5px solid #D1D5DB !important;
        border-radius: 8px !important;
        font-family: 'Poppins', sans-serif !important;
        font-size: 0.85rem !important;
        color: #003049 !important;
        background: #ffffff !important;
    }
    .st-key-zl_obs_wrap .stTextArea textarea:focus {
        border-color: #003049 !important;
        box-shadow: 0 0 0 3px rgba(0,48,73,0.12) !important;
    }

    /* Botones */
    .stButton > button {
        font-family: 'Poppins', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        border-radius: 10px !important;
        padding: 0.6rem 1.5rem !important;
        width: 100% !important;
    }
    .st-key-btn_siguiente .stButton > button {
        background: #003049 !important; color: #ffffff !important;
        border: none !important;
    }
    .st-key-btn_siguiente .stButton > button:hover { background: #004d6e !important; }
    .st-key-btn_anterior .stButton > button {
        background: transparent !important; color: #6B7280 !important;
        border: 1.5px solid #D1D5DB !important;
    }
    .st-key-btn_anterior .stButton > button:hover {
        background: #F3F4F6 !important; color: #003049 !important;
    }
    .st-key-btn_finalizar .stButton > button {
        background: #A8DC00 !important; color: #003049 !important;
        border: none !important;
    }
    .st-key-btn_finalizar .stButton > button:hover { background: #8FBB00 !important; }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
    """, unsafe_allow_html=True)

    modulos   = st.session_state.get("modulos_seleccionados", [])
    mod_idx   = st.session_state.get("modulo_actual_idx", 0)
    preg_idx  = st.session_state.get("pregunta_actual_idx", 0)
    respuestas = st.session_state.get("respuestas", {})

    if not modulos or mod_idx >= len(modulos):
        st.session_state["pantalla"] = "resultados"
        st.rerun()
        return

    id_modulo = modulos[mod_idx]

    # Cargar preguntas y opciones del módulo actual
    preguntas_df = get_preguntas(id_modulo)
    opciones_df  = get_opciones_modulo(id_modulo)
    total_pregs  = len(preguntas_df)

    if preg_idx >= total_pregs:
        # Módulo terminado → siguiente módulo o resultados
        siguiente_idx = mod_idx + 1
        if siguiente_idx < len(modulos):
            st.session_state["modulo_actual_idx"]   = siguiente_idx
            st.session_state["pregunta_actual_idx"] = 0
        else:
            st.session_state["pantalla"] = "resultados"
        st.rerun()
        return

    pregunta     = preguntas_df.iloc[preg_idx]
    id_pregunta  = pregunta["ID Pregunta"].strip()
    texto        = pregunta["Texto de la pregunta"].strip()
    subdimension = pregunta["Subdimensión"].strip()
    id_dimension = pregunta["ID Dimensión"].strip()

    # Opciones de esta pregunta (niveles 0-5)
    ops_preg = opciones_df[
        opciones_df["ID Pregunta"].str.strip() == id_pregunta
    ].sort_values("Nivel (0-5)").reset_index(drop=True)

    # Progreso global (todas las preguntas de todos los módulos)
    total_global  = sum(len(get_preguntas(m)) for m in modulos)
    pregs_antes   = sum(len(get_preguntas(modulos[i])) for i in range(mod_idx))
    progreso_abs  = pregs_antes + preg_idx + 1
    pct_progreso  = round(progreso_abs / total_global * 100)

    # Nombre del módulo (desde las preguntas)
    nombre_modulo = {
        "MOD-01": "Almacenamiento",
        "MOD-02": "Transporte",
        "MOD-03": "Inventarios",
        "MOD-04": "Planeación",
        "MOD-05": "Distribución",
    }.get(id_modulo, id_modulo)

    # ── Sidebar + header de contenido ────────────────────────────────────────
    render_sidebar("cuestionario")
    render_content_header(f"Cuestionario · {nombre_modulo}")

    st.markdown('<div class="zl-semaforo"></div>', unsafe_allow_html=True)

    # ── Progreso ──────────────────────────────────────────────────────────────
    st.markdown(f'<span class="zl-modulo-tag">📋 {nombre_modulo}</span>',
                unsafe_allow_html=True)
    st.markdown(
        f'<p class="zl-prog-info">Pregunta {preg_idx + 1} de {total_pregs} '
        f'· Progreso global {pct_progreso}%</p>',
        unsafe_allow_html=True)
    st.markdown(
        f'<div class="zl-prog-bar-bg">'
        f'<div class="zl-prog-bar-fill" style="width:{pct_progreso}%"></div>'
        f'</div>',
        unsafe_allow_html=True)

    # ── Card de pregunta (dos columnas: 80% pregunta / 20% calificación) ───────
    with st.container(key="zl_q_card"):
        col_izq, col_der = st.columns([4, 1])

        with col_izq:
            st.markdown(f"""
            <p class="zl-q-num">Pregunta {preg_idx + 1}</p>
            <p class="zl-q-texto">{texto}</p>
            <span class="zl-q-subdim">{subdimension}</span>
            """, unsafe_allow_html=True)

        with col_der:
            st.markdown('<p class="zl-q-calif-label">Calificación</p>', unsafe_allow_html=True)

            opciones_nivel = [NIVEL_LABELS[n][0] for n in range(6)]
            nivel_previo = st.session_state.get(f"nivel_{id_pregunta}", 0)
            idx_previo = nivel_previo if nivel_previo in range(6) else 0

            opcion_sel = st.selectbox(
                "Calificación",
                opciones_nivel,
                index=idx_previo,
                key=f"select_{id_pregunta}",
                label_visibility="collapsed",
            )
            nivel = int(opcion_sel[0])

            color_ind = NIVEL_COLOR_INDICADOR.get(nivel, "#003049")
            emoji_ind = NIVEL_LABELS.get(nivel, (str(nivel), "#003049", ""))[2]
            etiqueta_ind = NIVEL_LABELS.get(nivel, (str(nivel), "#003049", ""))[0].split("—", 1)[-1].strip()
            st.markdown(
                f'<p class="zl-nivel-indicador" style="color:{color_ind};">'
                f'{emoji_ind} {etiqueta_ind}</p>',
                unsafe_allow_html=True)

    # Guardar nivel en session_state para recuperarlo si vuelve atrás
    st.session_state[f"nivel_{id_pregunta}"] = nivel

    # Tabla de guías de calificación (izquierda) + observaciones del cliente (derecha)
    col_guia, col_obs = st.columns([3, 2])

    with col_guia:
        if not ops_preg.empty:
            filas_html = ""
            for _, fila in ops_preg.iterrows():
                nivel_fila = int(fila["Nivel (0-5)"])
                etiqueta = NIVEL_LABELS.get(nivel_fila, (str(nivel_fila), "#003049", ""))[0]
                color_fila = NIVEL_LABELS.get(nivel_fila, (str(nivel_fila), "#003049", ""))[1]
                emoji = NIVEL_LABELS.get(nivel_fila, ("", "#003049", ""))[2]
                guia = str(fila.get("Guía para el cliente", "")).strip()
                if "si:" in guia.lower():
                    guia = guia.split("si:", 1)[-1].strip()

                etiqueta_txt = etiqueta.split("—", 1)[-1].strip()
                clase_fila = "zl-guia-fila-sel" if nivel_fila == nivel else "zl-guia-fila-normal"

                # Sin saltos de línea ni indentación: evita que el parser de
                # Markdown interprete el HTML como bloque de código indentado.
                filas_html += (
                    f'<div class="zl-guia-fila {clase_fila}">'
                    f'<div class="zl-guia-col-nivel" style="color:{color_fila};">{nivel_fila} {emoji}</div>'
                    f'<div class="zl-guia-col-texto">{etiqueta_txt} — {guia}</div>'
                    f'</div>'
                )

            html_tabla = (
                '<div class="zl-guia-tabla">'
                '<div class="zl-guia-tabla-header">📖 Guía de calificación</div>'
                + filas_html +
                '</div>'
            )
            st.markdown(html_tabla, unsafe_allow_html=True)

    with col_obs:
        obs_previa = st.session_state.get(
            f"obs_{id_pregunta}",
            respuestas.get(id_pregunta, {}).get("observacion", ""),
        )
        st.markdown('<div class="zl-obs-box"><div class="zl-obs-box-header">📝 Observaciones</div></div>',
                    unsafe_allow_html=True)
        with st.container(key="zl_obs_wrap"):
            observacion = st.text_area(
                "Observaciones",
                value=obs_previa,
                key=f"obs_area_{id_pregunta}",
                height=230,
                placeholder="Escribe aquí alguna observación relacionada con tu respuesta...",
                label_visibility="collapsed",
            )
        st.session_state[f"obs_{id_pregunta}"] = observacion

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Navegación ────────────────────────────────────────────────────────────
    col_ant, col_sig = st.columns([1, 2])

    with col_ant:
        with st.container(key="btn_anterior"):
            if st.button("← Anterior", key=f"ant_{id_pregunta}"):
                # Solo se autoguarda si la pregunta ya tenía una respuesta
                # previa, si el usuario realmente seleccionó un nivel
                # distinto del valor por defecto, o si escribió una
                # observación. Evita crear en la BD un registro para una
                # pregunta que solo se visitó de paso (p.ej. al llegar por
                # "Siguiente" y retroceder sin responderla), ya que el
                # selectbox siempre expone un valor (0) aunque nunca se
                # haya tocado.
                if id_pregunta in respuestas or nivel != 0 or observacion.strip():
                    _registrar_respuesta(respuestas, id_pregunta, id_modulo,
                                          id_dimension, subdimension, nivel,
                                          observacion)

                if preg_idx > 0:
                    st.session_state["pregunta_actual_idx"] = preg_idx - 1
                elif mod_idx > 0:
                    prev_mod   = modulos[mod_idx - 1]
                    n_prev     = len(get_preguntas(prev_mod))
                    st.session_state["modulo_actual_idx"]   = mod_idx - 1
                    st.session_state["pregunta_actual_idx"] = n_prev - 1
                else:
                    st.session_state["pantalla"] = "seleccion_modulos"
                st.rerun()

    with col_sig:
        es_ultima = (preg_idx == total_pregs - 1) and (mod_idx == len(modulos) - 1)
        label_btn = "Ver resultados →" if es_ultima else "Siguiente →"
        key_btn   = "btn_finalizar" if es_ultima else "btn_siguiente"

        with st.container(key=key_btn):
            if st.button(label_btn, key=f"sig_{id_pregunta}"):
                # Guardar respuesta actual
                _registrar_respuesta(respuestas, id_pregunta, id_modulo,
                                      id_dimension, subdimension, nivel,
                                      observacion)

                # Avanzar
                if preg_idx < total_pregs - 1:
                    st.session_state["pregunta_actual_idx"] = preg_idx + 1
                elif mod_idx < len(modulos) - 1:
                    st.session_state["modulo_actual_idx"]   = mod_idx + 1
                    st.session_state["pregunta_actual_idx"] = 0
                else:
                    st.session_state["pantalla"] = "resultados"
                st.rerun()
