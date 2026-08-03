"""
app.py
------
Punto de entrada principal de la aplicación Streamlit.
Solo orquesta la navegación entre pantallas usando st.session_state["pantalla"].
Toda la lógica vive en modules/ y utils/.

Ejecutar:
    streamlit run app.py
"""

import streamlit as st
from utils.db import inicializar_bd

# ── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title   = "Diagnóstico Supply Chain · Zonalogística",
    page_icon    = "📦",
    layout       = "wide",
    initial_sidebar_state = "expanded",
)

# ── Inicialización única ──────────────────────────────────────────────────────
if "db_inicializada" not in st.session_state:
    inicializar_bd()
    st.session_state["db_inicializada"] = True

if "pantalla" not in st.session_state:
    st.session_state["pantalla"] = "inicio"

# ── Router de pantallas ───────────────────────────────────────────────────────
pantalla = st.session_state["pantalla"]

if pantalla == "inicio":
    from modules.inicio import render
    render()

elif pantalla == "seleccion_modulos":
    from modules.seleccion_modulos import render
    render()

elif pantalla == "cuestionario":
    from modules.cuestionario import render
    render()

elif pantalla == "resultados":
    from modules.resultados import render
    render()

else:
    st.session_state["pantalla"] = "inicio"
    st.rerun()
