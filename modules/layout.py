"""
modules/layout.py
------------------
Componentes de layout compartidos por todas las pantallas:
- render_sidebar(): sidebar izquierdo fijo (logo, usuario, navegación).
- render_content_header(): header del área de contenido derecha
  (nombre de la pantalla actual + badge de la empresa).

No introduce lógica de navegación nueva: los saltos de pantalla que
permite el sidebar solo usan las mismas claves de session_state
("pantalla", "modulos_seleccionados", "modulo_actual_idx",
"diagnostico_guardado") que ya gestiona el resto de la app, y únicamente
hacia pantallas que el usuario ya alcanzó en el flujo normal.
"""

import streamlit as st
from pathlib import Path

from utils.loader import get_preguntas, get_dimensiones

LOGO_ZL = Path(__file__).parent.parent / "assets" / "logo_zonalogistica.png"

NOMBRE_MODULO = {
    "MOD-01": "Almacenamiento",
    "MOD-02": "Transporte",
    "MOD-03": "Inventarios",
    "MOD-04": "Planeación",
    "MOD-05": "Distribución",
}


def _sidebar_css():
    st.markdown("""
    <style>
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"][aria-expanded="false"] {
        background: #003049 !important;
        min-width: 272px !important;
        max-width: 272px !important;
        width: 272px !important;
        transform: none !important;
        visibility: visible !important;
        margin-left: 0 !important;
    }
    section[data-testid="stSidebar"] * { font-family: 'Poppins', sans-serif; }
    section[data-testid="stSidebar"] > div { padding-top: 0.5rem; }

    /* Sidebar fijo: se oculta el botón nativo para colapsarlo por accidente */
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    .st-key-zl_side_logo { text-align: center; margin: 0.5rem 0 1.25rem 0; }

    .zl-side-user {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.14);
        border-radius: 10px;
        padding: 0.75rem 0.9rem;
        margin: 0 0.25rem 1.5rem 0.25rem;
    }
    .zl-side-user-nombre {
        color: #ffffff; font-size: 0.86rem; font-weight: 600; margin: 0;
    }
    .zl-side-user-empresa {
        color: #A8DC00; font-size: 0.76rem; font-weight: 500; margin: 0.15rem 0 0 0;
    }

    .zl-nav-item, .zl-nav-item-active {
        display: flex; align-items: center; gap: 10px;
        border-radius: 8px; padding: 0.55rem 0.9rem;
        margin: 0 0.25rem 0.25rem 0.25rem;
        font-size: 0.88rem; font-weight: 500;
    }
    .zl-nav-item { color: rgba(255,255,255,0.72); }
    .zl-nav-item-active {
        background: #A8DC00; color: #003049 !important; font-weight: 700;
    }

    section[data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        color: rgba(255,255,255,0.72) !important;
        border: none !important;
        text-align: left !important;
        justify-content: flex-start !important;
        font-weight: 500 !important;
        font-size: 0.88rem !important;
        padding: 0.55rem 0.9rem !important;
        border-radius: 8px !important;
        width: 100% !important;
        margin: 0 0 0.25rem 0 !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.10) !important;
        color: #ffffff !important;
    }

    .zl-sub-item {
        display: flex; align-items: center; gap: 8px;
        padding: 0.32rem 0.9rem 0.32rem 2.3rem;
        font-size: 0.78rem; color: rgba(255,255,255,0.5);
    }
    .zl-sub-item-actual { color: #A8DC00 !important; font-weight: 700; }
    .zl-sub-item-hecho { color: rgba(255,255,255,0.85) !important; }

    .zl-nav-sep {
        height: 1px; background: rgba(255,255,255,0.12);
        margin: 1rem 0.25rem;
    }

    /* Árbol de navegación del cuestionario */
    .zl-side-modulo-tag {
        font-family: 'Poppins', sans-serif; font-weight: 700; color: #A8DC00;
        font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em;
        margin: 0 0.25rem 0.75rem 0.25rem;
    }
    .zl-side-nav-label {
        font-family: 'Poppins', sans-serif; font-size: 0.7rem; color: #9AA1AC;
        text-transform: uppercase; letter-spacing: 0.1em;
        margin: 0 0.25rem 0.5rem 0.25rem;
    }
    .zl-side-dim-count {
        font-family: 'Poppins', sans-serif; font-size: 0.78rem; font-weight: 600;
        text-align: right; margin: 0.85rem 0.25rem 0 0;
        white-space: nowrap;
    }
    /* Botón-toggle de dimensión (desplegable, sin depender de íconos nativos) */
    [class*="st-key-navdim_"] .stButton > button {
        background: transparent !important; border: none !important;
        font-family: 'Poppins', sans-serif !important; font-size: 0.82rem !important;
        font-weight: 700 !important; color: #ffffff !important;
        text-align: left !important; justify-content: flex-start !important;
        padding: 0.45rem 0.25rem !important; width: 100% !important;
        box-shadow: none !important; margin: 0.4rem 0 0 0 !important;
    }
    [class*="st-key-navdim_"] .stButton > button:hover {
        color: #A8DC00 !important; background: rgba(255,255,255,0.06) !important;
    }

    /* Árbol de preguntas: implementado con st.radio en lugar de st.button
       (evita el re-render con estilos internos de Streamlit al hacer clic,
       que encogía visualmente el texto). Se oculta el marcador nativo del
       radio; los indicadores ●/○ llegan coloreados vía markdown y la
       pregunta actual se resalta con :has(input:checked), así que el
       tamaño y la posición del texto no cambian en ningún estado
       (reposo, hover, clic, focus). */
    [class*="st-key-navradio_"] { margin: 0 !important; }
    [class*="st-key-navradio_"] [data-testid="stWidgetLabel"] { display: none !important; }
    [class*="st-key-navradio_"] [data-testid="stRadioGroup"] {
        gap: 0 !important; flex-direction: column !important;
    }
    [class*="st-key-navradio_"] [data-testid="stRadioOption"] {
        margin: 0 !important; min-height: 1.75rem !important; border-radius: 4px;
    }
    [class*="st-key-navradio_"] [data-testid="stRadioOption"]:hover {
        background: rgba(255,255,255,0.08) !important;
    }
    [class*="st-key-navradio_"] [data-testid="stRadioOption"] div:has(+ [data-testid="stMarkdownContainer"]) {
        display: none !important;
    }
    [class*="st-key-navradio_"] [data-testid="stMarkdownContainer"] p {
        font-family: 'Poppins', sans-serif !important; font-size: 0.78rem !important;
        line-height: 1.4 !important; margin: 0 !important; padding: 3px 0 3px 0.75rem;
        color: #9AA1AC; transform: none !important;
    }
    [class*="st-key-navradio_"] [data-testid="stRadioOption"]:has(input:checked) [data-testid="stMarkdownContainer"] p {
        color: #FFCB03 !important; font-weight: 700 !important;
    }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
    """, unsafe_allow_html=True)


def _nav_item(clave, icono, nombre, activa, habilitado):
    if activa == clave:
        st.markdown(
            f'<div class="zl-nav-item-active">{icono}&nbsp;&nbsp;{nombre}</div>',
            unsafe_allow_html=True)
    elif habilitado:
        if st.button(f"{icono}  {nombre}", key=f"nav_{clave}"):
            st.session_state["pantalla"] = clave
            st.rerun()
    else:
        st.markdown(
            f'<div class="zl-nav-item">{icono}&nbsp;&nbsp;{nombre}</div>',
            unsafe_allow_html=True)


def _formatear_opcion_arbol(id_p: str, respuestas: dict, id_actual: str | None) -> str:
    """Etiqueta de una pregunta dentro del st.radio del árbol: la pregunta
    actual se muestra sin símbolo (el resaltado ya la distingue vía CSS
    :has(input:checked)); las demás llevan ●/○ coloreado según su estado.
    Si la pregunta ya tiene respuesta guardada, se agrega el nivel elegido
    (0-5) junto al número, ej. "Pregunta 4 (4)"."""
    numero = id_p.split("-")[1]
    nivel  = respuestas.get(id_p, {}).get("nivel")
    label  = f"Pregunta {numero} ({nivel})" if nivel is not None else f"Pregunta {numero}"
    if id_p == id_actual:
        return label
    if id_p in respuestas:
        return f':green[● {label}]'
    return f':gray[○ {label}]'


def _on_navtree_radio_change(radio_key: str, idx_por_id: dict, mod_idx_actual: int):
    id_p_sel = st.session_state.get(radio_key)
    if id_p_sel in idx_por_id:
        st.session_state["modulo_actual_idx"]   = mod_idx_actual
        st.session_state["pregunta_actual_idx"] = idx_por_id[id_p_sel]


def _render_arbol_cuestionario(id_modulo: str, mod_idx_actual: int, preg_idx_actual: int):
    """Árbol expandible Dimensión → Preguntas para el módulo activo del
    cuestionario. Solo se muestra cuando pantalla == 'cuestionario'."""
    respuestas   = st.session_state.get("respuestas", {})
    preguntas_df = get_preguntas(id_modulo)
    dims_df      = get_dimensiones(id_modulo)

    if preguntas_df.empty or dims_df.empty:
        return

    # Orden de dimensiones (únicas, en orden de aparición)
    dims_orden  = []
    dims_nombre = {}
    for _, fila in dims_df.iterrows():
        id_dim     = str(fila["ID Dimensión"]).strip()
        nombre_dim = str(fila["Nombre Dimensión"]).strip()
        if id_dim not in dims_nombre:
            dims_nombre[id_dim] = nombre_dim
            dims_orden.append(id_dim)

    # Preguntas agrupadas por dimensión; el índice i coincide exactamente con
    # pregunta_actual_idx porque get_preguntas() ya está ordenado y reindexado
    # (ver modules/cuestionario.py: preguntas_df.iloc[preg_idx]).
    preguntas_por_dim = {}
    for i, fila in preguntas_df.iterrows():
        id_dim = str(fila["ID Dimensión"]).strip()
        preguntas_por_dim.setdefault(id_dim, []).append((i, fila))

    # Dimensión que contiene la pregunta actual (auto-expandir)
    dim_actual = None
    if 0 <= preg_idx_actual < len(preguntas_df):
        dim_actual = str(preguntas_df.iloc[preg_idx_actual]["ID Dimensión"]).strip()

    nombre_modulo = NOMBRE_MODULO.get(id_modulo, id_modulo)
    st.markdown('<p class="zl-side-nav-label">Navegación del cuestionario</p>',
                unsafe_allow_html=True)
    st.markdown(f'<p class="zl-side-modulo-tag">📋 {nombre_modulo}</p>',
                unsafe_allow_html=True)

    for id_dim in dims_orden:
        preguntas_dim   = preguntas_por_dim.get(id_dim, [])
        total_dim       = len(preguntas_dim)
        respondidas_dim = sum(
            1 for _, fila in preguntas_dim
            if str(fila["ID Pregunta"]).strip() in respuestas
        )
        completa = total_dim > 0 and respondidas_dim == total_dim
        color_conteo = "#A8DC00" if completa else "#9AA1AC"
        es_dim_actual = (id_dim == dim_actual)

        # Dimensión desplegable: botón-toggle propio (no st.expander, cuyo ícono
        # nativo no renderiza en el sidebar) con flechas Unicode simples.
        toggle_key = f"navtree_dim_open_{id_dim}"
        if es_dim_actual:
            st.session_state[toggle_key] = True
        elif toggle_key not in st.session_state:
            st.session_state[toggle_key] = False
        abierto = st.session_state[toggle_key]

        col_dim, col_count = st.columns([4, 1])
        with col_dim:
            with st.container(key=f"navdim_{id_dim}"):
                icono_dim = "▼" if abierto else "▶"
                if st.button(f"{icono_dim}  {dims_nombre[id_dim]}", key=f"toggle_dim_{id_dim}"):
                    st.session_state[toggle_key] = not abierto
                    st.rerun()
        with col_count:
            st.markdown(
                f'<p class="zl-side-dim-count" style="color:{color_conteo};">'
                f'{respondidas_dim}/{total_dim}</p>',
                unsafe_allow_html=True)

        if not abierto or not preguntas_dim:
            continue

        ids_dim       = [str(fila["ID Pregunta"]).strip() for _, fila in preguntas_dim]
        idx_por_id    = {str(fila["ID Pregunta"]).strip(): i for i, fila in preguntas_dim}
        id_por_idx    = {i: id_p for id_p, i in idx_por_id.items()}
        id_actual_dim = id_por_idx.get(preg_idx_actual) if es_dim_actual else None

        radio_key = f"navradio_{id_dim}"
        if st.session_state.get(radio_key) != id_actual_dim:
            st.session_state[radio_key] = id_actual_dim

        st.radio(
            "preguntas", options=ids_dim, key=radio_key,
            label_visibility="collapsed",
            format_func=lambda id_p: _formatear_opcion_arbol(id_p, respuestas, id_actual_dim),
            on_change=_on_navtree_radio_change,
            args=(radio_key, idx_por_id, mod_idx_actual),
        )


def render_sidebar(pantalla_activa: str):
    """Dibuja el sidebar izquierdo fijo. `pantalla_activa` es el valor
    actual de st.session_state["pantalla"]."""
    _sidebar_css()

    # La selección de módulos es parte visual del flujo "Cuestionario".
    activa = "cuestionario" if pantalla_activa == "seleccion_modulos" else pantalla_activa

    empresa      = st.session_state.get("empresa", "")
    responsable  = st.session_state.get("responsable", "")
    modulos_sel  = st.session_state.get("modulos_seleccionados", [])
    mod_idx      = st.session_state.get("modulo_actual_idx", 0)
    diag_listo   = bool(st.session_state.get("diagnostico_guardado"))

    with st.sidebar:
        if LOGO_ZL.exists():
            with st.container(key="zl_side_logo"):
                st.image(str(LOGO_ZL), width=150)

        if responsable or empresa:
            st.markdown(f"""
            <div class="zl-side-user">
                <p class="zl-side-user-nombre">{responsable or '—'}</p>
                <p class="zl-side-user-empresa">{empresa or '—'}</p>
            </div>
            """, unsafe_allow_html=True)

        _nav_item("inicio", "🏠", "Inicio", activa, habilitado=True)
        _nav_item("cuestionario", "📋", "Cuestionario", activa,
                   habilitado=bool(modulos_sel))

        if modulos_sel:
            for i, id_m in enumerate(modulos_sel):
                nombre = NOMBRE_MODULO.get(id_m, id_m)
                if pantalla_activa == "cuestionario" and i == mod_idx:
                    cls, icono = "zl-sub-item-actual", "▶"
                elif i < mod_idx or pantalla_activa == "resultados":
                    cls, icono = "zl-sub-item-hecho", "✓"
                else:
                    cls, icono = "", "○"
                st.markdown(
                    f'<div class="zl-sub-item {cls}">{icono} {nombre}</div>',
                    unsafe_allow_html=True)

        _nav_item("resultados", "📊", "Resultados", activa, habilitado=diag_listo)

        st.markdown('<div class="zl-nav-sep"></div>', unsafe_allow_html=True)

        if pantalla_activa == "cuestionario" and modulos_sel and mod_idx < len(modulos_sel):
            _render_arbol_cuestionario(modulos_sel[mod_idx], mod_idx,
                                        st.session_state.get("pregunta_actual_idx", 0))


def render_content_header(titulo: str):
    """Header superior del área de contenido derecha: nombre de la
    pantalla actual + badge de la empresa."""
    empresa = st.session_state.get("empresa", "")
    badge_html = f'<span class="zl-content-badge">{empresa}</span>' if empresa else ""
    st.markdown(f"""
    <style>
    /* Se ocultan solo el menú, la toolbar y el status widget de Streamlit;
       el <header> se deja visible porque ahí vive el botón para reabrir
       el sidebar si llegara a colapsarse (p.ej. en pantallas angostas). */
    [data-testid="stMainMenu"], [data-testid="stToolbar"],
    [data-testid="stStatusWidget"], footer {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{ background: transparent; }}
    .stApp {{ background-color: #F4F5F7; }}
    .zl-content-header {{
        display: flex; align-items: center; justify-content: space-between;
        padding: 0 0 1.1rem 0; margin: -0.5rem 0 1.25rem 0;
        border-bottom: 1px solid #E5E7EB;
    }}
    .zl-content-titulo {{
        font-family: 'Poppins', sans-serif; font-size: 1.3rem; font-weight: 700;
        color: #003049; margin: 0;
    }}
    .zl-content-badge {{
        background: rgba(0,48,73,0.08); border: 1px solid #003049;
        color: #003049; font-family: 'Poppins', sans-serif; font-size: 0.78rem;
        font-weight: 600; padding: 4px 14px; border-radius: 20px;
    }}
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
    <div class="zl-content-header">
        <p class="zl-content-titulo">{titulo}</p>
        {badge_html}
    </div>
    """, unsafe_allow_html=True)
