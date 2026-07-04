from typing import Any
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard_config import (
    obtener_coleccion,
    LOL_COLLECTION_NAME,
    LOL_PUUID,
    LOL_RIOT_ID,
    duration_to_seconds,
)



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
        ultimo = collection.find_one(
            {},
            {"_id": 0, "info.gameCreation": 1, "metadata.matchId": 1},
            sort=[("info.gameCreation", -1)],
        )
        client.close()
        return ("lol", total, ultimo)
    except Exception:
        return ("lol-error",)


def extraer_fila_lol(
    match_data: dict[str, Any], puuid: str | None, riot_id: str | None
) -> dict[str, Any] | None:
    info = match_data.get("info", {})
    participantes = info.get("participants") or []

    participante = None
    if puuid:
        participante = next((p for p in participantes if p.get("puuid") == puuid), None)

    if not participante and riot_id:
        participante = next(
            (
                p
                for p in participantes
                if p.get("riotIdGameName") == riot_id or p.get("summonerName") == riot_id
            ),
            None,
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
                p
                for p in participantes
                if int(p.get("teamId") or 0) == team_id
                and p.get("puuid") != mi_puuid
                and (p.get("teamPosition") or p.get("individualPosition")) == role_code
            ),
            None,
        )
        compañeros[col] = companero.get("championName") if companero else None
        compañeros[f"{col}_damage_type"] = (
            companero.get("champion_damage_type") if companero else None
        )

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
        "role": (
            participante.get("teamPosition")
            or participante.get("individualPosition")
            or participante.get("role")
            or "UNKNOWN"
        ),
        "win": bool(participante.get("win")),
        "lado": lado,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kda": (kills + assists) / max(1, deaths),
        "damage": int(participante.get("totalDamageDealtToChampions") or 0),
        "vision": int(participante.get("visionScore") or 0),
        "gold": int(participante.get("goldEarned") or 0),
        "cs": int(participante.get("totalMinionsKilled") or 0)
        + int(participante.get("neutralMinionsKilled") or 0),
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
        condiciones.append({"info.participants.summonerName": riot_id})  # Por si hay registros antiguos

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
    df["cs_min"] = df.apply(
        lambda row: (row["cs"] / row["duration_minutes"]) if row["duration_minutes"] else 0, axis=1
    )
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

    años_disponibles = ["Todos"] + sorted(
        df["fecha"].dt.year.dropna().astype(int).unique(), reverse=True
    )
    col_filtro1, col_filtro2 = st.columns([1, 1])

    with col_filtro1:
        año_seleccionado = st.selectbox("Año", años_disponibles, index=0)

    if año_seleccionado == "Todos":
        df_anual = df.copy()
    else:
        df_anual = df[df["fecha"].dt.year == año_seleccionado].copy()

    roles_disponibles = ["Todos"] + sorted(
        df_anual["role"].fillna("UNKNOWN").astype(str).unique().tolist()
    )

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
        df_anual["duration_minutes"], bins=bins_duracion, labels=labels_duracion, right=False
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
        st.markdown(
            f"<div style='text-align: center; margin-top: 10px;'><b>Cantidad de partidas</b><br><span style='font-size: 3rem; font-weight: bold;'>{partidas}</span></div>",
            unsafe_allow_html=True,
        )

    with f1_col2.container(height=ALTURA_FILA_1, border=True):
        st.markdown(
            f"<div style='text-align: center; margin-top: 10px;'><b>Media de tiempo</b><br><span style='font-size: 2.5rem; font-weight: bold;'>{duracion_prom:.1f}</span><span style='font-size: 1.5rem;'> mins</span></div>",
            unsafe_allow_html=True,
        )

    with f1_col3.container(height=ALTURA_FILA_1, border=True):
        st.markdown(
            f"<div style='text-align: center; margin-top: 10px;'><b>KDA</b><br><span style='font-size: 3rem; font-weight: bold;'>{kda_prom:.2f}</span></div>",
            unsafe_allow_html=True,
        )

    with f1_col4.container(height=ALTURA_FILA_1, border=True):
        st.markdown(
            f"""
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
        """,
            unsafe_allow_html=True,
        )

    st.write("")  # Pequeño espacio

    # === FILA 2 ===
    f2_col1, f2_col2, f2_col3, f2_col4 = st.columns(4)

    with f2_col1.container(height=ALTURA_FILA_2, border=True):
        st.markdown(
            f"<div style='text-align: center; margin-top: 50px;'><b>Winrate</b><br><span style='font-size: 3rem; font-weight: bold;'>{winrate:.2f}%</span></div>",
            unsafe_allow_html=True,
        )

    with f2_col2.container(height=ALTURA_FILA_2, border=True):
        st.markdown("<div style='text-align: center;'><b>Winrate</b></div>", unsafe_allow_html=True)
        df_w = pd.DataFrame(
            {"Res": ["Victoria", "Derrota"], "Val": [victorias, partidas - victorias]}
        )
        fig_w = px.pie(
            df_w,
            values="Val",
            names="Res",
            hole=0.6,
            color="Res",
            color_discrete_map={"Victoria": "#00c853", "Derrota": "#d50000"},
        )
        fig_w.update_traces(textinfo="percent", textposition="outside", hoverinfo="label+value")
        # Ajustamos el height de la gráfica para que quepa bien en el contenedor fijo
        fig_w.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=200)
        st.plotly_chart(fig_w, use_container_width=True)

    with f2_col3.container(height=ALTURA_FILA_2, border=True):
        st.markdown("<div style='text-align: center;'><b>Lado</b></div>", unsafe_allow_html=True)
        lados_count = df_anual["lado"].value_counts().reset_index()
        lados_count.columns = ["Lado", "Cantidad"]
        fig_l = px.pie(
            lados_count,
            values="Cantidad",
            names="Lado",
            hole=0.6,
            color="Lado",
            color_discrete_map={"Azul": "#0288d1", "Rojo": "#d50000", "Desconocido": "#9e9e9e"},
        )
        fig_l.update_traces(textinfo="percent", textposition="outside", hoverinfo="label+value")
        fig_l.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=200)
        st.plotly_chart(fig_l, use_container_width=True)

    with f2_col4.container(height=ALTURA_FILA_2, border=True):
        st.markdown(
            "<div style='text-align: center;'><b>Winrate Lado</b></div>", unsafe_allow_html=True
        )

        # Pasamos el winrate para el tamaño visual del quesito, y una columna extra para el texto
        df_wl = pd.DataFrame(
            {
                "Lado": ["Azul", "Rojo"],
                "Winrate_Visual": [winrate_azul, winrate_rojo],
                "Texto_Mostrar": [f"{winrate_azul:.2f}%", f"{winrate_rojo:.2f}%"],
            }
        )

        fig_wl = px.pie(
            df_wl,
            values="Winrate_Visual",
            names="Lado",
            hole=0.6,
            color="Lado",
            color_discrete_map={"Azul": "#0288d1", "Rojo": "#d50000"},
        )

        # Usamos textinfo='text' para obligar a Plotly a usar nuestra columna "Texto_Mostrar"
        fig_wl.update_traces(
            text=df_wl["Texto_Mostrar"],
            textinfo="text",
            textposition="outside",
            hoverinfo="label+text",
        )
        fig_wl.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=200)

        st.plotly_chart(fig_wl, use_container_width=True)

    st.write("")

    # === FILA 3 ===
    f3_col1, f3_col2 = st.columns(2)
    with f3_col1.container(border=True):
        st.markdown(
            f"<div style='text-align: center;'><b>Daño medio</b><br><span style='font-size: 2rem;'>{damage_prom:,}</span></div>",
            unsafe_allow_html=True,
        )
    with f3_col2.container(border=True):
        st.markdown(
            f"<div style='text-align: center;'><b>CS / Minuto</b><br><span style='font-size: 2rem;'>{cs_min_prom:.2f}</span></div>",
            unsafe_allow_html=True,
        )

    st.divider()
    col_izq, col_der = st.columns(2)

    # ==========================================
    # COLUMNA IZQUIERDA
    # ==========================================
    with col_izq:
        # 1. TABLA KDA
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>KDA</h5>", unsafe_allow_html=True)
            df_kda = (
                df_anual.groupby("champion")
                .agg(
                    Partidas=("win", "count"),
                    Kills=("kills", "mean"),
                    Deaths=("deaths", "mean"),
                    Assist=("assists", "mean"),
                )
                .reset_index()
            )

            df_kda["KDA"] = (df_kda["Kills"] + df_kda["Assist"]) / df_kda["Deaths"].replace(0, 1)
            df_kda = df_kda.sort_values("Partidas", ascending=False).round(2)
            df_kda = df_kda.rename(columns={"champion": "Campeón"})

            st.dataframe(df_kda, use_container_width=True, hide_index=True, height=250)

        # 2. WINRATE POR MINUTOS
        with st.container(border=True):
            st.markdown(
                "<h5 style='text-align: center;'>Winrate por minutos</h5>", unsafe_allow_html=True
            )
            df_wr_min = (
                df_anual.groupby("duracion_rango", observed=False)["win"]
                .mean()
                .reset_index(name="Winrate")
            )
            df_wr_min["Winrate"] *= 100

            fig_wr_min = px.line(
                df_wr_min,
                x="duracion_rango",
                y="Winrate",
                markers=True,
                labels={"duracion_rango": "duracion", "Winrate": "Winrate"},
            )
            fig_wr_min.update_traces(line_color="#00c853", marker=dict(size=8), connectgaps=True)
            fig_wr_min.update_yaxes(ticksuffix="%")
            fig_wr_min.update_xaxes(tickangle=-90)
            fig_wr_min.update_layout(margin=dict(t=20, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig_wr_min, use_container_width=True)

        # 3. WINRATE POR HORAS
        with st.container(border=True):
            st.markdown(
                "<h5 style='text-align: center;'>Winrate por Horas (Cantidad color)</h5>",
                unsafe_allow_html=True,
            )
            df_wr_hora = (
                df_anual.groupby("hora")
                .agg(Winrate=("win", "mean"), Partidas=("win", "count"))
                .reset_index()
            )
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
            fig_hora.update_yaxes(
                ticksuffix="%", range=[0, max(df_wr_hora["Winrate"].max() * 1.15, 10)]
            )
            fig_hora.update_xaxes(type="category", title="hora")
            fig_hora.update_layout(margin=dict(t=30, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig_hora, use_container_width=True)

        # 4. DINERO POR POSITION
        with st.container(border=True):
            st.markdown(
                "<h5 style='text-align: center;'>Dinero por position</h5>", unsafe_allow_html=True
            )

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
                labels={
                    "duration_minutes": "duracion",
                    "gold": "yo.goldEarned",
                    "role": "yo.individualPosition",
                },
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
            st.markdown(
                "<h5 style='text-align: center;'>Distribución del tiempo de mis partidas</h5>",
                unsafe_allow_html=True,
            )
            df_dist_tiempo = (
                df_anual.groupby("duracion_rango", observed=False)
                .size()
                .reset_index(name="Partidas")
            )

            fig_dist = px.bar(
                df_dist_tiempo, x="duracion_rango", y="Partidas", labels={"duracion_rango": "Minutos"}
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
                labels={"champion": "yo.championName"},
            )

            fig_champs.update_layout(
                barmode="relative",
                barnorm="percent",
                xaxis_title="count ( yo.win )",
                showlegend=False,
                margin=dict(t=20, b=10, l=10, r=10),
                height=400,
            )
            fig_champs.update_xaxes(ticksuffix="%")
            st.plotly_chart(fig_champs, use_container_width=True)

        # 3. WINRATE POR DÍA DE LA SEMANA
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Winrate</h5>", unsafe_allow_html=True)

            df_anual["dia_semana"] = df_anual["fecha"].dt.day_name()
            orden_dias_en = [
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
            ]

            df_wr_dia = (
                df_anual.groupby("dia_semana")
                .agg(Winrate=("win", "mean"), Partidas=("win", "count"))
                .reindex(orden_dias_en)
                .reset_index()
            )
            df_wr_dia["Winrate"] *= 100
            df_wr_dia["dia_semana"] = pd.Categorical(
                df_wr_dia["dia_semana"], categories=orden_dias_en, ordered=True
            )

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
            fig_wr_dia.update_yaxes(
                ticksuffix="%", range=[0, max(df_wr_dia["Winrate"].max(skipna=True) * 1.15, 10)]
            )
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
                category_orders={
                    "Resultado": ["Victoria", "Derrota"],
                    "role": list(reversed(orden_roles)),
                },
                text="count",
                labels={"role": "yo.individualPosition", "count": "count ( yo.win )"},
            )
            fig_linea_pos.update_traces(textposition="inside", insidetextanchor="middle")
            fig_linea_pos.update_layout(
                barmode="stack", showlegend=False, margin=dict(t=20, b=10, l=10, r=10), height=300
            )
            st.plotly_chart(fig_linea_pos, use_container_width=True)

    # ==========================================
    # FILA FINAL — ANCHO COMPLETO
    # ==========================================
    st.write("")
    with st.container(border=True):
        st.markdown(
            "<h5 style='text-align: center;'>Cantidad por Horas (Winrate color)</h5>",
            unsafe_allow_html=True,
        )

        df_cnt_hora = (
            df_anual.groupby("hora")
            .agg(
                Partidas=("win", "count"),
                Winrate=("win", "mean"),
            )
            .reset_index()
        )
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
            fig_semana.add_trace(
                go.Bar(
                    x=df_semana["fecha"],
                    y=df_semana["Partidas"],
                    name="Partidas",
                    marker_color="#00c853",
                    text=df_semana["Partidas"],
                    textposition="outside",
                    yaxis="y1",
                )
            )
            fig_semana.add_trace(
                go.Scatter(
                    x=df_semana["fecha"],
                    y=df_semana["Winrate"],
                    name="Winrate",
                    mode="lines+markers+text",
                    line=dict(color="#1565c0", width=2),
                    marker=dict(size=6, color="#1565c0"),
                    text=df_semana["Winrate"].round(2).astype(str) + "%",
                    textposition="top center",
                    yaxis="y2",
                )
            )
            fig_semana.update_layout(
                xaxis=dict(title="info.gameCreation", tickformat="%d %b/%Y"),
                yaxis=dict(title="count ( _id )", side="left"),
                yaxis2=dict(
                    title="mean ( yo.win )", overlaying="y", side="right", ticksuffix="%", range=[0, 100]
                ),
                legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                margin=dict(t=30, b=10, l=10, r=10),
                height=380,
            )
            st.plotly_chart(fig_semana, use_container_width=True)

    with col_heatmap:
        with st.container(border=True):
            st.markdown("<h5 style='text-align: center;'>Winrate</h5>", unsafe_allow_html=True)

            df_anual["dia_semana_en"] = df_anual["fecha"].dt.day_name()
            orden_dias_en = [
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
            ]

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
    def winrate_sinergia_por_linea(
        df_anual: pd.DataFrame, columna_champ: str, titulo: str, top_n: int = 10
    ) -> None:
        df_validas = df_anual[df_anual[columna_champ].notna()]
        total_partidas = len(df_validas)

        st.markdown(
            f"<h5 style='text-align: center;'>Winrate {titulo} <span style='color: gray; font-weight: normal;'>({total_partidas} partidas)</span></h5>",
            unsafe_allow_html=True,
        )

        if df_validas.empty:
            st.info(f"No hay partidas con compañero identificado en {titulo}.")
            return

        resumen = (
            df_validas.groupby(columna_champ)
            .agg(
                Partidas=("win", "count"),
                Winrate=("win", "mean"),
            )
            .reset_index()
        )

        resumen = resumen.sort_values(
            ["Partidas", columna_champ], ascending=[False, True]
        ).head(top_n)
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
            categoryarray=list(reversed(orden_champs)),  # invertido: el primero se dibuja abajo
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

        st.caption(
            f"Mostrando {partidas_mostradas} de {total_partidas} partidas totales (top {top_n} campeones)."
        )

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
            st.markdown(
                "<h5 style='text-align: center;'>Winrate Daño Mid</h5>", unsafe_allow_html=True
            )

            df_mid_compañero = df_anual[df_anual["champ_mid_damage_type"].notna()].copy()

            if df_mid_compañero.empty:
                st.info("No hay partidas con compañero de mid identificado.")
            else:
                df_daño_wl = (
                    df_mid_compañero.groupby(["champ_mid_damage_type", "win"])
                    .size()
                    .reset_index(name="count")
                )
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
            st.markdown(
                "<h5 style='text-align: center;'>Pickrate Daño Mid</h5>", unsafe_allow_html=True
            )

            df_mid_compañero_pr = df_anual[df_anual["champ_mid_damage_type"].notna()].copy()

            if df_mid_compañero_pr.empty:
                st.info("Sin datos.")
            else:
                df_pickrate = (
                    df_mid_compañero_pr["champ_mid_damage_type"].value_counts().reset_index()
                )
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
                fig_pickrate.update_layout(
                    showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=380
                )
                st.plotly_chart(fig_pickrate, use_container_width=True)

    def tabla_objetivo_winrate(
        df_anual: pd.DataFrame,
        columna_kills: str,
        nombre_columna: str,
        titulo: str,
        max_kills: int = 6,
    ) -> None:
        st.markdown(f"<h5 style='text-align: center;'>{titulo}</h5>", unsafe_allow_html=True)

        df_tabla = (
            df_anual.groupby(columna_kills)
            .agg(
                Partidas=("win", "count"),
                Winrate=("win", "mean"),
            )
            .reset_index()
        )

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
            tabla_objetivo_winrate(
                df_anual, "herald_kills", "Herald Kills", "Herald Kills", max_kills=2
            )
