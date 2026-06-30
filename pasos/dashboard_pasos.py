import os
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="Panel de Vida", page_icon="📊", layout="wide")

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

MESES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def cargar_env_local(ruta: str = ".env") -> None:
    ruta_completa = ROOT_DIR / ruta
    if not ruta_completa.exists():
        return

    with open(ruta_completa, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue

            clave, valor = linea.split("=", 1)
            clave = clave.strip()
            valor = valor.strip().strip('"').strip("'")
            os.environ.setdefault(clave, valor)


cargar_env_local()


def config_value(nombre: str, defecto: Any = None) -> Any:
    valor = os.getenv(nombre)
    if valor not in (None, ""):
        return valor

    try:
        return st.secrets.get(nombre, defecto)
    except Exception:
        return defecto


MONGODB_URI = config_value("MONGODB_URI")
DB_NAME = config_value("DB_NAME", "lol")
STEPS_COLLECTION_NAME = config_value("COLLECTION_NAME", "pasos")
LOL_COLLECTION_NAME = config_value("LOL_COLLECTION_NAME", "partidas")
LOL_PUUID = config_value("LOL_PUUID")
LOL_RIOT_ID = config_value("LOL_RIOT_ID", "xAllow")

if not MONGODB_URI:
    st.error("❌ Falta configurar `MONGODB_URI`. El panel necesita MongoDB para cargar datos.")
    st.stop()


def obtener_conexion_mongo():
    from pymongo import MongoClient

    return MongoClient(MONGODB_URI)


def obtener_coleccion(nombre_coleccion: str):
    client = obtener_conexion_mongo()
    return client, client[DB_NAME][nombre_coleccion]


def to_epoch_seconds(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return float(value.timestamp())
    return float(pd.to_datetime(value, errors="coerce").timestamp())


def duration_to_seconds(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value) / 1000.0 if float(value) > 10000 else float(value)
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return 0.0
    return float(parsed) / 1000.0 if float(parsed) > 10000 else float(parsed)


def normalize_day_series(df: pd.DataFrame, date_col: str, value_col: str) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    if df.empty:
        return df

    df.set_index(date_col, inplace=True)
    calendario = pd.date_range(start=df.index.min(), end=df.index.max())
    df = df.reindex(calendario, fill_value=0)
    df = df.reset_index().rename(columns={"index": date_col})
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
    return df


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

        dias_es = {
            "Monday": "Lunes",
            "Tuesday": "Martes",
            "Wednesday": "Miércoles",
            "Thursday": "Jueves",
            "Friday": "Viernes",
            "Saturday": "Sábado",
            "Sunday": "Domingo",
        }
        df["dia_semana"] = df["fecha"].dt.day_name().map(dias_es)
        return df, metricas_imputacion

    try:
        df, metricas = cargar_datos_pasos(firma_datos())
    except Exception as e:
        st.error(f"❌ No se pudieron cargar los datos de pasos: {e}")
        return

    if df.empty:
        st.warning("⚠️ No se encontraron datos de pasos a partir del 1 de enero de 2025.")
        return

    config_col1, config_col2, config_col3 = st.columns([1.1, 1.1, 1])

    años_disponibles = sorted(df["año"].unique(), reverse=True)
    año_actual = date.today().year
    indice_anio_actual = años_disponibles.index(año_actual) if año_actual in años_disponibles else 0

    with config_col1:
        año_seleccionado = st.selectbox("Año", años_disponibles, index=indice_anio_actual)

    df_filtrado_año = df[df["año"] == año_seleccionado]
    meses_disponibles = sorted(df_filtrado_año["mes_num"].unique())
    mes_actual = date.today().month
    indice_mes_actual = meses_disponibles.index(mes_actual) if mes_actual in meses_disponibles else 0

    with config_col2:
        mes_seleccionado_num = st.selectbox(
            "Mes",
            options=meses_disponibles,
            index=indice_mes_actual,
            format_func=lambda x: MESES_ES[x],
        )

    with config_col3:
        meta_pasos = st.slider("Meta diaria", min_value=3000, max_value=20000, value=10000, step=500)

    st.caption(f"Objetivo actual: {meta_pasos:,} pasos por día")

    with st.expander("Auditoría de imputación", expanded=False):
        st.markdown(f"**Días vacíos rellenados:** {metricas['dias_rellenados']}")
        if metricas["dias_rellenados"] > 0:
            st.markdown(f"**Percentil 5 (suelo):** {metricas['limite_inf']} pasos")
            st.markdown(f"**Percentil 15 (techo):** {metricas['limite_sup']} pasos")

    df_mes_especifico = df_filtrado_año[df_filtrado_año["mes_num"] == mes_seleccionado_num].sort_values("fecha")
    nombre_mes = MESES_ES[mes_seleccionado_num]

    st.divider()
    st.header("🌍 Resumen histórico")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Días analizados", f"{len(df)} días")
    col2.metric("Promedio diario", f"{int(df['pasos_totales'].mean()):,} pasos")
    col3.metric("Récord absoluto", f"{int(df['pasos_totales'].max()):,} pasos")
    col4.metric("Pasos acumulados", f"{int(df['pasos_totales'].sum()):,}")

    st.subheader("Línea de tiempo")
    fig_linea = px.line(
        df,
        x="fecha",
        y="pasos_totales",
        labels={"fecha": "Fecha", "pasos_totales": "Pasos totales"},
        color_discrete_sequence=["#4f46e5"],
    )
    fig_linea.update_xaxes(rangeslider_visible=True)
    fig_linea.update_layout(hovermode="x unified")
    st.plotly_chart(fig_linea, use_container_width=True)

    st.divider()
    st.header(f"🔍 Detalle de {nombre_mes} {año_seleccionado}")

    if df_mes_especifico.empty:
        st.warning("No hay registros disponibles para ese periodo.")
    else:
        media_mes = int(round(df_mes_especifico["pasos_totales"].mean()))
        total_mes = int(df_mes_especifico["pasos_totales"].sum())
        dias_cumplidos = int((df_mes_especifico["pasos_totales"] >= meta_pasos).sum())
        dias_totales_mes = len(df_mes_especifico)
        porcentaje_exito = int(round((dias_cumplidos / dias_totales_mes) * 100)) if dias_totales_mes else 0

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric(f"Media en {nombre_mes}", f"{media_mes:,} pasos/día")
        col_m2.metric("Total acumulado", f"{total_mes:,} pasos")
        col_m3.metric("Días meta cumplida", f"{dias_cumplidos} / {dias_totales_mes}")

        col_grafica, col_anillo = st.columns([2.2, 1])

        with col_grafica:
            fig_diario = px.bar(
                df_mes_especifico,
                x="dia_str",
                y="pasos_totales",
                labels={"dia_str": "Día del mes", "pasos_totales": "Pasos totales"},
                color="pasos_totales",
                color_continuous_scale="Purples",
            )
            fig_diario.add_hline(
                y=media_mes,
                line_dash="dash",
                line_color="#ef4444",
                line_width=2,
                annotation_text=f"Media: {media_mes:,}",
                annotation_position="top left",
            )
            fig_diario.add_hline(
                y=meta_pasos,
                line_dash="dot",
                line_color="#10b981",
                line_width=2.5,
                annotation_text=f"Meta: {meta_pasos:,}",
                annotation_position="top right",
            )
            fig_diario.update_layout(xaxis_tickmode="linear", hovermode="x unified", coloraxis_showscale=False)
            st.plotly_chart(fig_diario, use_container_width=True)

        with col_anillo:
            st.markdown("<h5 style='text-align: center;'>🎯 Tasa de éxito del objetivo</h5>", unsafe_allow_html=True)
            datos_meta = pd.DataFrame(
                {
                    "Estado": ["Meta cumplida", "Por debajo"],
                    "Días": [dias_cumplidos, dias_totales_mes - dias_cumplidos],
                }
            )
            fig_meta = px.pie(
                datos_meta,
                values="Días",
                names="Estado",
                hole=0.62,
                color="Estado",
                color_discrete_map={"Meta cumplida": "#10b981", "Por debajo": "#e2e8f0"},
            )
            fig_meta.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
                margin=dict(t=10, b=10, l=10, r=10),
                annotations=[
                    dict(
                        text=f"{porcentaje_exito}%",
                        x=0.5,
                        y=0.5,
                        font_size=26,
                        font_color="#10b981",
                        font_family="Arial",
                        showarrow=False,
                    )
                ],
            )
            st.plotly_chart(fig_meta, use_container_width=True)

    st.divider()
    st.header("📊 Patrones y tendencias")

    st.subheader("Distribución de actividad")
    fig_hist = px.histogram(
        df,
        x="pasos_totales",
        nbins=40,
        labels={"pasos_totales": "Rango de pasos", "count": "Número de días"},
        color_discrete_sequence=["#8b5cf6"],
    )
    fig_hist.update_layout(bargap=0.1, yaxis_title="Días registrados")
    st.plotly_chart(fig_hist, use_container_width=True)

    col_izq, col_der = st.columns(2)

    with col_izq:
        st.subheader("Promedio diario por mes")
        pasos_mes_global = df.groupby("año_mes")["pasos_totales"].mean().round().astype(int).reset_index()
        fig_mes_global = px.bar(
            pasos_mes_global,
            x="año_mes",
            y="pasos_totales",
            labels={"año_mes": "Mes / año", "pasos_totales": "Promedio"},
            color="pasos_totales",
            color_continuous_scale="viridis",
        )
        fig_mes_global.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_mes_global, use_container_width=True)

    with col_der:
        st.subheader("Rendimiento por día de la semana")
        orden_dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        pasos_dia_semana = (
            df.groupby("dia_semana")["pasos_totales"].mean().round().reindex(orden_dias).fillna(0).reset_index()
        )
        pasos_dia_semana["pasos_totales"] = pasos_dia_semana["pasos_totales"].astype(int)
        fig_dias = px.bar(
            pasos_dia_semana,
            x="dia_semana",
            y="pasos_totales",
            labels={"dia_semana": "Día", "pasos_totales": "Promedio"},
            color="pasos_totales",
            color_continuous_scale="teal",
        )
        st.plotly_chart(fig_dias, use_container_width=True)


def resolver_puuid_lol() -> str | None:
    if LOL_PUUID:
        return str(LOL_PUUID)

    try:
        client, collection = obtener_coleccion(LOL_COLLECTION_NAME)
        documento = collection.find_one(
            {"metadata.targetPuuid": {"$exists": True, "$nin": [None, ""]}},
            {"_id": 0, "metadata.targetPuuid": 1},
            sort=[("info.gameCreation", -1)],
        )
        client.close()
        if documento:
            return documento.get("metadata", {}).get("targetPuuid")
    except Exception:
        pass

    try:
        client, collection = obtener_coleccion(LOL_COLLECTION_NAME)
        pipeline = [
            {"$match": {"info.participants.puuid": {"$exists": True}}},
            {"$unwind": "$info.participants"},
            {"$match": {"info.participants.puuid": {"$exists": True, "$nin": [None, ""]}}},
            {"$group": {"_id": "$info.participants.puuid", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 1},
        ]
        resultado = list(collection.aggregate(pipeline))
        client.close()
        if resultado:
            return resultado[0]["_id"]
    except Exception:
        return None

    return None


def firma_datos_lol() -> tuple:
    try:
        client, collection = obtener_coleccion(LOL_COLLECTION_NAME)
        total = collection.count_documents({})
        ultimo = collection.find_one({}, {"_id": 0, "info.gameCreation": 1, "metadata.matchId": 1}, sort=[("info.gameCreation", -1)])
        client.close()
        return ("lol", total, ultimo)
    except Exception:
        return ("lol-error",)


def extraer_fila_lol(match_data: dict[str, Any], puuid: str | None, riot_id: str | None) -> dict[str, Any] | None:
    info = match_data.get("info", {})
    participantes = info.get("participants") or []
    
    # 1. Intentamos buscarte primero por PUUID (es el método más seguro)
    participante = None
    if puuid:
        participante = next((p for p in participantes if p.get("puuid") == puuid), None)
    
    # 2. Si no te encuentra por PUUID, te busca por tu Riot ID o antiguo Summoner Name
    if not participante and riot_id:
        participante = next(
            (p for p in participantes if p.get("riotIdGameName") == riot_id or p.get("summonerName") == riot_id), 
            None
        )
        
    if not participante:
        return None

    kills = int(participante.get("kills") or 0)
    deaths = int(participante.get("deaths") or 0)
    assists = int(participante.get("assists") or 0)

    return {
        "fecha": info.get("gameCreation"),
        "match_id": match_data.get("metadata", {}).get("matchId"),
        "champion": participante.get("championName") or "Desconocido",
        "role": participante.get("teamPosition") or participante.get("individualPosition") or participante.get("role") or "UNKNOWN",
        "win": bool(participante.get("win")),
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kda": (kills + assists) / max(1, deaths),
        "damage": int(participante.get("totalDamageDealtToChampions") or 0),
        "vision": int(participante.get("visionScore") or 0),
        "gold": int(participante.get("goldEarned") or 0),
        "cs": int(participante.get("totalMinionsKilled") or 0) + int(participante.get("neutralMinionsKilled") or 0),
        "duration_seconds": duration_to_seconds(info.get("gameDuration")),
        "queue_id": info.get("queueId"),
    }


@st.cache_data(ttl=300)
def cargar_datos_lol(_firma: tuple, puuid: str | None, riot_id: str | None) -> pd.DataFrame:
    client, collection = obtener_coleccion(LOL_COLLECTION_NAME)
    
    # Construimos un filtro flexible para capturar todo
    condiciones = []
    if puuid:
        condiciones.append({"info.participants.puuid": puuid})
    if riot_id:
        condiciones.append({"info.participants.riotIdGameName": riot_id})
        condiciones.append({"info.participants.summonerName": riot_id}) # Por si hay registros antiguos
        
    filtro = {"$or": condiciones} if condiciones else {}
    
    documentos = list(collection.find(filtro, {"_id": 0}).sort("info.gameCreation", 1))
    client.close()

    filas = []
    for match_data in documentos:
        # Pasamos ambos parámetros a la extracción de la fila
        fila = extraer_fila_lol(match_data, puuid, riot_id)
        if fila:
            filas.append(fila)

    df = pd.DataFrame(filas)
    if df.empty:
        return df

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna(subset=["fecha"]).sort_values("fecha")
    df["duration_minutes"] = pd.to_numeric(df["duration_seconds"], errors="coerce").fillna(0) / 60.0
    df["cs_min"] = df.apply(lambda row: (row["cs"] / row["duration_minutes"]) if row["duration_minutes"] else 0, axis=1)
    return df


def render_lol_tab() -> None:
    st.header("🎮 Mis stats de LoL")
    st.caption("Resumen personal desde MongoDB usando solo las partidas ya guardadas.")

    puuid = resolver_puuid_lol()
    riot_id = LOL_RIOT_ID  # <--- Recuperamos el nombre de la configuración
    
    if not puuid and not riot_id:
        st.info(
            "No pude identificar tu cuenta de LoL. Puedes definir `LOL_PUUID` o `LOL_RIOT_ID` en el entorno."
        )
        return

    try:
        # PASAMOS AMBOS AQUÍ:
        df = cargar_datos_lol(firma_datos_lol(), puuid, riot_id)
    except Exception as e:
        st.error(f"❌ No se pudieron cargar las partidas de LoL: {e}")
        return

    if df.empty:
        st.warning("No hay partidas de LoL para esa cuenta en MongoDB todavía.")
        return

    años_disponibles = ["Todos"] + sorted(df["fecha"].dt.year.dropna().astype(int).unique(), reverse=True)
    col_filtro1, col_filtro2 = st.columns([1, 1])

    with col_filtro1:
        año_seleccionado = st.selectbox("Año", años_disponibles, index=0)

    if año_seleccionado == "Todos":
        df_anual = df.copy()
    else:
        df_anual = df[df["fecha"].dt.year == año_seleccionado].copy()

    roles_disponibles = ["Todos"] + sorted(df_anual["role"].fillna("UNKNOWN").astype(str).unique().tolist())

    with col_filtro2:
        rol_seleccionado = st.selectbox("Rol", roles_disponibles, index=0)

    if rol_seleccionado != "Todos":
        df_anual = df_anual[df_anual["role"] == rol_seleccionado]

    if df_anual.empty:
        st.warning("No hay partidas para los filtros seleccionados.")
        return

    partidas = len(df_anual)
    partidas_guardadas = len(df)
    victorias = int(df_anual["win"].sum())
    winrate = round((victorias / partidas) * 100, 1) if partidas else 0
    kda_prom = round(df_anual["kda"].mean(), 2)
    damage_prom = int(df_anual["damage"].mean())
    cs_min_prom = round(df_anual["cs_min"].mean(), 2)
    duracion_prom = round(df_anual["duration_minutes"].mean(), 1)

    st.subheader("Resumen general")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Partidas guardadas", f"{partidas_guardadas}")
    m2.metric("Victorias", f"{victorias}")
    m3.metric("Winrate", f"{winrate}%")
    m4.metric("KDA medio", f"{kda_prom}")
    m5.metric("Daño medio", f"{damage_prom:,}")
    m6.metric("CS/min", f"{cs_min_prom}")

    st.caption(f"Partidas visibles con los filtros actuales: {partidas}")

    c1, c2 = st.columns([1, 1.2])

    with c1:
        st.subheader("Victorias vs derrotas")
        resumen_resultado = pd.DataFrame(
            {
                "Resultado": ["Victoria", "Derrota"],
                "Partidas": [victorias, partidas - victorias],
            }
        )
        fig_resultado = px.pie(
            resumen_resultado,
            values="Partidas",
            names="Resultado",
            hole=0.6,
            color="Resultado",
            color_discrete_map={"Victoria": "#10b981", "Derrota": "#e5e7eb"},
        )
        fig_resultado.update_layout(margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig_resultado, use_container_width=True)

    with c2:
        st.subheader("Campeones más jugados")
        top_campeones = df_anual.groupby("champion").size().sort_values(ascending=False).head(10).reset_index(name="partidas")
        fig_campeones = px.bar(
            top_campeones,
            x="champion",
            y="partidas",
            color="partidas",
            color_continuous_scale="Blues",
            labels={"champion": "Campeón", "partidas": "Partidas"},
        )
        fig_campeones.update_layout(xaxis_tickangle=-35)
        st.plotly_chart(fig_campeones, use_container_width=True)

    st.subheader("Evolución reciente")
    df_reciente = df_anual.sort_values("fecha").tail(20).copy()
    fig_tendencia = px.line(
        df_reciente,
        x="fecha",
        y=["kills", "assists", "damage"],
        labels={"value": "Valor", "variable": "Métrica", "fecha": "Fecha"},
    )
    fig_tendencia.update_layout(hovermode="x unified")
    st.plotly_chart(fig_tendencia, use_container_width=True)

    st.subheader("Últimas partidas")
    tabla = df_anual.sort_values("fecha", ascending=False)[
        ["fecha", "champion", "role", "win", "kills", "deaths", "assists", "kda", "damage", "cs_min"]
    ].head(15)
    tabla = tabla.rename(
        columns={
            "fecha": "Fecha",
            "champion": "Campeón",
            "role": "Rol",
            "win": "Victoria",
            "kills": "Kills",
            "deaths": "Deaths",
            "assists": "Assists",
            "kda": "KDA",
            "damage": "Daño",
            "cs_min": "CS/min",
        }
    )
    st.dataframe(tabla, use_container_width=True, hide_index=True)


def main() -> None:
    st.title("📊 Mi panel de vida")
    st.markdown("Un lugar para ver pasos, LoL y más métricas personales en pestañas separadas.")
    
    tab_pasos, tab_lol = st.tabs(["🚶 Pasos", "🎮 LoL"])

    with tab_pasos:
        render_steps_tab()

    with tab_lol:
        render_lol_tab()


if __name__ == "__main__":
    main()