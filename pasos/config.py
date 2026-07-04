import os
from datetime import date
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
import streamlit as st

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
            value = valor.strip().strip('"').strip("'")
            os.environ.setdefault(clave, value)


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
