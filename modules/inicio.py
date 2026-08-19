"""
modules/inicio.py
-----------------
Pantalla 1: Bienvenida e identificación del cliente.
Recoge empresa, responsable y sector antes de iniciar el diagnóstico.
"""

import logging
import re
import streamlit as st
from pathlib import Path

from modules.layout import render_sidebar, render_content_header
from utils.db import (
    buscar_diagnostico_en_progreso,
    buscar_diagnostico_completado,
    obtener_respuestas_diagnostico,
)

logger = logging.getLogger(__name__)

LOGO_ZL = Path(__file__).parent.parent / "assets" / "logo_zonalogistica.png"

# Sectores económicos para el selector (clasificación ISIC Rev. 4 de la ONU)
SECTORES = [
    "Seleccione un sector...",
    # ── Sector primario ──────────────────────────────
    "Agricultura, ganadería y silvicultura",
    "Pesca y acuicultura",
    "Explotación de minas y canteras",
    # ── Sector secundario ────────────────────────────
    "Industria manufacturera — Alimentos y bebidas",
    "Industria manufacturera — Textil y confección",
    "Industria manufacturera — Madera y papel",
    "Industria manufacturera — Química y farmacéutica",
    "Industria manufacturera — Plástico y caucho",
    "Industria manufacturera — Productos minerales no metálicos",
    "Industria manufacturera — Metalurgia y productos metálicos",
    "Industria manufacturera — Maquinaria y equipo",
    "Industria manufacturera — Electrónica y tecnología",
    "Industria manufacturera — Vehículos y transporte",
    "Industria manufacturera — Otras manufacturas",
    "Suministro de electricidad, gas y vapor",
    "Suministro de agua y gestión de residuos",
    "Construcción",
    # ── Sector terciario / Servicios ─────────────────
    "Comercio al por mayor",
    "Comercio al por menor",
    "Transporte terrestre y por tubería",
    "Transporte marítimo y fluvial",
    "Transporte aéreo",
    "Almacenamiento y actividades auxiliares de transporte",
    "Correo y mensajería",
    "Alojamiento y servicios de comida",
    "Información y comunicaciones — Telecomunicaciones",
    "Información y comunicaciones — Tecnología y software",
    "Información y comunicaciones — Medios y contenido digital",
    "Actividades financieras y de seguros",
    "Actividades inmobiliarias",
    "Actividades jurídicas y contables",
    "Consultoría de gestión y administración empresarial",
    "Arquitectura, ingeniería y actividades técnicas",
    "Investigación y desarrollo científico",
    "Publicidad y estudios de mercado",
    "Actividades de empleo y recursos humanos",
    "Educación",
    "Salud humana y atención médica",
    "Atención veterinaria",
    "Actividades artísticas y de entretenimiento",
    "Deporte y recreación",
    "Actividades de asociaciones y organizaciones",
    "Administración pública y defensa",
    "Organizaciones y organismos internacionales",
    "Otro",
]

# Países para el selector (todos los países reconocidos por la ONU, por región)
PAISES = [
    "Seleccione un país...",
    "── Latinoamérica y el Caribe ──",
    "Argentina", "Bolivia", "Brasil", "Chile", "Colombia",
    "Costa Rica", "Cuba", "Ecuador", "El Salvador", "Guatemala",
    "Haití", "Honduras", "Jamaica", "México", "Nicaragua",
    "Panamá", "Paraguay", "Perú", "República Dominicana",
    "Trinidad y Tobago", "Uruguay", "Venezuela",
    "Antigua y Barbuda", "Bahamas", "Barbados", "Belice",
    "Dominica", "Granada", "Guyana", "San Cristóbal y Nieves",
    "San Vicente y las Granadinas", "Santa Lucía", "Surinam",
    "── América del Norte ──",
    "Canadá", "Estados Unidos", "México",
    "── Europa ──",
    "Albania", "Alemania", "Andorra", "Austria", "Bélgica",
    "Bielorrusia", "Bosnia y Herzegovina", "Bulgaria", "Chipre",
    "Croacia", "Dinamarca", "Eslovaquia", "Eslovenia", "España",
    "Estonia", "Finlandia", "Francia", "Grecia", "Hungría",
    "Irlanda", "Islandia", "Italia", "Kazajistán", "Kosovo",
    "Letonia", "Liechtenstein", "Lituania", "Luxemburgo",
    "Macedonia del Norte", "Malta", "Moldavia", "Mónaco",
    "Montenegro", "Noruega", "Países Bajos", "Polonia",
    "Portugal", "Reino Unido", "República Checa", "Rumania",
    "Rusia", "San Marino", "Serbia", "Suecia", "Suiza",
    "Turquía", "Ucrania", "Vaticano",
    "── Asia ──",
    "Afganistán", "Armenia", "Azerbaiyán", "Bangladés", "Bután",
    "Brunéi", "Camboya", "China", "Corea del Norte",
    "Corea del Sur", "Filipinas", "Georgia", "India", "Indonesia",
    "Japón", "Kirguistán", "Laos", "Malasia", "Maldivas",
    "Mongolia", "Myanmar", "Nepal", "Pakistán", "Singapur",
    "Sri Lanka", "Tailandia", "Taiwán", "Tayikistán",
    "Timor Oriental", "Turkmenistán", "Uzbekistán", "Vietnam",
    "── Oriente Medio ──",
    "Arabia Saudita", "Bahréin", "Emiratos Árabes Unidos",
    "Irak", "Irán", "Israel", "Jordania", "Kuwait", "Líbano",
    "Omán", "Palestina", "Qatar", "Siria", "Yemen",
    "── África ──",
    "Algeria", "Angola", "Benín", "Botsuana", "Burkina Faso",
    "Burundi", "Cabo Verde", "Camerún", "Chad",
    "Comoras", "Congo", "Costa de Marfil", "Djibouti",
    "Egipto", "Eritrea", "Etiopía", "Gabón", "Gambia", "Ghana",
    "Guinea", "Guinea Ecuatorial", "Guinea-Bisáu", "Kenia",
    "Lesoto", "Liberia", "Libia", "Madagascar", "Malaui",
    "Malí", "Marruecos", "Mauricio", "Mauritania", "Mozambique",
    "Namibia", "Níger", "Nigeria", "República Centroafricana",
    "República del Congo", "República Democrática del Congo",
    "Ruanda", "Santo Tomé y Príncipe", "Senegal", "Sierra Leona",
    "Somalia", "Sudáfrica", "Sudán", "Sudán del Sur", "Suazilandia",
    "Tanzania", "Togo", "Túnez", "Uganda", "Yibuti",
    "Zambia", "Zimbabue",
    "── Oceanía ──",
    "Australia", "Fiyi", "Islas Marshall", "Islas Salomón",
    "Kiribati", "Micronesia", "Nauru", "Nueva Zelanda", "Palaos",
    "Papúa Nueva Guinea", "Samoa", "Tonga", "Tuvalu", "Vanuatu",
    "Otro",
]

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def render():
    # ── CSS de la pantalla ────────────────────────────────────────────────────
    st.markdown("""
    <style>
    /* Franja semáforo */
    .zl-semaforo {
        height: 5px;
        background: linear-gradient(to right, #FF0303 33%, #FFCB03 33% 66%, #A8DC00 66%);
        margin: 0 0 2rem 0;
        border-radius: 3px;
    }

    /* Card central */
    .zl-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 2.5rem 2.5rem 2rem 2.5rem;
        box-shadow: 0 2px 8px rgba(0,48,73,0.08), 0 0 0 1px rgba(0,48,73,0.06);
        max-width: 620px;
        margin: 0 auto;
    }
    .zl-card-titulo {
        font-family: 'Poppins', sans-serif;
        font-size: 1.4rem;
        font-weight: 700;
        color: #003049;
        margin-bottom: 0.25rem;
    }
    .zl-card-subtitulo {
        font-family: 'Poppins', sans-serif;
        font-size: 0.88rem;
        color: #6B7280;
        margin-bottom: 1.75rem;
    }
    .zl-divider {
        height: 1px;
        background: #E5E7EB;
        margin: 1.5rem 0;
    }
    .zl-label {
        font-family: 'Poppins', sans-serif;
        font-size: 0.82rem;
        font-weight: 600;
        color: #003049;
        margin-bottom: 0.25rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .zl-nota {
        font-family: 'Poppins', sans-serif;
        font-size: 0.78rem;
        color: #9AA1AC;
        margin-top: 1.5rem;
        text-align: center;
    }

    /* Inputs */
    .stTextInput input {
        border: 1.5px solid #D1D5DB !important;
        border-radius: 8px !important;
        font-family: 'Poppins', sans-serif !important;
        font-size: 0.92rem !important;
        color: #003049 !important;
        padding: 0.55rem 0.85rem !important;
    }
    .stTextInput input:focus {
        border-color: #003049 !important;
        box-shadow: 0 0 0 3px rgba(0,48,73,0.12) !important;
    }
    .stSelectbox > div > div {
        border: 1.5px solid #D1D5DB !important;
        border-radius: 8px !important;
        font-family: 'Poppins', sans-serif !important;
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
        transition: background 0.2s !important;
    }
    .stButton > button:hover {
        background: #004d6e !important;
    }

    /* Mensajes de error */
    .zl-error {
        background: #FEF2F2;
        border: 1px solid #FECACA;
        border-left: 4px solid #FF0303;
        border-radius: 8px;
        padding: 0.65rem 1rem;
        font-family: 'Poppins', sans-serif;
        font-size: 0.84rem;
        color: #991B1B;
        margin-top: 1rem;
    }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
    """, unsafe_allow_html=True)

    # ── Sidebar + header de contenido ────────────────────────────────────────
    render_sidebar("inicio")
    render_content_header("Inicio")

    st.markdown('<div class="zl-semaforo"></div>', unsafe_allow_html=True)

    # ── Card principal ─────────────────────────────────────────────────────────
    st.markdown("""
    <p class="zl-card-titulo">Bienvenido al diagnóstico</p>
    <p class="zl-card-subtitulo">
        Complete los datos de su organización para comenzar. La evaluación toma
        entre 10 y 20 minutos dependiendo de los módulos seleccionados.
    </p>
    """, unsafe_allow_html=True)

    with st.expander("¿Ya iniciaste un diagnóstico? Retómalo aquí", expanded=False):
        st.markdown('<p class="zl-label">Correo electrónico</p>', unsafe_allow_html=True)
        correo_retomar = st.text_input(
            "correo_retomar", label_visibility="collapsed",
            placeholder="Ej: nombre@empresa.com",
            key="input_correo_retomar",
        )
        st.markdown('<p class="zl-label">Nombre de la empresa</p>', unsafe_allow_html=True)
        empresa_retomar = st.text_input(
            "empresa_retomar", label_visibility="collapsed",
            placeholder="Ej: Empresa S.A.",
            key="input_empresa_retomar",
        )

        if st.button("Buscar mi diagnóstico →", key="btn_buscar_retomar"):
            errores_retomar = []
            if not correo_retomar.strip():
                errores_retomar.append("Ingrese el correo con el que inició el diagnóstico.")
            elif not EMAIL_REGEX.match(correo_retomar.strip()):
                errores_retomar.append("El correo electrónico no tiene un formato válido.")
            if not empresa_retomar.strip():
                errores_retomar.append("Ingrese el nombre de la empresa.")

            if errores_retomar:
                for e in errores_retomar:
                    st.markdown(f'<div class="zl-error">⚠ {e}</div>', unsafe_allow_html=True)
            else:
                hubo_error_conexion = False
                try:
                    encontrado = buscar_diagnostico_en_progreso(
                        correo_retomar.strip(), empresa_retomar.strip())
                except Exception:
                    logger.exception(
                        "Error buscando diagnóstico en progreso (correo=%s, empresa=%s)",
                        correo_retomar.strip(), empresa_retomar.strip())
                    encontrado = None
                    hubo_error_conexion = True

                if hubo_error_conexion:
                    st.markdown(
                        '<div class="zl-error">⚠ No pudimos conectar con la base de '
                        'datos. Intente de nuevo o complete el formulario completo.</div>',
                        unsafe_allow_html=True)
                elif encontrado:
                    st.session_state["empresa"]     = encontrado["empresa"]
                    st.session_state["sector"]      = encontrado["sector"] or ""
                    st.session_state["responsable"] = encontrado["responsable"]
                    st.session_state["cargo"]       = encontrado["cargo"] or ""
                    st.session_state["celular"]     = encontrado["celular"] or ""
                    st.session_state["correo"]      = encontrado["correo"]
                    st.session_state["pais"]        = encontrado["pais"] or ""
                    st.session_state["ciudad"]      = encontrado["ciudad"] or ""
                    st.session_state["modulos_seleccionados"] = encontrado["modulos_aplicados"]
                    st.session_state["retomo_diagnostico"] = True
                    st.session_state["pantalla"] = "seleccion_modulos"
                    st.rerun()
                else:
                    st.info(
                        "No encontramos un diagnóstico en progreso con esos datos. "
                        "Verifique que el correo y el nombre de la empresa estén "
                        "escritos igual que la primera vez, o complete el formulario "
                        "completo más abajo para comenzar uno nuevo.")

    with st.expander("¿Ya finalizaste un diagnóstico? Descarga tus resultados aquí", expanded=False):
        st.markdown('<p class="zl-label">Correo electrónico</p>', unsafe_allow_html=True)
        correo_resultados = st.text_input(
            "correo_resultados", label_visibility="collapsed",
            placeholder="Ej: nombre@empresa.com",
            key="input_correo_resultados",
        )
        st.markdown('<p class="zl-label">Nombre de la empresa</p>', unsafe_allow_html=True)
        empresa_resultados = st.text_input(
            "empresa_resultados", label_visibility="collapsed",
            placeholder="Ej: Empresa S.A.",
            key="input_empresa_resultados",
        )

        if st.button("Ver mis resultados →", key="btn_buscar_resultados"):
            errores_resultados = []
            if not correo_resultados.strip():
                errores_resultados.append("Ingrese el correo con el que hizo el diagnóstico.")
            elif not EMAIL_REGEX.match(correo_resultados.strip()):
                errores_resultados.append("El correo electrónico no tiene un formato válido.")
            if not empresa_resultados.strip():
                errores_resultados.append("Ingrese el nombre de la empresa.")

            if errores_resultados:
                for e in errores_resultados:
                    st.markdown(f'<div class="zl-error">⚠ {e}</div>', unsafe_allow_html=True)
            else:
                hubo_error_conexion = False
                try:
                    encontrado = buscar_diagnostico_completado(
                        correo_resultados.strip(), empresa_resultados.strip())
                except Exception:
                    logger.exception(
                        "Error buscando diagnóstico completado (correo=%s, empresa=%s)",
                        correo_resultados.strip(), empresa_resultados.strip())
                    encontrado = None
                    hubo_error_conexion = True

                if hubo_error_conexion:
                    st.markdown(
                        '<div class="zl-error">⚠ No pudimos conectar con la base de '
                        'datos. Intente de nuevo más tarde.</div>',
                        unsafe_allow_html=True)
                elif encontrado:
                    st.session_state["empresa"]     = encontrado["empresa"]
                    st.session_state["sector"]      = encontrado["sector"] or ""
                    st.session_state["responsable"] = encontrado["responsable"]
                    st.session_state["cargo"]       = encontrado["cargo"] or ""
                    st.session_state["celular"]     = encontrado["celular"] or ""
                    st.session_state["correo"]      = encontrado["correo"]
                    st.session_state["pais"]        = encontrado["pais"] or ""
                    st.session_state["ciudad"]      = encontrado["ciudad"] or ""
                    st.session_state["modulos_seleccionados"] = encontrado["modulos_aplicados"]
                    st.session_state["id_diagnostico"] = encontrado["id_diagnostico"]
                    st.session_state["respuestas"] = obtener_respuestas_diagnostico(
                        encontrado["id_diagnostico"])
                    st.session_state["diagnostico_guardado"] = True
                    st.session_state["pantalla"] = "resultados"
                    st.rerun()
                else:
                    st.info(
                        "No encontramos un diagnóstico finalizado con esos datos. "
                        "Verifique que el correo y el nombre de la empresa estén "
                        "escritos igual que cuando lo completó.")

    st.markdown('<p class="zl-label">Nombre de la empresa</p>', unsafe_allow_html=True)
    empresa = st.text_input(
        "empresa", label_visibility="collapsed",
        placeholder="Ej: Empresa S.A.",
        value=st.session_state.get("empresa", ""),
    )

    st.markdown('<p class="zl-label">Sector económico</p>', unsafe_allow_html=True)
    sector_idx = SECTORES.index(st.session_state.get("sector", SECTORES[0])) \
        if st.session_state.get("sector") in SECTORES else 0
    sector = st.selectbox(
        "sector", SECTORES, index=sector_idx,
        label_visibility="collapsed",
    )

    st.markdown('<p class="zl-label">Nombre del responsable</p>', unsafe_allow_html=True)
    responsable = st.text_input(
        "responsable", label_visibility="collapsed",
        placeholder="Nombre completo de quien responde el diagnóstico",
        value=st.session_state.get("responsable", ""),
    )

    st.markdown('<p class="zl-label">Cargo</p>', unsafe_allow_html=True)
    cargo = st.text_input(
        "cargo", label_visibility="collapsed",
        placeholder="Ej: Gerente de Logística",
        value=st.session_state.get("cargo", ""),
    )

    st.markdown('<p class="zl-label">Número de celular</p>', unsafe_allow_html=True)
    celular = st.text_input(
        "celular", label_visibility="collapsed",
        placeholder="Ej: 3001234567",
        value=st.session_state.get("celular", ""),
    )

    st.markdown('<p class="zl-label">Correo electrónico</p>', unsafe_allow_html=True)
    correo = st.text_input(
        "correo", label_visibility="collapsed",
        placeholder="Ej: nombre@empresa.com",
        value=st.session_state.get("correo", ""),
    )

    st.markdown('<p class="zl-label">País</p>', unsafe_allow_html=True)
    pais_idx = PAISES.index(st.session_state.get("pais", PAISES[0])) \
        if st.session_state.get("pais") in PAISES else 0
    pais = st.selectbox(
        "pais", PAISES, index=pais_idx,
        label_visibility="collapsed",
    )

    st.markdown('<p class="zl-label">Ciudad</p>', unsafe_allow_html=True)
    ciudad = st.text_input(
        "ciudad", label_visibility="collapsed",
        placeholder="Ej: Medellín",
        value=st.session_state.get("ciudad", ""),
    )

    st.markdown('<div class="zl-divider"></div>', unsafe_allow_html=True)

    # ── Validación y avance ───────────────────────────────────────────────────
    if st.button("Comenzar diagnóstico →"):
        errores = []
        if not empresa.strip():
            errores.append("El nombre de la empresa es obligatorio.")
        if sector == SECTORES[0]:
            errores.append("Seleccione un sector económico.")
        if not responsable.strip():
            errores.append("El nombre del responsable es obligatorio.")
        if not cargo.strip():
            errores.append("El cargo es obligatorio.")
        if not celular.strip():
            errores.append("El número de celular es obligatorio.")
        elif not (celular.strip().isdigit() and len(celular.strip()) >= 7):
            errores.append("El número de celular debe contener solo dígitos y mínimo 7 caracteres.")
        if not correo.strip():
            errores.append("El correo electrónico es obligatorio.")
        elif not EMAIL_REGEX.match(correo.strip()):
            errores.append("El correo electrónico no tiene un formato válido.")
        if pais == PAISES[0] or pais.startswith("──"):
            errores.append("Seleccione un país válido.")
        if not ciudad.strip():
            errores.append("La ciudad es obligatoria.")

        if errores:
            for e in errores:
                st.markdown(f'<div class="zl-error">⚠ {e}</div>',
                            unsafe_allow_html=True)
        else:
            st.session_state["empresa"]     = empresa.strip()
            st.session_state["sector"]      = sector
            st.session_state["responsable"] = responsable.strip()
            st.session_state["cargo"]       = cargo.strip()
            st.session_state["celular"]     = celular.strip()
            st.session_state["correo"]      = correo.strip()
            st.session_state["pais"]        = pais
            st.session_state["ciudad"]      = ciudad.strip()
            st.session_state["pantalla"]    = "seleccion_modulos"
            st.rerun()

    st.markdown("""
    <p class="zl-nota">
        Los datos ingresados son confidenciales y se usan únicamente
        para generar su informe de diagnóstico.
    </p>
    """, unsafe_allow_html=True)


