
import streamlit as st
import pandas as pd
import plotly.express as px
import time, os, json
from datetime import datetime
from pathlib import Path
import numpy as np

APP_TITLE = "Plataforma DataOps DANE - Prototipo"
BASE_DIR = Path(__file__).resolve().parent
PUB_DIR = BASE_DIR / "publicaciones"
DATA_DIR = BASE_DIR / "datasets"
ASSETS = BASE_DIR / "assets"

st.set_page_config(page_title="DataOps DANE", page_icon=":bar_chart:", layout="wide")

def local_css(path):
    with open(path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css(str(ASSETS / "styles.css"))

st.markdown(f'''
<div class="header-dane">
  <h1>{APP_TITLE}</h1>
  <div class="subtitle">Carga -> Validacion -> Aprobacion -> Publicacion -> Monitoreo (SLA)</div>
</div>
''', unsafe_allow_html=True)

st.sidebar.title("Menu")
page = st.sidebar.radio(
    "Secciones",
    ["Inicio", "Carga y Validacion", "Aprobacion y Publicacion", "Monitoreo y Alertas", "Descargas"]
)

if "df" not in st.session_state:
    st.session_state.df = None
if "val_result" not in st.session_state:
    st.session_state.val_result = None
if "publicado" not in st.session_state:
    st.session_state.publicado = False
if "ultimo_boletin" not in st.session_state:
    st.session_state.ultimo_boletin = None

def validar_dataset(df: pd.DataFrame) -> dict:
    total = len(df)
    reglas = []
    errores = 0

    claves = ["anio", "mes", "hogar_id"]
    for c in claves:
        nnull = df[c].isna().sum() if c in df.columns else total
        flag = nnull == 0
        reglas.append({"regla": f"Sin nulos en {c}", "cumple": flag, "afectados": int(nnull)})
        errores += 0 if flag else int(nnull)

    if "mes" in df.columns:
        fuera = ((df["mes"] < 1) | (df["mes"] > 12)).sum()
        reglas.append({"regla": "Mes entre 1 y 12", "cumple": fuera == 0, "afectados": int(fuera)})
        errores += int(fuera)
    if "personas" in df.columns:
        fuera = (df["personas"] <= 0).sum()
        reglas.append({"regla": "Personas > 0", "cumple": fuera == 0, "afectados": int(fuera)})
        errores += int(fuera)
    if "ingreso_total" in df.columns:
        fuera = ((df["ingreso_total"].isna()) | (df["ingreso_total"] < 0)).sum()
        reglas.append({"regla": "Ingreso total >= 0 y no nulo", "cumple": fuera == 0, "afectados": int(fuera)})
        errores += int(fuera)

    if "anio" in df.columns and "ingreso_total" in df.columns:
        agg = df.groupby("anio")["ingreso_total"].mean(numeric_only=True)
        if len(agg) >= 2:
            delta = agg.sort_index().pct_change().iloc[-1]
            flag = not (delta < -0.8 or delta > 3.0)
            reglas.append({"regla": "Consistencia interanual (media ingresos)", "cumple": flag, "afectados": 0 if flag else None})
            if not flag:
                errores += 1

    calidad = max(0.0, 100.0 * (1 - (errores / max(1, total))))
    detalle = pd.DataFrame(reglas)
    return {"total": total, "errores": int(errores), "calidad": round(calidad, 2), "detalle": detalle}

def publicar(df: pd.DataFrame, metadata: dict):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_dir = PUB_DIR / f"release_{ts}"
    version_dir.mkdir(parents=True, exist_ok=True)
    data_path = version_dir / "microdatos_publicados.csv"
    meta_path = version_dir / "metadata.json"

    df.to_csv(data_path, index=False)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    html = f'''
    <html>
    <head><meta charset="utf-8"><title>Boletin DANE - {ts}</title></head>
    <body style="font-family: Arial, sans-serif;">
      <h2 style="color:#cc0000;">Boletin DANE - Publicacion {ts}</h2>
      <p>Registros: <b>{metadata.get('registros')}</b> | Calidad: <b>{metadata.get('calidad')}%</b> | Aprobado por: <b>{metadata.get('aprobado_por')}</b></p>
      <p>Descripcion: {metadata.get('descripcion')}</p>
      <hr/>
      <p>Archivos:</p>
      <ul>
        <li>microdatos_publicados.csv</li>
        <li>metadata.json</li>
      </ul>
      <p style="font-size:12px;color:#666;">Este es un boletin de demostracion (prototipo).</p>
    </body>
    </html>
    '''
    with open(version_dir / "boletin.html", "w", encoding="utf-8") as f:
        f.write(html)

    return str(version_dir)

if page == "Inicio":
    st.markdown("""
    <div class="box">
      <h3>Proposito</h3>
      <p>Este prototipo muestra el flujo institucional del DANE para produccion y divulgacion estadistica:
      <b>carga de microdatos -> validacion automatica -> aprobacion digital -> publicacion -> monitoreo (SLA)</b>.
      </p>
      <p>La interfaz replica un portal institucional con estilo DANE (rojo/blanco).</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Como usar")
    st.markdown("""
    1) Ve a <b>Carga y Validacion</b> y sube un CSV de microdatos (puedes usar <code>datasets/encuesta_demo.csv</code>).
    2) Revisa el <b>resultado de validacion</b> y el detalle de reglas.
    3) Continua a <b>Aprobacion y Publicacion</b> para simular la firma/aprobacion y generar un release con boletin HTML.
    4) Explora <b>Monitoreo y Alertas</b> para ver metricas y SLA simulados.
    """, unsafe_allow_html=True)

elif page == "Carga y Validacion":
    st.subheader("Carga de Microdatos")
    uploaded = st.file_uploader("Sube un archivo CSV", type=["csv"])

    if uploaded is None:
        st.info("Tambien puedes probar con el dataset de ejemplo.")
        if st.button("Usar dataset de ejemplo"):
            demo_path = DATA_DIR / "encuesta_demo.csv"
            df = pd.read_csv(demo_path)
            st.session_state.df = df
    else:
        df = pd.read_csv(uploaded)
        st.session_state.df = df

    if st.session_state.df is not None:
        df = st.session_state.df
        st.success(f"Datos cargados ({len(df)} registros).")
        st.dataframe(df.head())

        st.divider()
        st.subheader("Validacion automatica (Reglas de Calidad)")
        with st.spinner("Ejecutando validaciones..."):
            time.sleep(1.0)
            res = validar_dataset(df)
        st.session_state.val_result = res

        c1, c2, c3 = st.columns(3)
        c1.metric("Registros", res["total"])
        c2.metric("Errores (estimados)", res["errores"])
        c3.metric("Calidad (%)", res["calidad"])

        fig = px.pie(values=[res["errores"], max(0, res["total"]-res["errores"])],
                     names=["Errores", "Correctos"],
                     title="Resultado de Validacion")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Detalle de reglas:**")
        st.dataframe(res["detalle"])

elif page == "Aprobacion y Publicacion":
    st.subheader("Aprobacion Digital y Publicacion")
    if st.session_state.df is None or st.session_state.val_result is None:
        st.warning("Primero carga y valida un dataset en la seccion anterior.")
    else:
        res = st.session_state.val_result
        df = st.session_state.df

        st.markdown("**Resumen de calidad:**")
        c1, c2, c3 = st.columns(3)
        c1.metric("Registros", res["total"])
        c2.metric("Errores", res["errores"])
        c3.metric("Calidad (%)", res["calidad"])

        aprobado = res["calidad"] >= 95.0
        if aprobado:
            st.success("Cumple estandar minimo de calidad (>=95%). Elegible para publicacion.")
        else:
            st.error("No cumple el estandar minimo de calidad (95%). Debe corregirse antes de publicar.")

        aprobador = st.text_input("Aprobado por (nombre y cargo)", "Jefe(a) de Produccion Estadistica")
        descripcion = st.text_area("Descripcion del release", "Publicacion de microdatos y series asociadas (prototipo).")

        publicar_btn = st.button("Publicar (generar release y boletin)", disabled=not aprobado)

        if publicar_btn:
            with st.spinner("Generando artefactos de publicacion..."):
                time.sleep(1.2)
                meta = {
                    "fecha_publicacion": datetime.now().isoformat(),
                    "registros": int(res["total"]),
                    "calidad": float(res["calidad"]),
                    "aprobado_por": aprobador,
                    "descripcion": descripcion
                }
                out_dir = publicar(df, meta)
            st.session_state.publicado = True
            st.session_state.ultimo_boletin = out_dir
            st.success(f"Publicacion generada en: {out_dir}")
            st.markdown(f"- Boletin HTML: `{out_dir}/boletin.html`")
            st.markdown(f"- Microdatos: `{out_dir}/microdatos_publicados.csv`")
            st.markdown(f"- Metadatos: `{out_dir}/metadata.json`")

elif page == "Monitoreo y Alertas":
    st.subheader("Tablero Operativo (SLA)")
    up_time = 99.95
    t_resp = round(float(np.random.uniform(1.3, 2.8)), 2)
    # Generar alerta si la última validación tuvo calidad < 95%
    if "val_result" in st.session_state and st.session_state.val_result:
        calidad = st.session_state.val_result["calidad"]
        fallas = 1 if calidad < 95 else 0
    else:
        fallas = 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Disponibilidad", f"{up_time} %", "Objetivo: 99.95%")
    k2.metric("Tiempo prom. respuesta API", f"{t_resp} s", "Objetivo: <= 2 s")
    k3.metric("Alertas activas", int(fallas))

    if fallas:
        st.error("Alerta P1: retraso de publicacion detectado. Equipo 2o nivel notificado (simulado).")
    else:
        st.success("Operacion estable. Sin alertas criticas.")

    st.markdown("---")
    st.markdown("Series de validacion por publicacion (simulacion)")
    df_hist = pd.DataFrame({
        "release": [f"R{i:02d}" for i in range(1, 11)],
        "calidad": np.random.uniform(95, 100, 10).round(2),
        "duracion_min": np.random.uniform(3, 15, 10).round(1)
    })
    fig1 = px.line(df_hist, x="release", y="calidad", title="Calidad (%) por release")
    st.plotly_chart(fig1, use_container_width=True)
    fig2 = px.bar(df_hist, x="release", y="duracion_min", title="Duracion de validacion (min)")
    st.plotly_chart(fig2, use_container_width=True)

elif page == "Descargas":
    st.subheader("Artefactos y descargas")
    st.markdown("Dataset de ejemplo")
    demo_path = DATA_DIR / "encuesta_demo.csv"
    with open(demo_path, "rb") as f:
        st.download_button("Descargar encuesta_demo.csv", data=f, file_name="encuesta_demo.csv")

    st.markdown("---")
    st.markdown("Ultima publicacion generada")
    if st.session_state.ultimo_boletin:
        out_dir = st.session_state.ultimo_boletin
        st.code(out_dir)
        st.info("Abre los archivos desde tu explorador de archivos.")
    else:
        st.info("Aun no se han generado publicaciones en esta sesion.")

st.markdown('<div class="footer">Prototipo academico — No corresponde a sistemas productivos del DANE.</div>', unsafe_allow_html=True)
