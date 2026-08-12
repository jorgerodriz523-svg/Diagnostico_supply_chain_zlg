"""
modules/seleccion_modulos.py
----------------------------
Pantalla 2: Selección de módulos a evaluar.
Muestra los módulos disponibles; los inactivos aparecen en gris con
etiqueta "Próximamente".
"""

import streamlit as st
from utils.loader import get_modulos, get_preguntas
from utils.db import (
    buscar_borrador_modulo, crear_o_reabrir_diagnostico,
    obtener_respuestas_diagnostico, descartar_diagnostico,
)
from modules.layout import render_sidebar, render_content_header


# Íconos y descripciones cortas para cada módulo
MODULO_META = {
    "SUPPLY_CHAIN": {
        "icono": "🔗",
        "descripcion": "Evaluación integral de toda la cadena de suministro. "
                       "Incluye todos los módulos disponibles: Almacenamiento, "
                       "Transporte, Inventarios, Planeación y Distribución.",
    },
    "MOD-01": {
        "icono": "🏭",
        "descripcion": "Evalúa el nivel de madurez de su centro de distribución: "
                       "recibo, almacenamiento, despacho, control de inventarios y planeación.",
    },
    "MOD-02": {
        "icono": "🚛",
        "descripcion": "Diagnóstico de la gestión de flota, rutas y operaciones de transporte.",
    },
    "MOD-03": {
        "icono": "📦",
        "descripcion": "Evaluación del modelo de gestión y control de inventarios.",
    },
    "MOD-04": {
        "icono": "📊",
        "descripcion": "Evaluación del proceso de S&OP y planeación de la demanda.",
    },
    "MOD-05": {
        "icono": "🗺️",
        "descripcion": "Diagnóstico de la red de distribución y gestión del último kilómetro.",
    },
}


def _primera_posicion_sin_responder(modulos_activos, respuestas_guardadas):
    """
    Recorre los módulos seleccionados en orden y devuelve (modulo_idx,
    pregunta_idx) de la primera pregunta que todavía no tiene respuesta
    guardada. Si todas las preguntas ya están respondidas, devuelve (0, 0).
    """
    for i, id_m in enumerate(modulos_activos):
        ids_preguntas = get_preguntas(id_m)["ID Pregunta"].str.strip().tolist()
        for j, id_p in enumerate(ids_preguntas):
            if id_p not in respuestas_guardadas:
                return i, j
    return 0, 0


def _iniciar_cuestionario(modulos_activos, retomar, borradores_detectados=None):
    """
    Crea o reabre el diagnóstico del cliente actual, reconstruye (si
    corresponde) las respuestas ya guardadas y ubica el cursor en la
    primera pregunta pendiente antes de pasar a la pantalla del
    cuestionario.
    """
    borradores_detectados = borradores_detectados or {}

    if not retomar:
        # El usuario eligió "Comenzar de nuevo": los borradores detectados
        # para los módulos seleccionados quedan descartados (se conservan
        # para trazabilidad, no se borran).
        ids_a_descartar = {info["id_diagnostico"] for info in borradores_detectados.values()}
        for id_diag in ids_a_descartar:
            descartar_diagnostico(id_diag)

    id_diagnostico = crear_o_reabrir_diagnostico(
        empresa=st.session_state.get("empresa", ""),
        responsable=st.session_state.get("responsable", ""),
        sector=st.session_state.get("sector", ""),
        correo=st.session_state.get("correo", ""),
        cargo=st.session_state.get("cargo", ""),
        celular=st.session_state.get("celular", ""),
        pais=st.session_state.get("pais", ""),
        ciudad=st.session_state.get("ciudad", ""),
        modulos_seleccionados=modulos_activos,
    )

    respuestas_guardadas = obtener_respuestas_diagnostico(id_diagnostico) if retomar else {}

    # cuestionario.py recuerda la selección visual del selectbox y el
    # texto de observaciones por separado (session_state["nivel_<id>"] y
    # session_state["obs_<id>"]), para cuando el usuario navega hacia
    # atrás dentro de la misma sesión. Hay que poblarlas también al
    # retomar, o esas preguntas se verían en blanco pese a tener
    # respuesta guardada.
    for id_p, datos in respuestas_guardadas.items():
        st.session_state[f"nivel_{id_p}"] = datos.get("nivel", 0)
        st.session_state[f"obs_{id_p}"]   = datos.get("observacion", "")

    modulo_idx, pregunta_idx = _primera_posicion_sin_responder(modulos_activos, respuestas_guardadas)

    st.session_state["modulos_seleccionados"]     = modulos_activos
    st.session_state["id_diagnostico"]            = id_diagnostico
    st.session_state["respuestas"]                = respuestas_guardadas
    st.session_state["modulo_actual_idx"]         = modulo_idx
    st.session_state["pregunta_actual_idx"]       = pregunta_idx
    st.session_state["oferta_borrador_pendiente"] = False
    st.session_state.pop("borradores_detectados", None)
    st.session_state.pop("modulos_pendientes_confirmar", None)
    st.session_state["pantalla"] = "cuestionario"
    st.rerun()


def render():
    st.markdown("""
    <style>
    .zl-semaforo {
        height: 5px;
        background: linear-gradient(to right, #FF0303 33%, #FFCB03 33% 66%, #A8DC00 66%);
        margin: 0 0 2rem 0;
        border-radius: 3px;
    }
    .zl-page-titulo {
        font-family: 'Poppins', sans-serif;
        font-size: 1.35rem;
        font-weight: 700;
        color: #003049;
        margin-bottom: 0.2rem;
        text-align: center;
    }
    .zl-page-sub {
        font-family: 'Poppins', sans-serif;
        font-size: 0.88rem;
        color: #6B7280;
        text-align: center;
        margin-bottom: 2rem;
    }

    /* Cards de módulos */
    .modulo-card {
        background: #ffffff;
        border: 2px solid #E5E7EB;
        border-radius: 14px;
        padding: 1.4rem 1.5rem;
        margin-bottom: 1rem;
        transition: border-color 0.2s, box-shadow 0.2s;
        cursor: pointer;
    }
    .modulo-card:hover {
        border-color: #003049;
        box-shadow: 0 4px 16px rgba(0,48,73,0.10);
    }
    .modulo-card.seleccionado {
        border-color: #003049;
        background: #EEF3F6;
        box-shadow: 0 4px 16px rgba(0,48,73,0.12);
    }
    .modulo-card.inactivo {
        background: #F9FAFB;
        border-color: #E5E7EB;
        cursor: not-allowed;
        opacity: 0.65;
    }
    .modulo-icono {
        font-size: 1.8rem;
        margin-bottom: 0.4rem;
    }
    .modulo-nombre {
        font-family: 'Poppins', sans-serif;
        font-size: 1rem;
        font-weight: 700;
        color: #003049;
        margin-bottom: 0.3rem;
    }
    .modulo-desc {
        font-family: 'Poppins', sans-serif;
        font-size: 0.82rem;
        color: #6B7280;
        line-height: 1.45;
    }
    .badge-activo {
        display: inline-block;
        background: #DCFCE7;
        color: #15803D;
        font-family: 'Poppins', sans-serif;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 2px 10px;
        border-radius: 20px;
        margin-bottom: 0.5rem;
    }
    .badge-pronto {
        display: inline-block;
        background: #F3F4F6;
        color: #9CA3AF;
        font-family: 'Poppins', sans-serif;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 2px 10px;
        border-radius: 20px;
        margin-bottom: 0.5rem;
    }

    /* Botón principal */
    .stButton > button {
        background: #003049 !important;
        color: #ffffff !important;
        font-family: 'Poppins', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.65rem 2rem !important;
        width: 100% !important;
        margin-top: 0.5rem !important;
    }
    .stButton > button:hover { background: #004d6e !important; }

    /* Botón volver */
    .st-key-btn_volver .stButton > button {
        background: transparent !important;
        color: #6B7280 !important;
        border: 1.5px solid #D1D5DB !important;
        border-radius: 10px !important;
    }
    .st-key-btn_volver .stButton > button:hover {
        background: #F3F4F6 !important;
        color: #003049 !important;
    }

    .zl-error {
        background: #FEF2F2;
        border-left: 4px solid #FF0303;
        border-radius: 8px;
        padding: 0.65rem 1rem;
        font-family: 'Poppins', sans-serif;
        font-size: 0.84rem;
        color: #991B1B;
        margin-top: 0.5rem;
    }

    /* Card especial: Supply Chain (módulo paraguas) */
    .modulo-card.modulo-card-supply-chain {
        border: 3px solid #A8DC00;
    }
    .modulo-card.modulo-card-supply-chain.seleccionado {
        background: #F0F7E6;
        border-color: #A8DC00;
        box-shadow: 0 4px 16px rgba(168,220,0,0.25);
    }
    .badge-supply-chain {
        display: inline-block;
        background: #F0F7E6;
        color: #5C8A00;
        font-family: 'Poppins', sans-serif;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 2px 10px;
        border-radius: 20px;
        margin-bottom: 0.5rem;
    }

    /* Módulos individuales deshabilitados por Supply Chain */
    .modulo-card.deshabilitado-sc {
        opacity: 0.5;
        cursor: default;
    }

    .zl-info-supply {
        background: #F0F7E6;
        border-left: 4px solid #A8DC00;
        border-radius: 8px;
        padding: 0.65rem 1rem;
        font-family: 'Poppins', sans-serif;
        font-size: 0.84rem;
        color: #365314;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    /* Oferta de retomar un módulo con progreso guardado */
    .zl-info-borrador {
        background: #FFFBEB;
        border-left: 4px solid #FFCB03;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-family: 'Poppins', sans-serif;
        font-size: 0.84rem;
        color: #78350F;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }
    .zl-info-borrador ul {
        margin: 0.4rem 0 0.2rem 1.1rem;
        padding: 0;
    }
    .st-key-btn_comenzar_nuevo .stButton > button {
        background: transparent !important;
        color: #6B7280 !important;
        border: 1.5px solid #D1D5DB !important;
    }
    .st-key-btn_comenzar_nuevo .stButton > button:hover {
        background: #F3F4F6 !important;
        color: #003049 !important;
    }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
    """, unsafe_allow_html=True)

    empresa = st.session_state.get("empresa", "")

    # ── Sidebar + header de contenido ────────────────────────────────────────
    render_sidebar("seleccion_modulos")
    render_content_header("Selección de módulos")

    if st.session_state.pop("retomo_diagnostico", False):
        st.markdown(
            f'<div class="zl-info-supply">✓ Recuperamos los datos de '
            f'<b>{empresa}</b>. Ajuste los módulos si lo necesita y continúe.</div>',
            unsafe_allow_html=True)

    st.markdown('<div class="zl-semaforo"></div>', unsafe_allow_html=True)

    st.markdown("""
    <p class="zl-page-titulo">Selección de módulos</p>
    <p class="zl-page-sub">
        Seleccione los módulos que aplican a la operación de su empresa.<br>
        Puede elegir uno o varios; cada módulo se evalúa de forma independiente.
    </p>
    """, unsafe_allow_html=True)

    # ── Cards de módulos ──────────────────────────────────────────────────────
    todos_modulos = get_modulos(solo_activos=False)
    ids_reales_activos = [
        row["ID Módulo"].strip() for _, row in todos_modulos.iterrows()
        if str(row["Activo"]).strip().lower() == "sí"
    ]
    seleccionados = st.session_state.get("modulos_seleccionados", [])

    # ── Card especial: Supply Chain (módulo paraguas) ────────────────────────
    supply_chain_prev = st.session_state.get("supply_chain_activo", False)
    meta_sc = MODULO_META["SUPPLY_CHAIN"]
    css_card_sc = "modulo-card modulo-card-supply-chain" + \
                  (" seleccionado" if supply_chain_prev else "")

    st.markdown(f"""
    <div class="{css_card_sc}">
        <div class="modulo-icono">{meta_sc['icono']}</div>
        <span class="badge-supply-chain">Evaluación completa</span>
        <div class="modulo-nombre">Supply Chain</div>
        <div class="modulo-desc">{meta_sc['descripcion']}</div>
    </div>
    """, unsafe_allow_html=True)

    val_sc = st.checkbox(
        "Incluir Supply Chain",
        value=supply_chain_prev,
        key="cb_supply_chain",
    )

    if val_sc and not supply_chain_prev:
        # Se acaba de activar: sobreescribe la selección con todos los módulos activos
        st.session_state["supply_chain_activo"] = True
        seleccionados = list(ids_reales_activos)
        st.session_state["modulos_seleccionados"] = seleccionados
        for id_m in ids_reales_activos:
            st.session_state[f"cb_{id_m}"] = True
    elif not val_sc and supply_chain_prev:
        # Se acaba de desactivar: todos quedan desmarcados y habilitados
        st.session_state["supply_chain_activo"] = False
        seleccionados = []
        st.session_state["modulos_seleccionados"] = seleccionados
        for id_m in ids_reales_activos:
            st.session_state[f"cb_{id_m}"] = False

    supply_chain_activo = st.session_state.get("supply_chain_activo", False)

    if supply_chain_activo:
        st.markdown(
            '<div class="zl-info-supply">ℹ Al seleccionar Supply Chain se evaluarán '
            'todos los módulos disponibles</div>',
            unsafe_allow_html=True)

    for _, row in todos_modulos.iterrows():
        id_m    = row["ID Módulo"].strip()
        nombre  = row["Nombre Módulo"].strip()
        activo  = str(row["Activo"]).strip().lower() == "sí"
        meta    = MODULO_META.get(id_m, {"icono": "📋", "descripcion": ""})
        checked = id_m in seleccionados
        deshabilitado_sc = activo and supply_chain_activo

        # Renderizamos la card visualmente
        css_card = "modulo-card" + (" seleccionado" if checked else "") + \
                   (" inactivo" if not activo else "") + \
                   (" deshabilitado-sc" if deshabilitado_sc else "")
        badge_html = '<span class="badge-activo">Disponible</span>' \
            if activo else '<span class="badge-pronto">Próximamente</span>'

        st.markdown(f"""
        <div class="{css_card}">
            <div class="modulo-icono">{meta['icono']}</div>
            {badge_html}
            <div class="modulo-nombre">{nombre}</div>
            <div class="modulo-desc">{meta['descripcion']}</div>
        </div>
        """, unsafe_allow_html=True)

        # Checkbox funcional (solo para módulos activos)
        if activo:
            key_cb = f"cb_{id_m}"
            if key_cb not in st.session_state:
                st.session_state[key_cb] = checked
            val = st.checkbox(
                f"Incluir {nombre}",
                key=key_cb,
                disabled=deshabilitado_sc,
            )
            if not deshabilitado_sc:
                if val and id_m not in seleccionados:
                    seleccionados.append(id_m)
                    st.session_state["modulos_seleccionados"] = seleccionados
                elif not val and id_m in seleccionados:
                    seleccionados.remove(id_m)
                    st.session_state["modulos_seleccionados"] = seleccionados

    st.markdown("---")

    # ── Oferta de retomar un módulo con progreso guardado ───────────────────────
    # Se muestra en vez de los botones normales mientras el usuario no haya
    # decidido si continuar donde quedó o comenzar de nuevo.
    if st.session_state.get("oferta_borrador_pendiente"):
        borradores = st.session_state.get("borradores_detectados", {})
        modulos_pendientes = st.session_state.get("modulos_pendientes_confirmar", [])
        nombres_modulos = {
            row["ID Módulo"].strip(): row["Nombre Módulo"].strip()
            for _, row in todos_modulos.iterrows()
        }

        items_html = "".join(
            f"<li>{nombres_modulos.get(id_m, id_m)}: "
            f"{info['respondidas']} de {info['total']} preguntas respondidas</li>"
            for id_m, info in borradores.items()
        )
        st.markdown(f"""
        <div class="zl-info-borrador">
            ℹ Encontramos progreso guardado sin finalizar:
            <ul>{items_html}</ul>
            ¿Desea continuar donde quedó o comenzar de nuevo?
        </div>
        """, unsafe_allow_html=True)

        col_continuar, col_nuevo = st.columns(2)
        with col_continuar:
            if st.button("Continuar donde quedé →"):
                _iniciar_cuestionario(modulos_pendientes, retomar=True,
                                       borradores_detectados=borradores)
        with col_nuevo:
            with st.container(key="btn_comenzar_nuevo"):
                if st.button("Comenzar de nuevo"):
                    _iniciar_cuestionario(modulos_pendientes, retomar=False,
                                           borradores_detectados=borradores)

    else:
        # ── Botones de navegación ────────────────────────────────────────────
        col1, col2 = st.columns([1, 2])
        with col1:
            with st.container(key="btn_volver"):
                if st.button("← Volver"):
                    st.session_state["pantalla"] = "inicio"
                    st.rerun()

        with col2:
            if st.button("Iniciar evaluación →"):
                modulos_activos = [m for m in seleccionados
                                   if m in [r["ID Módulo"].strip()
                                            for _, r in todos_modulos.iterrows()
                                            if str(r["Activo"]).strip().lower() == "sí"]]
                if not modulos_activos:
                    st.markdown(
                        '<div class="zl-error">⚠ Seleccione al menos un módulo para continuar.</div>',
                        unsafe_allow_html=True)
                else:
                    correo  = st.session_state.get("correo", "")
                    empresa = st.session_state.get("empresa", "")
                    borradores = {}
                    for id_m in modulos_activos:
                        total = len(get_preguntas(id_m))
                        info = buscar_borrador_modulo(correo, empresa, id_m, total)
                        if info:
                            borradores[id_m] = info

                    if borradores:
                        st.session_state["oferta_borrador_pendiente"] = True
                        st.session_state["borradores_detectados"] = borradores
                        st.session_state["modulos_pendientes_confirmar"] = modulos_activos
                        st.rerun()
                    else:
                        _iniciar_cuestionario(modulos_activos, retomar=False)
