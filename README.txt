
# Prototipo DataOps DANE (Streamlit)

## Requisitos
Python 3.9+
pip install streamlit pandas plotly

## Ejecucion local
streamlit run app.py

## Estructura
- app.py: aplicacion principal
- assets/styles.css: estilos DANE
- datasets/encuesta_demo.csv: datos de ejemplo
- publicaciones/: releases (CSV, metadatos y boletin HTML)

## Flujo
Carga -> Validacion -> Aprobacion -> Publicacion -> Monitoreo (SLA)
