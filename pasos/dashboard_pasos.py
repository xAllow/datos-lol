import os
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import plotly.graph_objects as go

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
GOOGLE_SHEET_CSV_URL = config_value("GOOGLE_SHEET_CSV_URL")

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
    
    participante = None
    if puuid:
        participante = next((p for p in participantes if p.get("puuid") == puuid), None)
    
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
    team_id = int(participante.get("teamId") or 0)
    lado = "Azul" if team_id == 100 else "Rojo" if team_id == 200 else "Desconocido"

    # --- Compañeros de equipo por línea (campeón + tipo de daño) ---
    mi_puuid = participante.get("puuid")
    mapa_roles = {
        "champ_top": "TOP",
        "champ_jungle": "JUNGLE",
        "champ_mid": "MIDDLE",
        "champ_adc": "BOTTOM",
        "champ_support": "UTILITY",
    }
    compañeros = {}
    for col, role_code in mapa_roles.items():
        companero = next(
            (
                p for p in participantes
                if int(p.get("teamId") or 0) == team_id
                and p.get("puuid") != mi_puuid
                and (p.get("teamPosition") or p.get("individualPosition")) == role_code
            ),
            None,
        )
        compañeros[col] = companero.get("championName") if companero else None
        compañeros[f"{col}_damage_type"] = companero.get("champion_damage_type") if companero else None

    # --- Objetivos del equipo ---
    team_data = next((t for t in info.get("teams", []) if t.get("teamId") == team_id), {})
    objetivos = team_data.get("objectives", {})
    dragon_kills = objetivos.get("dragon", {}).get("kills", 0)
    baron_kills = objetivos.get("baron", {}).get("kills", 0)
    herald_kills = objetivos.get("riftHerald", {}).get("kills", 0)
    grub_kills = objetivos.get("horde", {}).get("kills", 0)

    fila = {
        "fecha": info.get("gameCreation"),
        "match_id": match_data.get("metadata", {}).get("matchId"),
        "champion": participante.get("championName") or "Desconocido",
        "champion_damage_type": participante.get("champion_damage_type"),
        "role": participante.get("teamPosition") or participante.get("individualPosition") or participante.get("role") or "UNKNOWN",
        "win": bool(participante.get("win")),
        "lado": lado,
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
        "dragon_kills": dragon_kills,
        "baron_kills": baron_kills,
        "herald_kills": herald_kills,
        "grub_kills": grub_kills,
    }
    fila.update(compañeros)
    return fila

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

    # === CÁLCULOS PREVIOS ===
    partidas = len(df_anual)
    victorias = int(df_anual["win"].sum())
    winrate = (victorias / partidas) * 100 if partidas else 0
    kda_prom = df_anual["kda"].mean()
    kills_prom = df_anual["kills"].mean()
    deaths_prom = df_anual["deaths"].mean()
    assists_prom = df_anual["assists"].mean()
    duracion_prom = df_anual["duration_minutes"].mean()
    damage_prom = int(df_anual["damage"].mean())
    cs_min_prom = df_anual["cs_min"].mean()

    # Separar victorias por lado (para el donut de Winrate Lado)
    df_azul = df_anual[df_anual["lado"] == "Azul"]
    df_rojo = df_anual[df_anual["lado"] == "Rojo"]
    
    partidas_azul = len(df_azul)
    partidas_rojo = len(df_rojo)
    
    wins_azul = len(df_azul[df_azul["win"] == True])
    wins_rojo = len(df_rojo[df_rojo["win"] == True])
    
    # Calculamos el winrate real de cada lado
    winrate_azul = (wins_azul / partidas_azul) * 100 if partidas_azul else 0
    winrate_rojo = (wins_rojo / partidas_rojo) * 100 if partidas_rojo else 0

    # 1. Rangos de 5 minutos para la duración
    bins_duracion = range(0, 55, 5)
    labels_duracion = [f"{i} - {i+5}" for i in range(0, 50, 5)]
    df_anual["duracion_rango"] = pd.cut(
        df_anual["duration_minutes"], 
        bins=bins_duracion, 
        labels=labels_duracion, 
        right=False
    )
    
    # 2. Extraer la hora de la partida
    df_anual["hora"] = df_anual["fecha"].dt.hour

    st.subheader("Resumen general")
    st.caption(f"Partidas visibles con los filtros actuales: {partidas}")

    # Definimos las alturas fijas para que todas las tarjetas cuadren perfectamente
    ALTURA_FILA_1 = 180
    ALTURA_FILA_2 = 280

    # === FILA 1 ===
    f1_col1, f1_col2, f1_col3, f1_col4 = st.columns(4)
    
    with f1_col1.container(height=ALTURA_FILA_1, border=True):
        st.markdown(f"<div style='text-align: center; margin-top: 10px;'><b>Cantidad de partidas</b><br><span style='font-size: 3rem; font-weight: bold;'>{partidas}</span></div>", unsafe_allow_html=True)
        
    with f1_col2.container(height=ALTURA_FILA_1, border=True):
        st.markdown(f"<div style='text-align: center; margin-top: 10px;'><b>Media de tiempo</b><br><span style='font-size: 2.5rem; font-weight: bold;'>{duracion_prom:.1f}</span><span style='font-size: 1.5rem;'> mins</span></div>", unsafe_allow_html=True)
        
    with f1_col3.container(height=ALTURA_FILA_1, border=True):
        st.markdown(f"<div style='text-align: center; margin-top: 10px;'><b>KDA</b><br><span style='font-size: 3rem; font-weight: bold;'>{kda_prom:.2f}</span></div>", unsafe_allow_html=True)
        
    with f1_col4.container(height=ALTURA_FILA_1, border=True):
        st.markdown(f"""
        <div style='text-align: center;'>
            <b>KDA Detalle</b>
            <table style='width:100%; text-align:center; margin-top:10px; font-size: 1.1rem;'>
                <tr style='border-bottom: 1px solid #ddd; color: gray;'>
                    <th>Kills</th><th>Deaths</th><th>Assist</th>
                </tr>
                <tr>
                    <td style='padding-top:10px;'>{kills_prom:.2f}</td>
                    <td style='padding-top:10px;'>{deaths_prom:.2f}</td>
                    <td style='padding-top:10px;'>{assists_prom:.2f}</td>
                </tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    st.write("") # Pequeño espacio

    # === FILA 2 ===
    f2_col1, f2_col2, f2_col3, f2_col4 = st.columns(4)

    with f2_col1.container(height=ALTURA_FILA_2, border=True):
        st.markdown(f"<div style='text-align: center; margin-top: 50px;'><b>Winrate</b><br><span style='font-size: 3rem; font-weight: bold;'>{winrate:.2f}%</span></div>", unsafe_allow_html=True)

    with f2_col2.container(height=ALTURA_FILA_2, border=True):
        st.markdown("<div style='text-align: center;'><b>Winrate</b></div>", unsafe_allow_html=True)
        df_w = pd.DataFrame({"Res": ["Victoria", "Derrota"], "Val": [victorias, partidas - victorias]})
        fig_w = px.pie(df_w, values="Val", names="Res", hole=0.6, color="Res", color_discrete_map={"Victoria": "#00c853", "Derrota": "#d50000"})
        fig_w.update_traces(textinfo='percent', textposition='outside', hoverinfo='label+value')
        # Ajustamos el height de la gráfica para que quepa bien en el contenedor fijo
        fig_w.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=200)
        st.plotly_chart(fig_w, use_container_width=True)

    with f2_col3.container(height=ALTURA_FILA_2, border=True):
        st.markdown("<div style='text-align: center;'><b>Lado</b></div>", unsafe_allow_html=True)
        lados_count = df_anual["lado"].value_counts().reset_index()
        lados_count.columns = ["Lado", "Cantidad"]
        fig_l = px.pie(lados_count, values="Cantidad", names="Lado", hole=0.6, color="Lado", color_discrete_map={"Azul": "#0288d1", "Rojo": "#d50000", "Desconocido": "#9e9e9e"})
        fig_l.update_traces(textinfo='percent', textposition='outside', hoverinfo='label+value')
        fig_l.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=200)
        st.plotly_chart(fig_l, use_container_width=True)

    with f2_col4.container(height=ALTURA_FILA_2, border=True):
        st.markdown("<div style='text-align: center;'><b>Winrate Lado</b></div>", unsafe_allow_html=True)
        
        # Pasamos el winrate para el tamaño visual del quesito, y una columna extra para el texto
        df_wl = pd.DataFrame({
            "Lado": ["Azul", "Rojo"], 
            "Winrate_Visual": [winrate_azul, winrate_rojo],
            "Texto_Mostrar": [f"{winrate_azul:.2f}%", f"{winrate_rojo:.2f}%"]
        })
        
        fig_wl = px.pie(
            df_wl, 
            values="Winrate_Visual", 
            names="Lado", 
            hole=0.6, 
            color="Lado", 
            color_discrete_map={"Azul": "#0288d1", "Rojo": "#d50000"}
        )
        
        # Usamos textinfo='text' para obligar a Plotly a usar nuestra columna "Texto_Mostrar"
        fig_wl.update_traces(
            text=df_wl["Texto_Mostrar"], 
            textinfo='text', 
            textposition='outside', 
            hoverinfo='label+text'
        )
        fig_wl.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=200)
        
        st.plotly_chart(fig_wl, use_container_width=True)

    st.write("") 

    # === FILA 3 ===
    f3_col1, f3_col2 = st.columns(2)
    with f3_col1.container(border=True):
        st.markdown(f"<div style='text-align: center;'><b>Daño medio</b><br><span style='font-size: 2rem;'>{damage_prom:,}</span></div>", unsafe_allow_html=True)
    with f3_col2.container(border=True):
        st.markdown(f"<div style='text-align: center;'><b>CS / Minuto</b><br><span style='font-size: 2rem;'>{cs_min_prom:.2f}</span></div>", unsafe_allow_html=True)


    st.divider()
    col_izq, col_der = st.columns(2)

    # ==========================================
    # COLUMNA IZQUIERDA
    # ==========================================
    with col_izq:
        # 1. TABLA KDA
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>KDA</h5>", unsafe_allow_html=True)
            df_kda = df_anual.groupby("champion").agg(
                Partidas=("win", "count"),
                Kills=("kills", "mean"),
                Deaths=("deaths", "mean"),
                Assist=("assists", "mean")
            ).reset_index()

            df_kda["KDA"] = (df_kda["Kills"] + df_kda["Assist"]) / df_kda["Deaths"].replace(0, 1)
            df_kda = df_kda.sort_values("Partidas", ascending=False).round(2)
            df_kda = df_kda.rename(columns={"champion": "Campeón"})

            st.dataframe(df_kda, use_container_width=True, hide_index=True, height=250)

        # 2. WINRATE POR MINUTOS
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Winrate por minutos</h5>", unsafe_allow_html=True)
            df_wr_min = df_anual.groupby("duracion_rango", observed=False)["win"].mean().reset_index(name="Winrate")
            df_wr_min["Winrate"] *= 100

            fig_wr_min = px.line(
                df_wr_min,
                x="duracion_rango",
                y="Winrate",
                markers=True,
                labels={"duracion_rango": "duracion", "Winrate": "Winrate"}
            )
            fig_wr_min.update_traces(line_color="#00c853", marker=dict(size=8), connectgaps=True)
            fig_wr_min.update_yaxes(ticksuffix="%")
            fig_wr_min.update_xaxes(tickangle=-90)
            fig_wr_min.update_layout(margin=dict(t=20, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig_wr_min, use_container_width=True)

        # 3. WINRATE POR HORAS
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Winrate por Horas (Cantidad color)</h5>", unsafe_allow_html=True)
            df_wr_hora = df_anual.groupby("hora").agg(
                Winrate=("win", "mean"),
                Partidas=("win", "count")
            ).reset_index()
            df_wr_hora["Winrate"] *= 100
            df_wr_hora["hora"] = df_wr_hora["hora"].astype(int)
            df_wr_hora = df_wr_hora.sort_values("hora")
            df_wr_hora["hora_str"] = df_wr_hora["hora"].astype(str)

            fig_hora = px.bar(
                df_wr_hora,
                x="hora_str",
                y="Winrate",
                color="Partidas",
                color_continuous_scale="Greens",
                text=df_wr_hora["Winrate"].round(1).astype(str) + "%",
            )
            fig_hora.update_traces(textposition="outside")
            fig_hora.update_yaxes(ticksuffix="%", range=[0, max(df_wr_hora["Winrate"].max() * 1.15, 10)])
            fig_hora.update_xaxes(type="category", title="hora")
            fig_hora.update_layout(margin=dict(t=30, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig_hora, use_container_width=True)

        # 4. DINERO POR POSITION
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Dinero por position</h5>", unsafe_allow_html=True)

            df_pos = df_anual[df_anual["role"] != "UNKNOWN"].copy()

            fig_dinero = px.scatter(
                df_pos,
                x="duration_minutes",
                y="gold",
                color="role",
                color_discrete_map={
                    "JUNGLE": "#00c853",
                    "MIDDLE": "#2962ff",
                    "TOP": "#ff8f00",
                    "UTILITY": "#d500f9",
                    "BOTTOM": "#d50000",
                },
                labels={"duration_minutes": "duracion", "gold": "yo.goldEarned", "role": "yo.individualPosition"},
                opacity=0.6,
            )
            fig_dinero.update_traces(marker=dict(size=8, line=dict(width=1)))
            fig_dinero.update_layout(margin=dict(t=20, b=10, l=10, r=10), height=400)
            st.plotly_chart(fig_dinero, use_container_width=True)

    # ==========================================
    # COLUMNA DERECHA
    # ==========================================
    with col_der:
        # 1. DISTRIBUCIÓN DEL TIEMPO
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Distribución del tiempo de mis partidas</h5>", unsafe_allow_html=True)
            df_dist_tiempo = df_anual.groupby("duracion_rango", observed=False).size().reset_index(name="Partidas")

            fig_dist = px.bar(
                df_dist_tiempo,
                x="duracion_rango",
                y="Partidas",
                labels={"duracion_rango": "Minutos"}
            )
            fig_dist.update_traces(marker_color="#00c853")
            fig_dist.update_layout(margin=dict(t=20, b=10, l=10, r=10), height=350)
            st.plotly_chart(fig_dist, use_container_width=True)

        # 2. CAMPEONES (Winrate Apilado 100%)
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Campeones</h5>", unsafe_allow_html=True)

            top_campeones = df_kda.head(6)["Campeón"].tolist()
            df_champs = df_anual[df_anual["champion"].isin(top_campeones)].copy()

            df_champs_wl = df_champs.groupby(["champion", "win"]).size().reset_index(name="count")
            df_champs_wl["Resultado"] = df_champs_wl["win"].map({True: "Victoria", False: "Derrota"})

            fig_champs = px.bar(
                df_champs_wl,
                y="champion",
                x="count",
                color="Resultado",
                orientation="h",
                color_discrete_map={"Victoria": "#00c853", "Derrota": "#d50000"},
                category_orders={
                    "Resultado": ["Victoria", "Derrota"],
                    "champion": list(reversed(top_campeones)),
                },
                text="count",
                labels={"champion": "yo.championName"}
            )

            fig_champs.update_layout(
                barmode="relative",
                barnorm="percent",
                xaxis_title="count ( yo.win )",
                showlegend=False,
                margin=dict(t=20, b=10, l=10, r=10),
                height=400
            )
            fig_champs.update_xaxes(ticksuffix="%")
            st.plotly_chart(fig_champs, use_container_width=True)

        # 3. WINRATE POR DÍA DE LA SEMANA
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Winrate</h5>", unsafe_allow_html=True)

            df_anual["dia_semana"] = df_anual["fecha"].dt.day_name()
            orden_dias_en = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

            df_wr_dia = (
                df_anual.groupby("dia_semana")
                .agg(Winrate=("win", "mean"), Partidas=("win", "count"))
                .reindex(orden_dias_en)
                .reset_index()
            )
            df_wr_dia["Winrate"] *= 100
            df_wr_dia["dia_semana"] = pd.Categorical(df_wr_dia["dia_semana"], categories=orden_dias_en, ordered=True)

            fig_wr_dia = px.bar(
                df_wr_dia,
                x="dia_semana",
                y="Winrate",
                color="Partidas",
                color_continuous_scale="Greens",
                text=df_wr_dia["Winrate"].round(2).astype(str) + "%",
                labels={"dia_semana": "info.gameCreation"},
            )
            fig_wr_dia.update_traces(textposition="outside")
            fig_wr_dia.update_yaxes(ticksuffix="%", range=[0, max(df_wr_dia["Winrate"].max(skipna=True) * 1.15, 10)])
            fig_wr_dia.update_layout(margin=dict(t=30, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig_wr_dia, use_container_width=True)

        # 4. LÍNEA (victorias/derrotas por posición)
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Línea</h5>", unsafe_allow_html=True)

            df_solo_roles = df_anual[df_anual["role"] != "UNKNOWN"]
            df_pos_wl = df_solo_roles.groupby(["role", "win"]).size().reset_index(name="count")
            df_pos_wl["Resultado"] = df_pos_wl["win"].map({True: "Victoria", False: "Derrota"})

            orden_roles = df_solo_roles["role"].value_counts().index.tolist()

            fig_linea_pos = px.bar(
                df_pos_wl,
                y="role",
                x="count",
                color="Resultado",
                orientation="h",
                color_discrete_map={"Victoria": "#00c853", "Derrota": "#d50000"},
                category_orders={"Resultado": ["Victoria", "Derrota"], "role": list(reversed(orden_roles))},
                text="count",
                labels={"role": "yo.individualPosition", "count": "count ( yo.win )"},
            )
            fig_linea_pos.update_traces(textposition="inside", insidetextanchor="middle")
            fig_linea_pos.update_layout(barmode="stack", showlegend=False, margin=dict(t=20, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig_linea_pos, use_container_width=True)

    # ==========================================
    # FILA FINAL — ANCHO COMPLETO
    # ==========================================
    st.write("")
    with st.container(border=True):
        st.markdown("<h5 style='text-align: center;'>Cantidad por Horas (Winrate color)</h5>", unsafe_allow_html=True)

        df_cnt_hora = df_anual.groupby("hora").agg(
            Partidas=("win", "count"),
            Winrate=("win", "mean"),
        ).reset_index()
        df_cnt_hora["Winrate"] *= 100
        df_cnt_hora = df_cnt_hora.sort_values("hora")
        df_cnt_hora["hora_str"] = df_cnt_hora["hora"].astype(int).astype(str)

        fig_cnt_hora = px.bar(
            df_cnt_hora,
            x="hora_str",
            y="Partidas",
            color="Winrate",
            color_continuous_scale="Blues",
            text="Partidas",
            labels={"Winrate": "Winrate", "hora_str": "Hora del día"},
        )
        fig_cnt_hora.update_traces(textposition="outside")
        fig_cnt_hora.update_xaxes(type="category")
        fig_cnt_hora.update_coloraxes(colorbar_ticksuffix="%")
        fig_cnt_hora.update_layout(margin=dict(t=30, b=10, l=10, r=10), height=350)
        st.plotly_chart(fig_cnt_hora, use_container_width=True)

    # ==========================================
    # FILA: Winrate semanal | Heatmap hora x día
    # ==========================================
    st.write("")
    col_semana, col_heatmap = st.columns(2)

    with col_semana:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Winrate</h5>", unsafe_allow_html=True)

            df_semana = (
                df_anual.set_index("fecha")
                .resample("W")
                .agg(Partidas=("win", "count"), Winrate=("win", "mean"))
                .reset_index()
            )
            df_semana = df_semana[df_semana["Partidas"] > 0]
            df_semana["Winrate"] *= 100

            fig_semana = go.Figure()
            fig_semana.add_trace(go.Bar(
                x=df_semana["fecha"],
                y=df_semana["Partidas"],
                name="Partidas",
                marker_color="#00c853",
                text=df_semana["Partidas"],
                textposition="outside",
                yaxis="y1",
            ))
            fig_semana.add_trace(go.Scatter(
                x=df_semana["fecha"],
                y=df_semana["Winrate"],
                name="Winrate",
                mode="lines+markers+text",
                line=dict(color="#1565c0", width=2),
                marker=dict(size=6, color="#1565c0"),
                text=df_semana["Winrate"].round(2).astype(str) + "%",
                textposition="top center",
                yaxis="y2",
            ))
            fig_semana.update_layout(
                xaxis=dict(title="info.gameCreation", tickformat="%d %b/%Y"),
                yaxis=dict(title="count ( _id )", side="left"),
                yaxis2=dict(title="mean ( yo.win )", overlaying="y", side="right", ticksuffix="%", range=[0, 100]),
                legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                margin=dict(t=30, b=10, l=10, r=10),
                height=380,
            )
            st.plotly_chart(fig_semana, use_container_width=True)

    with col_heatmap:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Winrate</h5>", unsafe_allow_html=True)

            df_anual["dia_semana_en"] = df_anual["fecha"].dt.day_name()
            orden_dias_en = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

            df_heat = df_anual.groupby(["hora", "dia_semana_en"])["win"].mean().reset_index()
            df_heat["win"] *= 100

            pivot = df_heat.pivot(index="hora", columns="dia_semana_en", values="win")
            pivot = pivot.reindex(columns=orden_dias_en).sort_index()
            pivot.index = [f"{h:02d}:00" for h in pivot.index]

            fig_heat = px.imshow(
                pivot,
                color_continuous_scale="Blues",
                labels=dict(x="info.gameCreation", y="hora", color="mean ( yo.win )"),
                aspect="auto",
            )
            fig_heat.update_xaxes(side="bottom")
            fig_heat.update_coloraxes(colorbar_ticksuffix="%")
            fig_heat.update_layout(margin=dict(t=30, b=10, l=10, r=10), height=380)
            st.plotly_chart(fig_heat, use_container_width=True)

    # ==========================================
    # FILA: Winrate por campeón según línea (4 columnas)
    # ==========================================
    def winrate_sinergia_por_linea(df_anual: pd.DataFrame, columna_champ: str, titulo: str, top_n: int = 10) -> None:
        df_validas = df_anual[df_anual[columna_champ].notna()]
        total_partidas = len(df_validas)

        st.markdown(
            f"<h5 style='text-align: center;'>Winrate {titulo} <span style='color: gray; font-weight: normal;'>({total_partidas} partidas)</span></h5>",
            unsafe_allow_html=True,
        )

        if df_validas.empty:
            st.info(f"No hay partidas con compañero identificado en {titulo}.")
            return

        resumen = df_validas.groupby(columna_champ).agg(
            Partidas=("win", "count"),
            Winrate=("win", "mean"),
        ).reset_index()

        resumen = resumen.sort_values(["Partidas", columna_champ], ascending=[False, True]).head(top_n)
        orden_champs = resumen[columna_champ].tolist()  # más jugado primero
        partidas_mostradas = int(resumen["Partidas"].sum())

        df_top = df_validas[df_validas[columna_champ].isin(orden_champs)]
        df_wl = df_top.groupby([columna_champ, "win"]).size().reset_index(name="count")
        df_wl["Resultado"] = df_wl["win"].map({True: "Victoria", False: "Derrota"})

        fig = px.bar(
            df_wl,
            y=columna_champ,
            x="count",
            color="Resultado",
            orientation="h",
            color_discrete_map={"Victoria": "#00c853", "Derrota": "#d50000"},
            category_orders={"Resultado": ["Victoria", "Derrota"]},
            text="count",
            labels={columna_champ: "championName", "count": "count ( win )"},
        )
        fig.update_traces(textposition="inside", insidetextanchor="middle")

        # Orden EXPLÍCITO con nuestro propio array — más fiable que "total ascending"
        fig.update_yaxes(
            categoryorder="array",
            categoryarray=list(reversed(orden_champs)),  # invertido: el primero del array se dibuja abajo
        )

        fig.update_layout(
            barmode="relative",
            barnorm="percent",
            showlegend=False,
            margin=dict(t=10, b=10, l=10, r=10),
            height=400,
        )
        fig.update_xaxes(ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)

        st.caption(f"Mostrando {partidas_mostradas} de {total_partidas} partidas totales (top {top_n} campeones).")

    st.write("")
    col_top, col_mid, col_adc, col_sup = st.columns(4)

    with col_top:
        with st.container(border=True):
            winrate_sinergia_por_linea(df_anual, "champ_top", "top")

    with col_mid:
        with st.container(border=True):
            winrate_sinergia_por_linea(df_anual, "champ_mid", "mid")

    with col_adc:
        with st.container(border=True):
            winrate_sinergia_por_linea(df_anual, "champ_adc", "ADC")

    with col_sup:
        with st.container(border=True):
            winrate_sinergia_por_linea(df_anual, "champ_support", "support")

    col_daño1, col_daño2 = st.columns([2, 1])

    with col_daño1:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Winrate Daño Mid</h5>", unsafe_allow_html=True)

            df_mid_compañero = df_anual[df_anual["champ_mid_damage_type"].notna()].copy()

            if df_mid_compañero.empty:
                st.info("No hay partidas con compañero de mid identificado.")
            else:
                df_daño_wl = df_mid_compañero.groupby(["champ_mid_damage_type", "win"]).size().reset_index(name="count")
                df_daño_wl["Resultado"] = df_daño_wl["win"].map({True: "Victoria", False: "Derrota"})

                orden_daño = df_mid_compañero["champ_mid_damage_type"].value_counts().index.tolist()

                fig_daño = px.bar(
                    df_daño_wl,
                    y="champ_mid_damage_type",
                    x="count",
                    color="Resultado",
                    orientation="h",
                    color_discrete_map={"Victoria": "#00c853", "Derrota": "#d50000"},
                    category_orders={"Resultado": ["Victoria", "Derrota"]},
                    labels={"champ_mid_damage_type": "Daño", "count": "Winrate"},
                )
                fig_daño.update_yaxes(categoryorder="array", categoryarray=list(reversed(orden_daño)))
                fig_daño.update_layout(
                    barmode="relative",
                    barnorm="percent",
                    showlegend=False,
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=380,
                )
                fig_daño.update_xaxes(ticksuffix="%")
                st.plotly_chart(fig_daño, use_container_width=True)

    with col_daño2:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Pickrate Daño Mid</h5>", unsafe_allow_html=True)

            df_mid_compañero_pr = df_anual[df_anual["champ_mid_damage_type"].notna()].copy()

            if df_mid_compañero_pr.empty:
                st.info("Sin datos.")
            else:
                df_pickrate = df_mid_compañero_pr["champ_mid_damage_type"].value_counts().reset_index()
                df_pickrate.columns = ["champ_mid_damage_type", "count"]

                fig_pickrate = px.pie(
                    df_pickrate,
                    values="count",
                    names="champ_mid_damage_type",
                    hole=0.55,
                    color="champ_mid_damage_type",
                    color_discrete_map={"AP": "#1565c0", "AD": "#d50000", "HYBRID": "#f57f17"},
                )
                fig_pickrate.update_traces(textinfo="percent+label", textposition="outside")
                fig_pickrate.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=380)
                st.plotly_chart(fig_pickrate, use_container_width=True)

    def tabla_objetivo_winrate(df_anual: pd.DataFrame, columna_kills: str, nombre_columna: str, titulo: str, max_kills: int = 6) -> None:
        st.markdown(f"<h5 style='text-align: center;'>{titulo}</h5>", unsafe_allow_html=True)

        df_tabla = df_anual.groupby(columna_kills).agg(
            Partidas=("win", "count"),
            Winrate=("win", "mean"),
        ).reset_index()

        df_tabla = df_tabla[df_tabla[columna_kills] <= max_kills].sort_values(columna_kills)
        df_tabla["Winrate"] = (df_tabla["Winrate"] * 100).round(2).astype(str) + "%"
        df_tabla = df_tabla.rename(columns={columna_kills: nombre_columna})
        df_tabla = df_tabla[[nombre_columna, "Winrate"]]

        st.dataframe(df_tabla, use_container_width=True, hide_index=True, height=280)


    st.write("")
    col_drag, col_grub, col_baron, col_herald = st.columns(4)

    with col_drag:
        with st.container(border=True):
            tabla_objetivo_winrate(df_anual, "dragon_kills", "Dragon Kills", "Dragon Kills")

    with col_grub:
        with st.container(border=True):
            tabla_objetivo_winrate(df_anual, "grub_kills", "Grubs Kills", "Grubs Kills")

    with col_baron:
        with st.container(border=True):
            tabla_objetivo_winrate(df_anual, "baron_kills", "Baron Kills", "Baron Kills")

    with col_herald:
        with st.container(border=True):
            tabla_objetivo_winrate(df_anual, "herald_kills", "Herald Kills", "Herald Kills", max_kills=2)

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
        "%Y-%m-%dT%H:%M:%S",   # 2026-01-02T20:30:00
        "%Y-%m-%d %H:%M:%S",   # 2026-04-17 13:00:00
        "%d/%m/%Y %H:%M:%S",   # 17/04/2026 18:00:00
        "%Y-%m-%d",            # 2026-01-02 (solo fecha, por si acaso)
        "%d/%m/%Y",            # 17/04/2026 (solo fecha, por si acaso)
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
    racha_sin_actual = rachas_sin.iloc[-1]["dias"] if not rachas_sin.empty and rachas_sin.iloc[-1]["fin"] == rachas["fin"].max() else 0
    racha_sin_maxima = int(rachas_sin["dias"].max()) if not rachas_sin.empty else 0
    racha_con_maxima = int(rachas_con["dias"].max()) if not rachas_con.empty else 0
    duracion_media = df["Duracion_min"].mean()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total registros", total_registros)
    col2.metric("Días con registro", dias_unicos)
    col3.metric("Racha sin (máx)", f"{racha_sin_maxima} días")
    col4.metric("Racha con (máx)", f"{racha_con_maxima} días")
    col5.metric("Duración media", f"{duracion_media:.1f} min" if not pd.isna(duracion_media) else "N/D")

    st.divider()

    # ==========================================
    # TIMELINE DE RACHAS (Gantt tipo semáforo)
    # ==========================================
    st.subheader("📅 Línea temporal de rachas")

    fig_timeline = go.Figure()
    for _, row in rachas.iterrows():
        color = "#00c853" if row["tipo"] == "Con registro" else "#d50000"
        fig_timeline.add_trace(go.Scatter(
            x=[row["inicio"], row["fin"] + pd.Timedelta(days=1)],
            y=[row["tipo"], row["tipo"]],
            mode="lines",
            line=dict(color=color, width=20),
            showlegend=False,
            hovertemplate=f"{row['tipo']}<br>{row['inicio'].date()} → {row['fin'].date()}<br>{row['dias']} días<extra></extra>",
        ))
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
            st.markdown("<h5 style='text-align: center;'>Frecuencia de rachas sin registro</h5>", unsafe_allow_html=True)

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
            st.markdown("<h5 style='text-align: center;'>Frecuencia de rachas con registro</h5>", unsafe_allow_html=True)

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
            st.markdown("<h5 style='text-align: center;'>Registros por día de la semana</h5>", unsafe_allow_html=True)
            orden_dias_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            dias_es = {
                "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
                "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo",
            }
            conteo_dia_semana = df["dia_semana_en"].value_counts().reindex(orden_dias_en).fillna(0).reset_index()
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
            st.markdown("<h5 style='text-align: center;'>Distribución por hora del día</h5>", unsafe_allow_html=True)
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
            st.markdown("<h5 style='text-align: center;'>Duración media por día de la semana</h5>", unsafe_allow_html=True)
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
        st.markdown("<h5 style='text-align: center;'>Mapa de calor: hora × día de la semana</h5>", unsafe_allow_html=True)

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
        fig_mensual.add_trace(go.Bar(
            x=resumen_mensual["año_mes"],
            y=resumen_mensual["registros"],
            name="Registros",
            marker_color="#4f46e5",
            yaxis="y1",
        ))
        fig_mensual.add_trace(go.Scatter(
            x=resumen_mensual["año_mes"],
            y=resumen_mensual["duracion_media"],
            name="Duración media (min)",
            mode="lines+markers",
            line=dict(color="#f57f17", width=2),
            yaxis="y2",
        ))
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
        st.markdown("<h5 style='text-align: center;'>Calendario de actividad</h5>", unsafe_allow_html=True)

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

def main() -> None:
    st.title("📊 Mi panel de vida")
    st.markdown("Un lugar para ver pasos, LoL y más métricas personales en pestañas separadas.")
    
    tab_pasos, tab_lol, tab_registro = st.tabs(["🚶 Pasos", "🎮 LoL", "📋 Registro"])

    with tab_pasos:
        render_steps_tab()

    with tab_lol:
        render_lol_tab()

    with tab_registro:
        render_registro_tab()

if __name__ == "__main__":
    main()