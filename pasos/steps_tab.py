from datetime import date
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import (
    obtener_coleccion,
    STEPS_COLLECTION_NAME,
    normalize_day_series,
    MESES_ES,
)

DIAS_ES = {
    "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
    "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo",
}
ORDEN_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
ORDEN_DIAS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def calcular_rachas_meta(df: pd.DataFrame, meta: int) -> pd.DataFrame:
    """Rachas de días consecutivos cumpliendo (o no) la meta diaria."""
    if df.empty:
        return pd.DataFrame(columns=["cumple", "inicio", "fin", "dias"])

    serie = (df.sort_values("fecha")["pasos_totales"] >= meta).astype(int)
    fechas = df.sort_values("fecha")["fecha"].reset_index(drop=True)
    serie = serie.reset_index(drop=True)

    cambio = serie.diff().fillna(1) != 0
    grupo_id = cambio.cumsum()

    rachas = []
    for gid, idxs in pd.Series(range(len(serie))).groupby(grupo_id):
        inicio = fechas.iloc[idxs.iloc[0]]
        fin = fechas.iloc[idxs.iloc[-1]]
        dias = len(idxs)
        cumple = bool(serie.iloc[idxs.iloc[0]])
        rachas.append({"cumple": cumple, "inicio": inicio, "fin": fin, "dias": dias})

    return pd.DataFrame(rachas)


def render_steps_tab() -> None:
    st.header("🚶 Pasos")
    st.caption("Histórico de pasos y tendencia diaria desde 2025.")

    def firma_datos() -> tuple:
        try:
            client, collection = obtener_coleccion(STEPS_COLLECTION_NAME)
            total = collection.count_documents({})
            ultimo = collection.find_one({}, {"_id": 0, "fecha": 1, "pasos": 1}, sort=[("fecha", -1)])
            client.close()
            return ("steps", total, ultimo)
        except Exception:
            return ("steps-error",)

    @st.cache_data(ttl=300)
    def cargar_datos_pasos(_firma: tuple):
        client, collection = obtener_coleccion(STEPS_COLLECTION_NAME)
        documentos = list(collection.find({}, {"_id": 0}).sort("fecha", 1))
        client.close()

        df = pd.DataFrame(documentos)
        if df.empty:
            return df, {"dias_rellenados": 0, "limite_inf": 0, "limite_sup": 0}

        if "pasos_totales" not in df.columns and "pasos" in df.columns:
            df = df.rename(columns={"pasos": "pasos_totales"})

        if "fecha" not in df.columns:
            return pd.DataFrame(), {"dias_rellenados": 0, "limite_inf": 0, "limite_sup": 0}

        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df = df[df["fecha"] >= "2025-01-01"]
        df = normalize_day_series(df, "fecha", "pasos_totales")

        mascara_ceros = df["pasos_totales"] == 0
        total_ceros = int(mascara_ceros.sum())
        metricas_imputacion = {"dias_rellenados": total_ceros, "limite_inf": 0, "limite_sup": 0}

        if total_ceros > 0:
            dias_reales = df[df["pasos_totales"] > 0]["pasos_totales"]
            if not dias_reales.empty:
                limite_inferior = int(dias_reales.quantile(0.05))
                limite_superior = int(dias_reales.quantile(0.15))
                if limite_inferior >= limite_superior:
                    limite_superior = limite_inferior + 150
            else:
                limite_inferior, limite_superior = 200, 500

            metricas_imputacion["limite_inf"] = limite_inferior
            metricas_imputacion["limite_sup"] = limite_superior
            df.loc[mascara_ceros, "pasos_totales"] = np.random.randint(
                low=limite_inferior,
                high=limite_superior,
                size=total_ceros,
            )

        df["año"] = df["fecha"].dt.year
        df["mes_num"] = df["fecha"].dt.month
        df["año_mes"] = df["fecha"].dt.to_period("M").astype(str)
        df["dia_str"] = df["fecha"].dt.strftime("%d")
        df["dia_semana_en"] = df["fecha"].dt.day_name()
        df["dia_semana"] = df["dia_semana_en"].map(DIAS_ES)
        df["semana_iso"] = df["fecha"].dt.isocalendar().week
        df["media_movil_7"] = df["pasos_totales"].rolling(7, min_periods=1).mean()
        df["media_movil_30"] = df["pasos_totales"].rolling(30, min_periods=1).mean()

        return df, metricas_imputacion

    try:
        df, metricas = cargar_datos_pasos(firma_datos())
    except Exception as e:
        st.error(f"❌ No se pudieron cargar los datos de pasos: {e}")
        return

    if df.empty:
        st.warning("⚠️ No se encontraron datos de pasos a partir del 1 de enero de 2025.")
        return

    # ==========================================
    # FILTROS — reorganizados en una barra clara
    # ==========================================
    with st.container(border=True):
        f_col1, f_col2, f_col3, f_col4 = st.columns([1, 1, 1.4, 1])

        años_disponibles = ["Todos"] + sorted(df["año"].unique(), reverse=True)
        año_actual = date.today().year
        indice_anio_actual = años_disponibles.index(año_actual) if año_actual in años_disponibles else 0

        with f_col1:
            año_seleccionado = st.selectbox("Año", años_disponibles, index=indice_anio_actual)

        df_filtrado_año = df if año_seleccionado == "Todos" else df[df["año"] == año_seleccionado]

        meses_disponibles = ["Todos"] + sorted(df_filtrado_año["mes_num"].unique())
        mes_actual = date.today().month
        indice_mes_actual = meses_disponibles.index(mes_actual) if mes_actual in meses_disponibles else 0

        with f_col2:
            mes_seleccionado_num = st.selectbox(
                "Mes",
                options=meses_disponibles,
                index=indice_mes_actual,
                format_func=lambda x: "Todos" if x == "Todos" else MESES_ES[x],
            )

        with f_col3:
            meta_pasos = st.slider("Meta diaria", min_value=3000, max_value=20000, value=10000, step=500)

        with f_col4:
            mostrar_media_movil = st.selectbox("Media móvil", ["Ninguna", "7 días", "30 días"], index=1)

        st.caption(f"Objetivo actual: {meta_pasos:,} pasos por día")

        with st.expander("🔍 Auditoría de imputación de días vacíos"):
            st.markdown(f"**Días vacíos rellenados:** {metricas['dias_rellenados']}")
            if metricas["dias_rellenados"] > 0:
                st.markdown(f"**Percentil 5 (suelo):** {metricas['limite_inf']} pasos")
                st.markdown(f"**Percentil 15 (techo):** {metricas['limite_sup']} pasos")

    if mes_seleccionado_num == "Todos":
        df_mes_especifico = df_filtrado_año.sort_values("fecha")
        nombre_mes = "todo el año" if año_seleccionado != "Todos" else "todo el periodo"
    else:
        df_mes_especifico = df_filtrado_año[df_filtrado_año["mes_num"] == mes_seleccionado_num].sort_values("fecha")
        nombre_mes = MESES_ES[mes_seleccionado_num]

    # ==========================================
    # RESUMEN HISTÓRICO
    # ==========================================
    st.divider()
    st.header("🌍 Resumen histórico")

    dia_record = df.loc[df["pasos_totales"].idxmax()]
    racha_actual_meta = 0
    df_ordenado = df.sort_values("fecha")
    for pasos in reversed(df_ordenado["pasos_totales"].tolist()):
        if pasos >= meta_pasos:
            racha_actual_meta += 1
        else:
            break

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Días analizados", f"{len(df)} días")
    col2.metric("Promedio diario", f"{int(df['pasos_totales'].mean()):,} pasos")
    col3.metric("Récord absoluto", f"{int(df['pasos_totales'].max()):,} pasos", help=f"{dia_record['fecha'].strftime('%d/%m/%Y')}")
    col4.metric("Pasos acumulados", f"{int(df['pasos_totales'].sum()):,}")
    col5.metric("Racha meta (actual)", f"{racha_actual_meta} días")

    st.subheader("Línea de tiempo")
    fig_linea = go.Figure()
    fig_linea.add_trace(go.Bar(
        x=df["fecha"], y=df["pasos_totales"], name="Pasos diarios",
        marker_color="#c7d2fe", opacity=0.7,
    ))
    if mostrar_media_movil == "7 días":
        fig_linea.add_trace(go.Scatter(
            x=df["fecha"], y=df["media_movil_7"], name="Media móvil (7 días)",
            line=dict(color="#4f46e5", width=2),
        ))
    elif mostrar_media_movil == "30 días":
        fig_linea.add_trace(go.Scatter(
            x=df["fecha"], y=df["media_movil_30"], name="Media móvil (30 días)",
            line=dict(color="#4f46e5", width=2),
        ))
    fig_linea.add_hline(y=meta_pasos, line_dash="dot", line_color="#10b981", annotation_text="Meta")
    fig_linea.update_xaxes(rangeslider_visible=True)
    fig_linea.update_layout(hovermode="x unified", legend=dict(orientation="h", y=-0.2), height=400)
    st.plotly_chart(fig_linea, use_container_width=True)

    st.divider()

    # ==========================================
    # DETALLE DEL PERIODO SELECCIONADO
    # ==========================================
    st.header(f"🔍 Detalle de {nombre_mes}" + (f" {año_seleccionado}" if año_seleccionado != "Todos" else ""))

    if df_mes_especifico.empty:
        st.warning("No hay registros disponibles para ese periodo.")
    else:
        media_mes = int(round(df_mes_especifico["pasos_totales"].mean()))
        total_mes = int(df_mes_especifico["pasos_totales"].sum())
        dias_cumplidos = int((df_mes_especifico["pasos_totales"] >= meta_pasos).sum())
        dias_totales_mes = len(df_mes_especifico)
        porcentaje_exito = int(round((dias_cumplidos / dias_totales_mes) * 100)) if dias_totales_mes else 0
        mejor_dia = df_mes_especifico.loc[df_mes_especifico["pasos_totales"].idxmax()]
        peor_dia = df_mes_especifico.loc[df_mes_especifico["pasos_totales"].idxmin()]

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric(f"Media", f"{media_mes:,} pasos/día")
        col_m2.metric("Total acumulado", f"{total_mes:,} pasos")
        col_m3.metric("Días meta cumplida", f"{dias_cumplidos} / {dias_totales_mes}")
        col_m4.metric("Mejor día", f"{int(mejor_dia['pasos_totales']):,}", help=mejor_dia["fecha"].strftime("%d/%m/%Y"))

        col_grafica, col_anillo = st.columns([2.2, 1])

        with col_grafica:
            if mes_seleccionado_num == "Todos":
                eje_x, etiqueta_x = "fecha", "Fecha"
            else:
                eje_x, etiqueta_x = "dia_str", "Día del mes"

            fig_diario = px.bar(
                df_mes_especifico,
                x=eje_x,
                y="pasos_totales",
                labels={eje_x: etiqueta_x, "pasos_totales": "Pasos totales"},
                color="pasos_totales",
                color_continuous_scale="Purples",
            )
            fig_diario.add_hline(
                y=media_mes, line_dash="dash", line_color="#ef4444", line_width=2,
                annotation_text=f"Media: {media_mes:,}", annotation_position="top left",
            )
            fig_diario.add_hline(
                y=meta_pasos, line_dash="dot", line_color="#10b981", line_width=2.5,
                annotation_text=f"Meta: {meta_pasos:,}", annotation_position="top right",
            )
            fig_diario.update_layout(xaxis_tickmode="linear" if mes_seleccionado_num != "Todos" else "auto",
                                      hovermode="x unified", coloraxis_showscale=False)
            st.plotly_chart(fig_diario, use_container_width=True)

        with col_anillo:
            st.markdown("<h5 style='text-align: center;'>🎯 Tasa de éxito del objetivo</h5>", unsafe_allow_html=True)
            datos_meta = pd.DataFrame({
                "Estado": ["Meta cumplida", "Por debajo"],
                "Días": [dias_cumplidos, dias_totales_mes - dias_cumplidos],
            })
            fig_meta = px.pie(
                datos_meta, values="Días", names="Estado", hole=0.62, color="Estado",
                color_discrete_map={"Meta cumplida": "#10b981", "Por debajo": "#e2e8f0"},
            )
            fig_meta.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
                margin=dict(t=10, b=10, l=10, r=10),
                annotations=[dict(text=f"{porcentaje_exito}%", x=0.5, y=0.5, font_size=26,
                                   font_color="#10b981", font_family="Arial", showarrow=False)],
            )
            st.plotly_chart(fig_meta, use_container_width=True)

    st.divider()

    # ==========================================
    # RACHAS DE META CUMPLIDA
    # ==========================================
    st.header("🔥 Rachas de objetivo")

    rachas_meta = calcular_rachas_meta(df, meta_pasos)
    rachas_cumplidas = rachas_meta[rachas_meta["cumple"]].sort_values("dias", ascending=False)

    col_r1, col_r2 = st.columns(2)

    with col_r1:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>🏆 Mejores rachas cumpliendo la meta</h5>", unsafe_allow_html=True)
            if rachas_cumplidas.empty:
                st.info("Aún no hay rachas cumpliendo esta meta.")
            else:
                tabla_rachas = rachas_cumplidas.head(10)[["inicio", "fin", "dias"]].copy()
                tabla_rachas["inicio"] = tabla_rachas["inicio"].dt.strftime("%d/%m/%Y")
                tabla_rachas["fin"] = tabla_rachas["fin"].dt.strftime("%d/%m/%Y")
                tabla_rachas = tabla_rachas.rename(columns={"inicio": "Desde", "fin": "Hasta", "dias": "Días"})
                st.dataframe(tabla_rachas, use_container_width=True, hide_index=True, height=300)

    with col_r2:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Frecuencia de rachas por duración</h5>", unsafe_allow_html=True)
            if rachas_cumplidas.empty:
                st.info("Sin datos.")
            else:
                conteo_rachas = rachas_cumplidas["dias"].value_counts().reset_index()
                conteo_rachas.columns = ["dias", "veces"]
                conteo_rachas = conteo_rachas.sort_values("dias")
                fig_rachas = px.bar(
                    conteo_rachas, x="dias", y="veces", text="veces",
                    labels={"dias": "Días consecutivos cumpliendo meta", "veces": "Nº de veces"},
                    color_discrete_sequence=["#10b981"],
                )
                fig_rachas.update_traces(textposition="outside")
                fig_rachas.update_xaxes(dtick=1)
                fig_rachas.update_layout(margin=dict(t=20, b=10, l=10, r=10), height=300)
                st.plotly_chart(fig_rachas, use_container_width=True)

    st.divider()

    # ==========================================
    # RANKING DE DÍAS
    # ==========================================
    st.header("🏅 Ranking de días")
    col_top, col_bottom = st.columns(2)

    with col_top:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>🔝 Top 10 mejores días</h5>", unsafe_allow_html=True)
            top10 = df.nlargest(10, "pasos_totales")[["fecha", "pasos_totales", "dia_semana"]].copy()
            top10["fecha"] = top10["fecha"].dt.strftime("%d/%m/%Y")
            top10 = top10.rename(columns={"fecha": "Fecha", "pasos_totales": "Pasos", "dia_semana": "Día"})
            st.dataframe(top10, use_container_width=True, hide_index=True, height=300)

    with col_bottom:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>🔻 Top 10 peores días</h5>", unsafe_allow_html=True)
            bottom10 = df.nsmallest(10, "pasos_totales")[["fecha", "pasos_totales", "dia_semana"]].copy()
            bottom10["fecha"] = bottom10["fecha"].dt.strftime("%d/%m/%Y")
            bottom10 = bottom10.rename(columns={"fecha": "Fecha", "pasos_totales": "Pasos", "dia_semana": "Día"})
            st.dataframe(bottom10, use_container_width=True, hide_index=True, height=300)

    st.divider()

    # ==========================================
    # PATRONES Y TENDENCIAS
    # ==========================================
    st.header("📊 Patrones y tendencias")

    st.subheader("Distribución de actividad")
    fig_hist = px.histogram(
        df, x="pasos_totales", nbins=40,
        labels={"pasos_totales": "Rango de pasos", "count": "Número de días"},
        color_discrete_sequence=["#8b5cf6"],
    )
    fig_hist.add_vline(x=meta_pasos, line_dash="dot", line_color="#10b981", annotation_text="Meta")
    fig_hist.update_layout(bargap=0.1, yaxis_title="Días registrados")
    st.plotly_chart(fig_hist, use_container_width=True)

    col_izq, col_der = st.columns(2)

    with col_izq:
        st.subheader("Promedio diario por mes")
        pasos_mes_global = df.groupby("año_mes")["pasos_totales"].mean().round().astype(int).reset_index()
        fig_mes_global = px.bar(
            pasos_mes_global, x="año_mes", y="pasos_totales",
            labels={"año_mes": "Mes / año", "pasos_totales": "Promedio"},
            color="pasos_totales", color_continuous_scale="viridis",
        )
        fig_mes_global.add_hline(y=meta_pasos, line_dash="dot", line_color="#10b981")
        fig_mes_global.update_layout(xaxis_tickangle=-45, coloraxis_showscale=False)
        st.plotly_chart(fig_mes_global, use_container_width=True)

    with col_der:
        st.subheader("Rendimiento por día de la semana")
        pasos_dia_semana = (
            df.groupby("dia_semana")["pasos_totales"].mean().round().reindex(ORDEN_DIAS).fillna(0).reset_index()
        )
        pasos_dia_semana["pasos_totales"] = pasos_dia_semana["pasos_totales"].astype(int)
        fig_dias = px.bar(
            pasos_dia_semana, x="dia_semana", y="pasos_totales",
            labels={"dia_semana": "Día", "pasos_totales": "Promedio"},
            color="pasos_totales", color_continuous_scale="teal",
        )
        fig_dias.add_hline(y=meta_pasos, line_dash="dot", line_color="#10b981")
        fig_dias.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_dias, use_container_width=True)

    st.divider()

    # ==========================================
    # HEATMAP: mes x día de la semana
    # ==========================================
    with st.container(border=True):
        st.markdown("<h5 style='text-align: center;'>Mapa de calor: mes × día de la semana</h5>", unsafe_allow_html=True)

        df_heat = df.groupby(["mes_num", "dia_semana_en"])["pasos_totales"].mean().reset_index()
        pivot_heat = df_heat.pivot(index="mes_num", columns="dia_semana_en", values="pasos_totales")
        pivot_heat = pivot_heat.reindex(columns=ORDEN_DIAS_EN)
        pivot_heat.columns = [DIAS_ES[c] for c in pivot_heat.columns]
        pivot_heat.index = [MESES_ES[m] for m in pivot_heat.index]

        fig_heat = px.imshow(
            pivot_heat, color_continuous_scale="Purples",
            labels=dict(x="Día", y="Mes", color="Pasos medios"),
            aspect="auto",
        )
        fig_heat.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=400)
        st.plotly_chart(fig_heat, use_container_width=True)

    st.divider()

    # ==========================================
    # COMPARATIVA AÑO CONTRA AÑO
    # ==========================================
    años_con_datos = sorted(df["año"].unique())
    if len(años_con_datos) > 1:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>📅 Comparativa año contra año</h5>", unsafe_allow_html=True)

            df["dia_del_año"] = df["fecha"].dt.dayofyear
            df["acumulado_año"] = df.groupby("año")["pasos_totales"].cumsum()

            fig_comparativa = px.line(
                df, x="dia_del_año", y="acumulado_año", color="año",
                labels={"dia_del_año": "Día del año", "acumulado_año": "Pasos acumulados", "año": "Año"},
            )
            fig_comparativa.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=400,
                                            legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig_comparativa, use_container_width=True)

        st.divider()

    # ==========================================
    # CALENDARIO ANUAL TIPO GITHUB
    # ==========================================
    with st.container(border=True):
        st.markdown("<h5 style='text-align: center;'>📆 Calendario de actividad</h5>", unsafe_allow_html=True)

        años_disp_cal = sorted(df["año"].unique(), reverse=True)
        año_cal = st.selectbox("Año del calendario", años_disp_cal, key="año_calendario_pasos")

        df_año_cal = df[df["año"] == año_cal].copy()
        iso = df_año_cal["fecha"].dt.isocalendar()
        df_año_cal["semana"] = iso.week
        df_año_cal["iso_year"] = iso.year
        df_año_cal = df_año_cal[df_año_cal["iso_year"] == año_cal]
        df_año_cal["dia_semana_num"] = df_año_cal["fecha"].dt.dayofweek

        pivot_cal = df_año_cal.pivot_table(
            index="dia_semana_num", columns="semana", values="pasos_totales", fill_value=0
        )
        pivot_cal = pivot_cal.reindex(range(7), fill_value=0)
        dias_num_es = {0: "Lun", 1: "Mar", 2: "Mié", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom"}
        pivot_cal.index = [dias_num_es[i] for i in pivot_cal.index]

        fig_calendario = px.imshow(
            pivot_cal, color_continuous_scale="Greens",
            labels=dict(x="Semana del año", y="", color="Pasos"),
            aspect="auto",
        )
        fig_calendario.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=250)
        st.plotly_chart(fig_calendario, use_container_width=True)