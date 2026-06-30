import os
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

# 1. Configuración de la página
st.set_page_config(page_title="Control de Actividad Física", page_icon="🏃‍♂️", layout="wide")
st.title("🏃‍♂️ Mi Panel de Actividad Física Completo")
st.markdown("Análisis macroscópico de todo el histórico y desglose diario con objetivos configurables (Desde 2025).")

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

MESES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
    7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}


def cargar_env_local(ruta='.env'):
    ruta_completa = ROOT_DIR / ruta

    if not ruta_completa.exists():
        return

    with open(ruta_completa, 'r', encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith('#') or '=' not in linea:
                continue

            clave, valor = linea.split('=', 1)
            clave = clave.strip()
            valor = valor.strip().strip('"').strip("'")
            os.environ.setdefault(clave, valor)


cargar_env_local()

def config_value(nombre, defecto=None):
    valor = os.getenv(nombre)
    if valor:
        return valor
    try:
        return st.secrets.get(nombre, defecto)
    except Exception:
        return defecto


MONGODB_URI = config_value('MONGODB_URI')
DB_NAME = config_value('DB_NAME', 'lol')
COLLECTION_NAME = config_value('COLLECTION_NAME', 'pasos')

if not MONGODB_URI:
    st.error("❌ Falta configurar `MONGODB_URI`. Este panel ahora solo lee desde MongoDB.")
    st.stop()


def cargar_desde_mongo():
    from pymongo import MongoClient

    client = MongoClient(MONGODB_URI)
    collection = client[DB_NAME][COLLECTION_NAME]
    documentos = list(collection.find({}, {'_id': 0}).sort('fecha', 1))
    client.close()
    return pd.DataFrame(documentos)


def firma_datos():
    try:
        from pymongo import MongoClient

        client = MongoClient(MONGODB_URI)
        collection = client[DB_NAME][COLLECTION_NAME]
        total = collection.count_documents({})
        ultimo = collection.find_one({}, {'_id': 0, 'fecha': 1, 'pasos': 1}, sort=[('fecha', -1)])
        client.close()
        return ('mongo', total, ultimo)
    except Exception:
        return ('mongo-error',)


@st.cache_data(ttl=300)
def cargar_datos_completos(_firma):
    df = cargar_desde_mongo()

    if 'pasos_totales' not in df.columns and 'pasos' in df.columns:
        df = df.rename(columns={'pasos': 'pasos_totales'})

    df['fecha'] = pd.to_datetime(df['fecha'])
    
    # Filtro temporal (2025 en adelante)
    df = df[df['fecha'] >= '2025-01-01']
    
    # Rellenar el calendario ininterrumpido
    df.set_index('fecha', inplace=True)
    if not df.empty:
        calendario_continuo = pd.date_range(start=df.index.min(), end=df.index.max())
        df = df.reindex(calendario_continuo, fill_value=0)
    df = df.reset_index()
    df.rename(columns={'index': 'fecha'}, inplace=True)

    # Imputación basada en percentiles
    mascara_ceros = df['pasos_totales'] == 0
    total_ceros = mascara_ceros.sum()
    
    metricas_imputacion = {
        "dias_rellenados": int(total_ceros),
        "limite_inf": 0,
        "limite_sup": 0
    }
    
    if total_ceros > 0:
        dias_reales = df[df['pasos_totales'] > 0]['pasos_totales']
        
        if not dias_reales.empty:
            limite_inferior = int(dias_reales.quantile(0.05))
            limite_superior = int(dias_reales.quantile(0.15))
            
            if limite_inferior >= limite_superior:
                limite_superior = limite_inferior + 150
        else:
            limite_inferior, limite_superior = 200, 500
            
        metricas_imputacion["limite_inf"] = limite_inferior
        metricas_imputacion["limite_sup"] = limite_superior
            
        df.loc[mascara_ceros, 'pasos_totales'] = np.random.randint(
            low=limite_inferior, 
            high=limite_superior, 
            size=total_ceros
        )

    # Columnas de soporte temporal
    df['año'] = df['fecha'].dt.year
    df['mes_num'] = df['fecha'].dt.month
    df['año_mes'] = df['fecha'].dt.to_period('M').astype(str)
    df['dia_str'] = df['fecha'].dt.strftime('%d')
    
    dias_es = {
        'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
        'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    df['dia_semana'] = df['fecha'].dt.day_name().map(dias_es)
    
    return df, metricas_imputacion

try:
    df, metricas = cargar_datos_completos(firma_datos())
    
    if df.empty:
        st.warning("⚠️ No se encontraron datos a partir del 1 de enero de 2025.")
    else:
        # =========================================================================
        # BARRA LATERAL (FILTROS, CONFIGURACIÓN DE META Y AUDITORÍA)
        # =========================================================================
        st.sidebar.header("Configuración del Panel")
        
        # Filtros de Fecha
        años_disponibles = sorted(df['año'].unique(), reverse=True)
        año_actual = date.today().year
        indice_anio_actual = años_disponibles.index(año_actual) if año_actual in años_disponibles else 0
        año_seleccionado = st.sidebar.selectbox("Selecciona el Año", años_disponibles, index=indice_anio_actual)
        
        df_filtrado_año = df[df['año'] == año_seleccionado]
        meses_disponibles = sorted(df_filtrado_año['mes_num'].unique())
        mes_actual = date.today().month
        indice_mes_actual = meses_disponibles.index(mes_actual) if mes_actual in meses_disponibles else 0
        mes_seleccionado_num = st.sidebar.selectbox(
            "Selecciona el Mes",
            options=meses_disponibles,
            index=indice_mes_actual,
            format_func=lambda x: MESES_ES[x]
        )
        
        df_mes_especifico = df_filtrado_año[df_filtrado_año['mes_num'] == mes_seleccionado_num].sort_values('fecha')
        nombre_mes = MESES_ES[mes_seleccionado_num]
        
        st.sidebar.divider()
        
        # Slider interactivo para configurar la Meta Diaria
        meta_pasos = st.sidebar.slider(
            "🎯 Configura tu Meta Diaria", 
            min_value=3000, max_value=20000, value=10000, step=500
        )
        
        st.sidebar.divider()
        
        # Panel de auditoría de percentiles
        with st.sidebar.expander("🛠️ Auditoría de Imputación", expanded=False):
            st.markdown(f"**Días vacíos rellenados:** {metricas['dias_rellenados']}")
            if metricas['dias_rellenados'] > 0:
                st.markdown(f"**Percentil 5 (Suelo):** {metricas['limite_inf']} pasos")
                st.markdown(f"**Percentil 15 (Techo):** {metricas['limite_sup']} pasos")

        # =========================================================================
        # SECCIÓN 1: VISTAS GENERALES HISTÓRICAS
        # =========================================================================
        st.header("🌍 Resumen Macroscópico Histórico (2025+)")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Días Analizados", f"{len(df)} días")
        col2.metric("Promedio Diario Real", f"{int(df['pasos_totales'].mean()):,} pasos")
        col3.metric("Récord Absoluto", f"{int(df['pasos_totales'].max()):,} pasos")
        col4.metric("Pasos Acumulados", f"{int(df['pasos_totales'].sum()):,}")
        
        st.subheader("📈 Línea de Tiempo Absoluta")
        fig_linea = px.line(df, x='fecha', y='pasos_totales', labels={'fecha': 'Fecha', 'pasos_totales': 'Pasos Totales'}, color_discrete_sequence=['#4f46e5'])
        fig_linea.update_xaxes(rangeslider_visible=True)
        fig_linea.update_layout(hovermode="x unified")
        st.plotly_chart(fig_linea, use_container_width=True)
        
        st.divider()

        # =========================================================================
        # SECCIÓN 2: VISTA DIARIA DETALLADA + TASA DE ÉXITO DE META
        # =========================================================================
        st.header(f"🔍 Análisis Detallado: {nombre_mes} {año_seleccionado}")
        
        if not df_mes_especifico.empty:
            media_mes = int(round(df_mes_especifico['pasos_totales'].mean()))
            total_mes = int(df_mes_especifico['pasos_totales'].sum())
            
            dias_cumplidos = len(df_mes_especifico[df_mes_especifico['pasos_totales'] >= meta_pasos])
            dias_totales_mes = len(df_mes_especifico)
            porcentaje_exito = int(round((dias_cumplidos / dias_totales_mes) * 100))
            
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric(f"Media en {nombre_mes}", f"{media_mes:,} pasos/día")
            col_m2.metric(f"Total acumulado", f"{total_mes:,} pasos")
            col_m3.metric(f"Días Meta Cumplida", f"{dias_cumplidos} / {dias_totales_mes} días")
            
            col_grafica, col_anillo = st.columns([2.2, 1])
            
            with col_grafica:
                fig_diario = px.bar(
                    df_mes_especifico, x='dia_str', y='pasos_totales',
                    labels={'dia_str': 'Día del Mes', 'pasos_totales': 'Pasos Totales'},
                    color='pasos_totales', color_continuous_scale='Purples'
                )
                
                fig_diario.add_hline(
                    y=media_mes, line_dash="dash", line_color="#ef4444", line_width=2,
                    annotation_text=f"Media: {media_mes:,}", annotation_position="top left"
                )
                
                fig_diario.add_hline(
                    y=meta_pasos, line_dash="dot", line_color="#10b981", line_width=2.5,
                    annotation_text=f"Meta: {meta_pasos:,}", annotation_position="top right"
                )
                
                fig_diario.update_layout(xaxis_tickmode='linear', hovermode="x unified", coloraxis_showscale=False)
                st.plotly_chart(fig_diario, use_container_width=True)
                
            with col_anillo:
                st.markdown("<h5 style='text-align: center; color: #374151;'>🎯 Tasa de Éxito del Objetivo</h5>", unsafe_allow_html=True)
                
                datos_meta = pd.DataFrame({
                    'Estado': ['Meta Cumplida', 'Por Debajo'],
                    'Días': [dias_cumplidos, dias_totales_mes - dias_cumplidos]
                })
                
                fig_meta = px.pie(
                    datos_meta, values='Días', names='Estado', hole=0.62,
                    color='Estado', color_discrete_map={'Meta Cumplida': '#10b981', 'Por Debajo': '#e2e8f0'}
                )
                
                fig_meta.update_layout(
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
                    margin=dict(t=10, b=10, l=10, r=10),
                    annotations=[dict(text=f"{porcentaje_exito}%", x=0.5, y=0.5, font_size=26, font_color="#10b981", font_family="Arial", showarrow=False)]
                )
                st.plotly_chart(fig_meta, use_container_width=True)
        else:
            st.warning("No hay registros disponibles para el periodo seleccionado.")
            
        st.divider()

        # =========================================================================
        # SECCIÓN 3: PATRONES Y TENDENCIAS MACRO
        # =========================================================================
        st.header("📊 Patrones y Tendencias de Comportamiento")
        
        # 🔥 NUEVO: Histograma de frecuencia (Distribución general)
        st.subheader("📈 Distribución de tu Actividad (¿Cuál es tu día típico?)")
        fig_hist = px.histogram(
            df, x="pasos_totales", nbins=40,
            labels={'pasos_totales': 'Rango de Pasos', 'count': 'Número de Días'},
            color_discrete_sequence=['#8b5cf6']
        )
        fig_hist.update_layout(bargap=0.1, yaxis_title="Días registrados")
        st.plotly_chart(fig_hist, use_container_width=True)
        
        st.write("") # Pequeño espaciado visual

        col_izq, col_der = st.columns(2)

        with col_izq:
            st.subheader("📅 Promedio Diario por Mes")
            pasos_mes_global = df.groupby('año_mes')['pasos_totales'].mean().round().astype(int).reset_index()
            fig_mes_global = px.bar(
                pasos_mes_global, x='año_mes', y='pasos_totales',
                labels={'año_mes': 'Mes / Año', 'pasos_totales': 'Promedio'},
                color='pasos_totales', color_continuous_scale='viridis'
            )
            fig_mes_global.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_mes_global, use_container_width=True)

        with col_der:
            st.subheader("📆 Rendimiento por Día de la Semana")
            orden_dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
            pasos_dia_semana = df.groupby('dia_semana')['pasos_totales'].mean().round().astype(int).reindex(orden_dias).reset_index()
            fig_dias = px.bar(
                pasos_dia_semana, x='dia_semana', y='pasos_totales',
                labels={'dia_semana': 'Día', 'pasos_totales': 'Promedio'},
                color='pasos_totales', color_continuous_scale='teal'
            )
            st.plotly_chart(fig_dias, use_container_width=True)

except Exception as e:
    st.error(f"❌ No se pudieron cargar los datos desde MongoDB: {e}")
