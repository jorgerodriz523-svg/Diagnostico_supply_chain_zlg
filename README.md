# 📦 Diagnóstico Supply Chain — Zonalogística

Aplicación web para autodiagnosticar el nivel de madurez de la cadena de
suministro de una empresa. El usuario responde un cuestionario modular
(🏭 Almacenamiento, 🚛 Transporte, 📊 Inventarios, 🗓️ Planeación,
🗺️ Distribución) y la app calcula un score de madurez, genera estrategias
de mejora priorizadas y produce un dashboard, una presentación y una
matriz de priorización descargables.

## 🏗️ Arquitectura

```code
📦 proyecto/
│
├── app.py                     → 🚪 punto de entrada; router de pantallas vía session_state["pantalla"]
│
├── 📁 assets/                → 🎨 logo, plantilla HTML del dashboard e imágenes de referencia
│
├── 📁 config/                → 📑 Excel de parametrización (preguntas, pesos, estrategias)
│
├── 📁 database/              → 🗃️ base de datos SQLite con los diagnósticos guardados 
│
├── 📁modules/                → 🖥️ una pantalla por archivo (UI con Streamlit)
│   ├── layout.py                → 🧭 sidebar de navegación y header de contenido compartidos
│   ├── inicio.py                → 🆔 identificación de la empresa/responsable
│   ├── seleccion_modulos.py     → ✅ elección de módulos a evaluar
│   ├── cuestionario.py          → ❓ Preguntas a responder por cada módulo
│   └── resultados.py            → 📈 scores, estrategias recomendadas y descargas
│
├── 📁utils/                  → ⚙️ lógica de negocio, independiente de la UI
│   ├── loader.py                → 📥 lee la parametrización desde config/*.xlsx
│   ├── scoring.py               → 🧮 calcula scores por dimensión y nivel de madurez
│   └── db.py                    → 🗄️ persistencia en SQLite (database/diagnosticos.db)    
│
├── 📁tests/                  → ✅ pruebas automatizadas (hoy: utils/scoring.py)
│
└── generar_datos.py           → 📤 arma el payload de resultados y genera HTML/PPTX/matriz

```

**🔄 Flujo de pantallas:** `inicio → seleccion_modulos → cuestionario → resultados`,
controlado por `st.session_state["pantalla"]` en `app.py`. Cada módulo del
cuestionario se agrega/quita independientemente sin afectar el motor de scoring.

## 🛠️ Tecnologías

- 🎈 **Streamlit** — interfaz web
- 🐼 **Pandas / openpyxl** — lectura de la parametrización (Excel)
- 📊 **Plotly / Kaleido** — gráficos del dashboard
- 📽️ **python-pptx** — generación de la presentación descargable
- 🗄️ **SQLite** — almacenamiento de diagnósticos y respuestas

## ▶️ Ejecución

```bash
pip install -r requirements.txt
streamlit run app.py
```

## ✅ Tests

`utils/scoring.py` (el cálculo de madurez pregunta → subdimensión →
dimensión → score general) tiene su propia suite en `tests/`, con casos
de ponderación aislados y de regresión contra la parametrización real de
MOD-01.

```bash
pip install -r requirements-dev.txt
pytest tests/
```

## 🧩 Personalización del diagnóstico

Las preguntas, pesos, niveles de madurez y estrategias recomendadas se
definen en `config/Parametrizacion_Almacenamiento_MOD01.xlsx` (una hoja
por módulo/dimensión/pregunta/estrategia). No requieren cambios de código
para actualizarse.
