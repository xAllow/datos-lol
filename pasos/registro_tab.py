from datetime import date
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import GOOGLE_SHEET_CSV_URL


def parsear_duracion(valor) -> float:
    """La columna Duración siempre viene como un entero (minutos)."""
    if pd.isna(valor):
        return np.nan
    try:
        return float(valor)
    except (ValueError, TypeError):
        return np.nan


def parsear_fecha_mixta(serie: pd.Series) -> pd.Series:
    """
    Parsea fecha por fila, probando formatos conocidos explícitamente.
    Evita el problema de que pandas infiera un único formato para toda la columna.
    """
    formatos_conocidos = [
        "%Y-%m-%dT%H:%M:%S",  # 2026-01-02T20:30:00
        "%Y-%m-%d %H:%M:%S",  # 2026-04-17 13:00:00
        "%d/%m/%Y %H:%M:%S",  # 17/04/2026 18:00:00
        "%Y-%m-%d",  # 2026-01-02 (solo fecha, por si acaso)
        "%d/%m/%Y",  # 17/04/2026 (solo fecha, por si acaso)
    ]

    def parsear_una_fecha(valor: str):
        valor = str(valor).strip()
        for fmt in formatos_conocidos:
            try:
                return pd.to_datetime(valor, format=fmt)
            except (ValueError, TypeError):
                continue
        # Último recurso: dejar que dateutil lo intente adivinar
        return pd.to_datetime(valor, errors="coerce", dayfirst=True)

    return serie.apply(parsear_una_fecha)


@st.cache_data(ttl=300)
def cargar_datos_registro(_firma: str) -> pd.DataFrame:
    df = pd.read_csv(
        GOOGLE_SHEET_CSV_URL,
        usecols=[0, 1],
        header=0,
        engine="python",
        on_bad_lines="skip",
    )

    # Renombramos por POSICIÓN, no por nombre, para evitar problemas de BOM/espacios
    df.columns = ["Fecha", "Duracion"]

    df["Fecha"] = df["Fecha"].astype(str).str.strip()
    df["Fecha"] = parsear_fecha_mixta(df["Fecha"])
    df = df.dropna(subset=["Fecha"])

    df["Duracion_min"] = pd.to_numeric(df["Duracion"], errors="coerce")
    df = df.dropna(subset=["Duracion_min"])

    df["fecha_dia"] = df["Fecha"].dt.normalize()
    df["hora"] = df["Fecha"].dt.hour
    df["dia_semana_en"] = df["Fecha"].dt.day_name()

    return df.sort_values("Fecha").reset_index(drop=True)


def calcular_rachas(df: pd.DataFrame, col_fecha: str = "fecha_dia") -> pd.DataFrame:
    """
    Devuelve un DataFrame con TODAS las rachas (con y sin registro),
    su duración en días, fecha de inicio y fin.
    """
    if df.empty:
        return pd.DataFrame(columns=["tipo", "inicio", "fin", "dias"])

    fecha_min = df[col_fecha].min()
    fecha_max = df[col_fecha].max()
    calendario = pd.date_range(fecha_min, fecha_max, freq="D")

    dias_con_registro = set(df[col_fecha].dt.normalize())
    tiene_registro = pd.Series(
        [1 if d in dias_con_registro else 0 for d in calendario],
        index=calendario,
    )

    # Detectar cambios de racha
    cambio = tiene_registro.diff().fillna(1) != 0
    grupo_id = cambio.cumsum()

    rachas = []
    for gid, grupo in tiene_registro.groupby(grupo_id):
        inicio = grupo.index.min()
        fin = grupo.index.max()
        dias = len(grupo)
        tipo = "Con registro" if grupo.iloc[0] == 1 else "Sin registro"
        rachas.append({"tipo": tipo, "inicio": inicio, "fin": fin, "dias": dias})

    return pd.DataFrame(rachas)


def render_registro_tab() -> None:
    st.header("📋 Mi registro diario")
    st.caption("Estadísticas, rachas y patrones a partir de tu hoja de Google Sheets.")

    if not GOOGLE_SHEET_CSV_URL:
        st.error("❌ Falta configurar `GOOGLE_SHEET_CSV_URL` en el .env")
        return

    try:
        firma = date.today().isoformat()
        df = cargar_datos_registro(firma)
    except Exception as e:
        st.error(f"❌ No se pudo cargar la hoja de cálculo: {e}")
        return

    if df.empty:
        st.warning("No hay registros en la hoja.")
        return

    rachas = calcular_rachas(df)
    rachas_con = rachas[rachas["tipo"] == "Con registro"].sort_values("inicio")
    rachas_sin = rachas[rachas["tipo"] == "Sin registro"].sort_values("inicio")

    # ==========================================
    # MÉTRICAS RESUMEN
    # ==========================================
    total_registros = len(df)
    dias_unicos = df["fecha_dia"].nunique()
    racha_sin_actual = (
        rachas_sin.iloc[-1]["dias"]
        if not rachas_sin.empty and rachas_sin.iloc[-1]["fin"] == rachas["fin"].max()
        else 0
    )
    racha_sin_maxima = int(rachas_sin["dias"].max()) if not rachas_sin.empty else 0
    racha_con_maxima = int(rachas_con["dias"].max()) if not rachas_con.empty else 0
    duracion_media = df["Duracion_min"].mean()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total registros", total_registros)
    col2.metric("Días con registro", dias_unicos)
    col3.metric("Racha sin (máx)", f"{racha_sin_maxima} días")
    col4.metric("Racha con (máx)", f"{racha_con_maxima} días")
    col5.metric(
        "Duración media",
        f"{duracion_media:.1f} min" if not pd.isna(duracion_media) else "N/D",
    )

    st.divider()

    # ==========================================
    # TIMELINE DE RACHAS (Gantt tipo semáforo)
    # ==========================================
    st.subheader("📅 Línea temporal de rachas")

    fig_timeline = go.Figure()
    for _, row in rachas.iterrows():
        color = "#00c853" if row["tipo"] == "Con registro" else "#d50000"
        fig_timeline.add_trace(
            go.Scatter(
                x=[row["inicio"], row["fin"] + pd.Timedelta(days=1)],
                y=[row["tipo"], row["tipo"]],
                mode="lines",
                line=dict(color=color, width=20),
                showlegend=False,
                hovertemplate=f"{row['tipo']}<br>{row['inicio'].date()} → {row['fin'].date()}<br>{row['dias']} días<extra></extra>",
            )
        )
    fig_timeline.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        height=200,
        xaxis_title="Fecha",
        yaxis=dict(title="", categoryorder="array", categoryarray=["Sin registro", "Con registro"]),
    )
    st.plotly_chart(fig_timeline, use_container_width=True)

    st.divider()

    # ==========================================
    # RACHAS SIN REGISTRO: tabla + histograma
    # ==========================================
    col_izq, col_der = st.columns(2)

    with col_izq:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>🔴 Rachas sin registro</h5>", unsafe_allow_html=True)

            if rachas_sin.empty:
                st.info("No hay rachas sin registro.")
            else:
                tabla_sin = rachas_sin[["inicio", "fin", "dias"]].copy()
                tabla_sin["inicio"] = tabla_sin["inicio"].dt.strftime("%d/%m/%Y")
                tabla_sin["fin"] = tabla_sin["fin"].dt.strftime("%d/%m/%Y")
                tabla_sin = tabla_sin.rename(columns={"inicio": "Desde", "fin": "Hasta", "dias": "Días"})
                tabla_sin = tabla_sin.sort_values("Días", ascending=False)
                st.dataframe(tabla_sin, use_container_width=True, hide_index=True, height=300)

    with col_der:
        with st.container(border=True):
            st.markdown(
                "<h5 style='text-align: center;'>Frecuencia de rachas sin registro</h5>",
                unsafe_allow_html=True,
            )

            if rachas_sin.empty:
                st.info("Sin datos.")
            else:
                conteo_dias_sin = rachas_sin["dias"].value_counts().reset_index()
                conteo_dias_sin.columns = ["dias", "veces"]
                conteo_dias_sin = conteo_dias_sin.sort_values("dias")

                fig_hist_sin = px.bar(
                    conteo_dias_sin,
                    x="dias",
                    y="veces",
                    text="veces",
                    labels={"dias": "Días consecutivos sin registro", "veces": "Nº de veces que ocurrió"},
                    color_discrete_sequence=["#d50000"],
                )
                fig_hist_sin.update_traces(textposition="outside")
                fig_hist_sin.update_xaxes(dtick=1)
                fig_hist_sin.update_layout(margin=dict(t=20, b=10, l=10, r=10), height=300)
                st.plotly_chart(fig_hist_sin, use_container_width=True)

    # ==========================================
    # RACHAS CON REGISTRO: tabla + histograma
    # ==========================================
    col_izq2, col_der2 = st.columns(2)

    with col_izq2:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>🟢 Rachas con registro</h5>", unsafe_allow_html=True)

            if rachas_con.empty:
                st.info("No hay rachas con registro.")
            else:
                tabla_con = rachas_con[["inicio", "fin", "dias"]].copy()
                tabla_con["inicio"] = tabla_con["inicio"].dt.strftime("%d/%m/%Y")
                tabla_con["fin"] = tabla_con["fin"].dt.strftime("%d/%m/%Y")
                tabla_con = tabla_con.rename(columns={"inicio": "Desde", "fin": "Hasta", "dias": "Días"})
                tabla_con = tabla_con.sort_values("Días", ascending=False)
                st.dataframe(tabla_con, use_container_width=True, hide_index=True, height=300)

    with col_der2:
        with st.container(border=True):
            st.markdown(
                "<h5 style='text-align: center;'>Frecuencia de rachas con registro</h5>",
                unsafe_allow_html=True,
            )

            if rachas_con.empty:
                st.info("Sin datos.")
            else:
                conteo_dias_con = rachas_con["dias"].value_counts().reset_index()
                conteo_dias_con.columns = ["dias", "veces"]
                conteo_dias_con = conteo_dias_con.sort_values("dias")

                fig_hist_con = px.bar(
                    conteo_dias_con,
                    x="dias",
                    y="veces",
                    text="veces",
                    labels={"dias": "Días consecutivos con registro", "veces": "Nº de veces que ocurrió"},
                    color_discrete_sequence=["#00c853"],
                )
                fig_hist_con.update_traces(textposition="outside")
                fig_hist_con.update_xaxes(dtick=1)
                fig_hist_con.update_layout(margin=dict(t=20, b=10, l=10, r=10), height=300)
                st.plotly_chart(fig_hist_con, use_container_width=True)

    st.divider()

    # ==========================================
    # SERIE TEMPORAL: registros por día
    # ==========================================
    st.subheader("📈 Registros a lo largo del tiempo")

    registros_por_dia = df.groupby("fecha_dia").size().reset_index(name="registros")
    calendario_completo = pd.date_range(df["fecha_dia"].min(), df["fecha_dia"].max(), freq="D")
    registros_por_dia = (
        registros_por_dia.set_index("fecha_dia")
        .reindex(calendario_completo, fill_value=0)
        .reset_index()
        .rename(columns={"index": "fecha_dia"})
    )

    fig_serie = px.bar(
        registros_por_dia,
        x="fecha_dia",
        y="registros",
        labels={"fecha_dia": "Fecha", "registros": "Registros"},
        color_discrete_sequence=["#4f46e5"],
    )
    fig_serie.update_xaxes(rangeslider_visible=True)
    fig_serie.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig_serie, use_container_width=True)

    st.divider()

    # ==========================================
    # HISTOGRAMAS Y DISTRIBUCIONES
    # ==========================================
    col_h1, col_h2 = st.columns(2)

    with col_h1:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Distribución de duración</h5>", unsafe_allow_html=True)
            fig_dur_hist = px.histogram(
                df.dropna(subset=["Duracion_min"]),
                x="Duracion_min",
                nbins=25,
                labels={"Duracion_min": "Duración (min)"},
                color_discrete_sequence=["#8b5cf6"],
            )
            fig_dur_hist.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350, bargap=0.1)
            st.plotly_chart(fig_dur_hist, use_container_width=True)

    with col_h2:
        with st.container(border=True):
            st.markdown(
                "<h5 style='text-align: center;'>Registros por día de la semana</h5>",
                unsafe_allow_html=True,
            )
            orden_dias_en = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
            dias_es = {
                "Monday": "Lunes",
                "Tuesday": "Martes",
                "Wednesday": "Miércoles",
                "Thursday": "Jueves",
                "Friday": "Viernes",
                "Saturday": "Sábado",
                "Sunday": "Domingo",
            }
            conteo_dia_semana = (
                df["dia_semana_en"].value_counts().reindex(orden_dias_en).fillna(0).reset_index()
            )
            conteo_dia_semana.columns = ["dia", "count"]
            conteo_dia_semana["dia_es"] = conteo_dia_semana["dia"].map(dias_es)

            fig_dow = px.bar(
                conteo_dia_semana,
                x="dia_es",
                y="count",
                labels={"dia_es": "Día", "count": "Registros"},
                color="count",
                color_continuous_scale="Purples",
            )
            fig_dow.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350, coloraxis_showscale=False)
            st.plotly_chart(fig_dow, use_container_width=True)

    col_h3, col_h4 = st.columns(2)

    with col_h3:
        with st.container(border=True):
            st.markdown(
                "<h5 style='text-align: center;'>Distribución por hora del día</h5>",
                unsafe_allow_html=True,
            )
            conteo_hora = df["hora"].value_counts().sort_index().reset_index()
            conteo_hora.columns = ["hora", "count"]
            conteo_hora["hora_str"] = conteo_hora["hora"].astype(str)

            fig_hora_dist = px.bar(
                conteo_hora,
                x="hora_str",
                y="count",
                labels={"hora_str": "Hora", "count": "Registros"},
                color="count",
                color_continuous_scale="Oranges",
            )
            fig_hora_dist.update_xaxes(type="category")
            fig_hora_dist.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350, coloraxis_showscale=False)
            st.plotly_chart(fig_hora_dist, use_container_width=True)

    with col_h4:
        with st.container(border=True):
            st.markdown(
                "<h5 style='text-align: center;'>Duración media por día de la semana</h5>",
                unsafe_allow_html=True,
            )
            dur_dia_semana = (
                df.dropna(subset=["Duracion_min"])
                .groupby("dia_semana_en")["Duracion_min"]
                .mean()
                .reindex(orden_dias_en)
                .fillna(0)
                .reset_index()
            )
            dur_dia_semana.columns = ["dia", "duracion"]
            dur_dia_semana["dia_es"] = dur_dia_semana["dia"].map(dias_es)

            fig_dur_dow = px.bar(
                dur_dia_semana,
                x="dia_es",
                y="duracion",
                labels={"dia_es": "Día", "duracion": "Duración media (min)"},
                color="duracion",
                color_continuous_scale="teal",
            )
            fig_dur_dow.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350, coloraxis_showscale=False)
            st.plotly_chart(fig_dur_dow, use_container_width=True)

    st.divider()

    # ==========================================
    # HEATMAP: hora x día de la semana
    # ==========================================
    with st.container(border=True):
        st.markdown(
            "<h5 style='text-align: center;'>Mapa de calor: hora × día de la semana</h5>",
            unsafe_allow_html=True,
        )

        df_heat = df.groupby(["hora", "dia_semana_en"]).size().reset_index(name="count")
        pivot_heat = df_heat.pivot(index="hora", columns="dia_semana_en", values="count")
        pivot_heat = pivot_heat.reindex(columns=orden_dias_en).fillna(0)
        pivot_heat.columns = [dias_es[c] for c in pivot_heat.columns]
        pivot_heat = pivot_heat.sort_index()
        pivot_heat.index = [f"{h:02d}:00" for h in pivot_heat.index]

        fig_heat_registro = px.imshow(
            pivot_heat,
            color_continuous_scale="Purples",
            labels=dict(x="Día", y="Hora", color="Registros"),
            aspect="auto",
        )
        fig_heat_registro.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=450)
        st.plotly_chart(fig_heat_registro, use_container_width=True)

    st.divider()

    # ==========================================
    # EVOLUCIÓN MENSUAL: cantidad + duración media
    # ==========================================
    with st.container(border=True):
        st.markdown("<h5 style='text-align: center;'>Evolución mensual</h5>", unsafe_allow_html=True)

        df["año_mes"] = df["fecha_dia"].dt.to_period("M").astype(str)
        resumen_mensual = df.groupby("año_mes").agg(
            registros=("Fecha", "count"),
            duracion_media=("Duracion_min", "mean"),
        ).reset_index()

        fig_mensual = go.Figure()
        fig_mensual.add_trace(
            go.Bar(
                x=resumen_mensual["año_mes"],
                y=resumen_mensual["registros"],
                name="Registros",
                marker_color="#4f46e5",
                yaxis="y1",
            )
        )
        fig_mensual.add_trace(
            go.Scatter(
                x=resumen_mensual["año_mes"],
                y=resumen_mensual["duracion_media"],
                name="Duración media (min)",
                mode="lines+markers",
                line=dict(color="#f57f17", width=2),
                yaxis="y2",
            )
        )
        fig_mensual.update_layout(
            xaxis=dict(title="Mes", tickangle=-45),
            yaxis=dict(title="Registros", side="left"),
            yaxis2=dict(title="Duración media (min)", overlaying="y", side="right"),
            legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5),
            margin=dict(t=10, b=10, l=10, r=10),
            height=400,
        )
        st.plotly_chart(fig_mensual, use_container_width=True)

    st.divider()

    # ==========================================
    # CALENDARIO ANUAL TIPO GITHUB (heatmap por día)
    # ==========================================
    with st.container(border=True):
        st.markdown(
            "<h5 style='text-align: center;'>Calendario de actividad</h5>", unsafe_allow_html=True
        )

        años_disp = sorted(df["fecha_dia"].dt.year.unique(), reverse=True)
        año_cal = st.selectbox("Año", años_disp, key="año_calendario_registro")

        registros_año = registros_por_dia[registros_por_dia["fecha_dia"].dt.year == año_cal].copy()
        registros_año["semana"] = registros_año["fecha_dia"].dt.isocalendar().week
        registros_año["dia_semana_num"] = registros_año["fecha_dia"].dt.dayofweek

        pivot_calendario = registros_año.pivot_table(
            index="dia_semana_num", columns="semana", values="registros", fill_value=0
        )
        pivot_calendario.index = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"][: len(pivot_calendario)]

        fig_calendario = px.imshow(
            pivot_calendario,
            color_continuous_scale="Greens",
            labels=dict(x="Semana del año", y="", color="Registros"),
            aspect="auto",
        )
        fig_calendario.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=250)
        st.plotly_chart(fig_calendario, use_container_width=True)
