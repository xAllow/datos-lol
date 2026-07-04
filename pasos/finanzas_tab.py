import io
from datetime import date
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from dashboard_config import BANK_CSV_URL, MESES_ES


def parse_number(val):
    if pd.isna(val):
        return 0.0
    val_str = str(val).strip()
    if not val_str:
        return 0.0
    # Spanish formatting uses '.' for thousands and ',' for decimals
    if "," in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    try:
        return float(val_str)
    except ValueError:
        return 0.0


def categorizar_transaccion(concepto: str) -> str:
    concept = str(concepto).upper()
    if "BIZUM" in concept:
        return "Bizum"
    elif any(
        kw in concept
        for kw in [
            "MERCADONA",
            "CARREFOUR",
            "CRF EXP",
            "BAZAR HONG YOU",
            "EXPRESS TAM",
            "EXPRESS TAMAYO",
            "SUPERMERCADO",
            "ALIMENTACION",
        ]
    ):
        return "Alimentación (Súper)"
    elif any(
        kw in concept
        for kw in [
            "DOMINOS PIZZA",
            "PIZZA",
            "MCDONALDS",
            "UBER",
            "EATS",
            "KIBAB",
            "DURUM",
            "CAFE",
            "CAFETERIA",
            "ASADOR",
            "RESTAURANTE",
            "CREMOLATTA",
            "BAR",
            "QUINTO A",
            "EL CENTIMO DE REGALO",
            "MADRE DE DIOS",
        ]
    ):
        return "Restauración / Comida"
    elif any(kw in concept for kw in ["AMAZON", "AMZN"]):
        return "Compras / Amazon"
    elif any(kw in concept for kw in ["AUTOESCUELA", "LIBRO", "LIBRARY", "AGAPEA"]):
        return "Formación / Estudios"
    elif any(
        kw in concept
        for kw in [
            "PAPA",
            "VICENTE",
            "ALVARO LUQUE",
            "TRANSF. ALVARO",
            "CONDONACION CUOTA MANT.",
        ]
    ):
        return "Transferencias Familia / Cuentas"
    elif any(kw in concept for kw in ["MOVISTAR", "TELEFONICA", "JAZZTEL", "WIFI"]):
        return "Telecomunicaciones / Wifi"
    elif "TESORO PUBLICO" in concept:
        return "Nómina / Ingresos del Estado"
    elif any(kw in concept for kw in ["COMIS.TARJETA", "LIQ. DE INT", "INTERESES"]):
        return "Comisiones / Intereses"
    elif any(
        kw in concept
        for kw in ["ALSA", "METRO", "BLABLACAR", "PAYPAL *BLABLACAR", "VIAJE"]
    ):
        return "Transporte / Viajes"
    elif "PELUQUERIA" in concept:
        return "Cuidado Personal"
    elif any(
        kw in concept for kw in ["BOMBONA", "GIBRALFARO GAS", "LUZ", "AGUA", "LLEIDA.NET"]
    ):
        return "Hogar / Suministros"
    elif any(
        kw in concept
        for kw in [
            "STEAM",
            "EPIC",
            "MICROSOFT STOR",
            "GIANTSGAMIN",
            "VERSE",
            "GOOGLE STATSFM",
        ]
    ):
        return "Ocio / Gaming"
    else:
        return "Otros"


@st.cache_data(ttl=300)
def cargar_datos_banco(_firma: str) -> pd.DataFrame:
    try:
        response = requests.get(BANK_CSV_URL)
        if response.status_code != 200:
            return pd.DataFrame()
        content = response.content.decode("utf-8")

        lines = content.splitlines()
        data_start = 0
        for idx, line in enumerate(lines):
            if line.startswith("fecha,concepto,"):
                data_start = idx
                break

        csv_data = "\n".join(lines[data_start:])
        df = pd.read_csv(io.StringIO(csv_data))
        df = df.dropna(subset=["fecha"])
        df = df[df["fecha"] != "fecha"]
        df = df.dropna(how="all")

        # Parsear fechas y números
        df["fecha_dt"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y", errors="coerce")
        df = df.dropna(subset=["fecha_dt"])

        df["importe_val"] = df["importe"].apply(parse_number)
        df["saldo_val"] = df["saldo"].apply(parse_number)

        # Limpiar conceptos y categorizar
        df["concepto"] = df["concepto"].astype(str).str.strip()
        df["categoria"] = df["concepto"].apply(categorizar_transaccion)

        # Ordenar cronológicamente (antiguo a reciente)
        df = df.sort_values(by=["fecha_dt", "saldo_val"], ascending=[True, True]).reset_index(
            drop=True
        )
        return df
    except Exception as e:
        st.error(f"Error cargando datos del banco: {e}")
        return pd.DataFrame()


def render_finanzas_tab() -> None:
    st.header("💳 Mis Finanzas")
    st.caption("Seguimiento de movimientos bancarios y análisis de gastos mensuales.")

    firma = date.today().isoformat()
    df = cargar_datos_banco(firma)

    if df.empty:
        st.warning("⚠️ No se encontraron movimientos bancarios o la URL no está disponible.")
        return

    # --- FILTROS ---
    st.subheader("Filtros de Búsqueda")
    col_f1, col_f2, col_f3 = st.columns(3)

    # Rango de Años
    años_disponibles = ["Todos"] + sorted(
        df["fecha_dt"].dt.year.dropna().unique().tolist(), reverse=True
    )
    with col_f1:
        año_sel = st.selectbox("Año", años_disponibles, index=0)

    # Rango de Meses
    if año_sel != "Todos":
        df_año = df[df["fecha_dt"].dt.year == año_sel]
        meses_disponibles = sorted(df_año["fecha_dt"].dt.month.dropna().unique().tolist())
        with col_f2:
            mes_sel_num = st.selectbox(
                "Mes",
                options=["Todos"] + meses_disponibles,
                format_func=lambda x: MESES_ES[x] if x != "Todos" else "Todos",
                index=0,
            )
    else:
        df_año = df.copy()
        with col_f2:
            st.selectbox("Mes", ["Todos"], disabled=True)
            mes_sel_num = "Todos"

    # Tipo de Transacción
    with col_f3:
        tipo_sel = st.selectbox(
            "Tipo de movimiento", ["Todos", "Solo Ingresos", "Solo Gastos"], index=0
        )

    # Buscador por concepto
    buscar_concepto = st.text_input("Buscar por concepto...")

    # Aplicar filtros
    df_filtrado = df_año.copy()
    if mes_sel_num != "Todos":
        df_filtrado = df_filtrado[df_filtrado["fecha_dt"].dt.month == mes_sel_num]

    if tipo_sel == "Solo Ingresos":
        df_filtrado = df_filtrado[df_filtrado["importe_val"] > 0]
    elif tipo_sel == "Solo Gastos":
        df_filtrado = df_filtrado[df_filtrado["importe_val"] < 0]

    if buscar_concepto:
        df_filtrado = df_filtrado[
            df_filtrado["concepto"].str.contains(buscar_concepto, case=False, na=False)
        ]

    # --- MÉTRICAS ---
    st.divider()

    # Saldo Actual Global (última fila de todo el dataset)
    saldo_actual_global = df.iloc[-1]["saldo_val"]

    # Calcular ingresos, gastos y ahorro del periodo filtrado
    ingresos_periodo = df_filtrado[df_filtrado["importe_val"] > 0]["importe_val"].sum()
    gastos_periodo = df_filtrado[df_filtrado["importe_val"] < 0]["importe_val"].sum()
    ahorro_periodo = ingresos_periodo + gastos_periodo  # gastos es negativo

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Saldo Actual Global", f"{saldo_actual_global:,.2f} €")
    col2.metric("Ingresos en Período", f"{ingresos_periodo:,.2f} €")
    col3.metric("Gastos en Período", f"{gastos_periodo:,.2f} €")

    # Ahorro neto con indicador dinámico de color
    tasa_ahorro = (
        (ahorro_periodo / ingresos_periodo) * 100
        if ingresos_periodo > 0 and ahorro_periodo > 0
        else 0
    )
    col4.metric(
        "Ahorro Neto",
        f"{ahorro_periodo:,.2f} €",
        delta=f"{tasa_ahorro:.1f}% tasa de ahorro" if ahorro_periodo > 0 else None,
    )

    # --- GRÁFICOS ---
    st.divider()

    # 1. Evolución del Saldo Temporal (ancho completo)
    st.subheader("📈 Evolución del Saldo Temporal")
    if not df_filtrado.empty:
        fig_saldo = px.line(
            df_filtrado,
            x="fecha_dt",
            y="saldo_val",
            labels={"fecha_dt": "Fecha", "saldo_val": "Saldo (€)"},
            color_discrete_sequence=["#1565c0"],
        )
        fig_saldo.update_traces(mode="lines+markers", marker=dict(size=4))
        fig_saldo.update_layout(hovermode="x unified", height=350, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig_saldo, use_container_width=True)
    else:
        st.info("Sin datos para graficar la evolución del saldo en este periodo.")

    # 2. Distribución y Comparaciones (Dos columnas)
    col_g1, col_g2 = st.columns([1.2, 1])

    with col_g1:
        st.subheader("📊 Ingresos vs Gastos Mensuales")
        # Agrupar por Mes
        df_mensual = df_filtrado.copy()
        df_mensual["año_mes"] = df_mensual["fecha_dt"].dt.to_period("M").astype(str)

        df_grouped = (
            df_mensual.groupby("año_mes")
            .agg(
                Ingresos=("importe_val", lambda x: x[x > 0].sum()),
                Gastos=("importe_val", lambda x: -x[x < 0].sum()),
            )
            .reset_index()
        )

        if not df_grouped.empty:
            fig_barras = go.Figure()
            fig_barras.add_trace(
                go.Bar(
                    x=df_grouped["año_mes"],
                    y=df_grouped["Ingresos"],
                    name="Ingresos",
                    marker_color="#00c853",
                )
            )
            fig_barras.add_trace(
                go.Bar(
                    x=df_grouped["año_mes"],
                    y=df_grouped["Gastos"],
                    name="Gastos",
                    marker_color="#d50000",
                )
            )
            fig_barras.update_layout(
                barmode="group",
                height=350,
                legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                margin=dict(t=10, b=10, l=10, r=10),
            )
            st.plotly_chart(fig_barras, use_container_width=True)
        else:
            st.info("Sin datos para el gráfico de barras mensual.")

    with col_g2:
        st.subheader("🍩 Distribución de Gastos")
        df_gastos = df_filtrado[df_filtrado["importe_val"] < 0].copy()
        df_gastos["importe_abs"] = -df_gastos["importe_val"]

        # Agrupar por categoría
        df_cat = df_gastos.groupby("categoria")["importe_abs"].sum().reset_index()
        df_cat = df_cat.sort_values(by="importe_abs", ascending=False)

        if not df_cat.empty:
            total_gastos = df_cat["importe_abs"].sum()
            fig_cat = px.pie(
                df_cat,
                values="importe_abs",
                names="categoria",
                hole=0.6,
                color_discrete_sequence=px.colors.qualitative.Safe,
            )
            fig_cat.update_traces(textinfo="percent")
            fig_cat.update_layout(
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="middle",
                    y=0.5,
                    xanchor="left",
                    x=0.95
                ),
                margin=dict(t=20, b=20, l=10, r=100),
                height=350,
                annotations=[
                    dict(
                        text=f"Gastos<br><b>{total_gastos:,.2f} €</b>",
                        x=0.5,
                        y=0.5,
                        font_size=15,
                        showarrow=False,
                        align="center"
                    )
                ]
            )
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("No se registraron gastos en este período.")


    # --- TABLA DETALLADA ---
    st.divider()
    st.subheader("📝 Listado de Movimientos")

    if not df_filtrado.empty:
        # Preparar dataframe para mostrar
        df_mostrar = df_filtrado[
            ["fecha", "concepto", "categoria", "importe_val", "saldo_val"]
        ].copy()
        df_mostrar.columns = ["Fecha", "Concepto", "Categoría", "Importe (€)", "Saldo (€)"]

        # Ordenar de más reciente a más antiguo para la tabla
        df_mostrar = df_mostrar.iloc[::-1].reset_index(drop=True)

        # Aplicar formato de color para Importe (verde para ingresos, rojo para gastos)
        def color_importe(val):
            color = "#00c853" if val > 0 else "#d50000"
            return f"color: {color}; font-weight: bold;"

        try:
            st.dataframe(
                df_mostrar.style.format({"Importe (€)": "{:,.2f} €", "Saldo (€)": "{:,.2f} €"}).map(
                    color_importe, subset=["Importe (€)"]
                ),
                use_container_width=True,
                hide_index=True,
            )
        except Exception:
            # Fallback en caso de que style.map falle o no esté soportado
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
    else:
        st.info("No hay movimientos que coincidan con los filtros seleccionados.")
