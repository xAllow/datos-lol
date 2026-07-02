import os
import io
import glob
from pathlib import Path
import pandas as pd
import sys
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseDownload

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
# =========================================================
# 🔐 CONFIG
# =========================================================

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
SERVICE_ACCOUNT_FILE = BASE_DIR / 'credentials.json'
FOLDER_ID = '1cZDKzh8LzYPwOXKtgL6-SwuM8UkYnWWV'
CARPETA_BOOTSTRAP = './drive_csv'


# =========================================================
# ☁️ GOOGLE DRIVE
# =========================================================

def conectar_drive():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)


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

MONGODB_URI = os.getenv('MONGODB_URI')
DB_NAME = os.getenv('DB_NAME', 'lol')
COLLECTION_NAME = os.getenv('COLLECTION_NAME', 'pasos')
RAW_COLLECTION_NAME = os.getenv('RAW_COLLECTION_NAME', 'pasos_raw')


def listar_csv(service):
    files = []
    page_token = None

    while True:
        response = service.files().list(
            q=f"'{FOLDER_ID}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, size, modifiedTime)",
            pageToken=page_token
        ).execute()

        files.extend(response.get('files', []))
        page_token = response.get('nextPageToken')

        if not page_token:
            break

    print(f"📂 Total archivos en Drive: {len(files)}")
    return files


def descargar_archivo(service, file_id, destino):
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(destino, 'wb')
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    fh.close()


def descargar_csv_como_texto(service, file_id):
    buffer = io.BytesIO()
    request = service.files().get_media(fileId=file_id)
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    contenido = buffer.getvalue()
    if not contenido:
        return None

    return io.StringIO(contenido.decode('utf-8-sig', errors='replace'))


# =========================================================
# 🧠 MONGO
# =========================================================

def obtener_collecciones_mongo():
    if not MONGODB_URI:
        return None, None, None

    try:
        from pymongo import MongoClient, UpdateOne
    except ImportError:
        print("MongoDB no disponible: instala pymongo para subir datos a Mongo.")
        return None, None, None

    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    return client, db[RAW_COLLECTION_NAME], db[COLLECTION_NAME]


def archivo_ya_sincronizado(raw_collection, file_id, modified_time):
    if not file_id:
        return False

    return raw_collection.find_one(
        {'file_id': file_id, 'modifiedTime': modified_time},
        {'_id': 1}
    ) is not None


def guardar_en_mongo(df):
    client, _, collection = obtener_collecciones_mongo()
    if client is None or collection is None:
        return

    from pymongo import UpdateOne

    if df is None or df.empty:
        client.close()
        return

    operaciones = []
    for registro in df.to_dict('records'):
        fecha = str(registro['fecha'])
        pasos = int(registro['pasos'])
        operaciones.append(
            UpdateOne(
                {'fecha': fecha},
                {'$set': {'fecha': fecha, 'pasos': pasos}},
                upsert=True
            )
        )

    if operaciones:
        collection.bulk_write(operaciones)
        print(f"MongoDB actualizado: {len(operaciones)} dias en {DB_NAME}.{COLLECTION_NAME}")

    client.close()


def guardar_raw_en_mongo(raw_collection, file_id, nombre_archivo, modified_time, df):
    if df is None or df.empty:
        return 0

    from pymongo import UpdateOne

    operaciones = []
    for registro in df.to_dict('records'):
        fecha = str(registro['fecha'])
        pasos = int(registro['pasos'])
        operaciones.append(
            UpdateOne(
                {'file_id': file_id, 'fecha': fecha},
                {
                    '$set': {
                        'file_id': file_id,
                        'name': nombre_archivo,
                        'modifiedTime': modified_time,
                        'fecha': fecha,
                        'pasos': pasos,
                    }
                },
                upsert=True
            )
        )

    if operaciones:
        raw_collection.bulk_write(operaciones)

    return len(operaciones)


def procesar_archivo_y_guardar(raw_collection, archivo, lector_csv):
    nombre_archivo = archivo['name']
    file_id = archivo['id']
    modified_time = str(archivo.get('modifiedTime') or '')

    if archivo_ya_sincronizado(raw_collection, file_id, modified_time):
        return False

    df = extraer_df_diario(nombre_archivo, lector_csv)
    if df is None or df.empty:
        return False

    raw_collection.delete_many({'file_id': file_id})
    guardar_raw_en_mongo(raw_collection, file_id, nombre_archivo, modified_time, df)
    return True


def recalcular_consolidado_desde_raw(raw_collection, consolidated_collection):
    documentos = list(raw_collection.find({}, {'_id': 0, 'fecha': 1, 'pasos': 1}))
    if not documentos:
        consolidated_collection.delete_many({})
        return None

    df = pd.DataFrame(documentos)
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    df = df.dropna(subset=['fecha'])

    if df.empty:
        consolidated_collection.delete_many({})
        return None

    df = df.groupby('fecha')['pasos'].max().reset_index().sort_values('fecha')

    consolidated_collection.delete_many({})
    consolidated_collection.insert_many([
        {'fecha': registro['fecha'].date().isoformat(), 'pasos': int(registro['pasos'])}
        for registro in df.to_dict('records')
    ])

    return df


# =========================================================
# 📊 PARSEO DE ARCHIVOS
# =========================================================

def extraer_df_diario(nombre_archivo, lector_csv):
    FUENTES_HEALTH_CONNECT = [
        'com.sec.android.app.shealth',
        'com.huami.watch.hmwatchmanager'
    ]

    if "Health Connect" in nombre_archivo and nombre_archivo.startswith("Pasos"):
        df = pd.read_csv(lector_csv, header=None)

        if len(df.columns) < 4:
            return None

        df.columns = ['fecha_hora_inicio', 'hora_fin', 'pasos', 'origen']
        df['origen'] = df['origen'].astype(str).str.strip()
        df = df[df['origen'].isin(FUENTES_HEALTH_CONNECT)]

        if df.empty:
            return None

        df['fecha'] = pd.to_datetime(
            df['fecha_hora_inicio'].astype(str).str.split(' ').str[0],
            format='%Y.%m.%d',
            errors='coerce'
        ).dt.date

        df['pasos'] = pd.to_numeric(df['pasos'], errors='coerce').fillna(0).astype(int)

        fechas_dt = pd.to_datetime(df['fecha'])
        df = df[~((fechas_dt.dt.year == 2026) & (fechas_dt.dt.month == 3))]

        if df.empty:
            return None

        return df.groupby('fecha')['pasos'].sum().reset_index()

    if "Huawei Health" in nombre_archivo:
        df = pd.read_csv(lector_csv)
        df.columns = [c.strip().lower() for c in df.columns]

        if 'fecha' not in df.columns or 'pasos' not in df.columns:
            return None

        df['fecha'] = pd.to_datetime(
            df['fecha'].astype(str).str.split(' ').str[0],
            format='%Y.%m.%d',
            errors='coerce'
        ).dt.date

        df['pasos'] = pd.to_numeric(df['pasos'], errors='coerce').fillna(0).astype(int)

        return df.groupby('fecha')['pasos'].sum().reset_index()

    return None


def procesar_todos_los_csv_de_drive(service, archivos):
    csvs = [f for f in archivos if f['name'].lower().endswith('.csv')]

    if not csvs:
        print("❌ No se encontraron archivos CSV en Drive")
        return None

    print(f"📂 Procesando {len(csvs)} archivos desde Drive...\n")

    lista_dataframes = []
    archivos_actualizados = 0
    archivos_saltados = 0

    client, raw_collection, consolidated_collection = obtener_collecciones_mongo()
    if client is None or raw_collection is None or consolidated_collection is None:
        print("❌ Mongo no está configurado; no se puede guardar el resultado.")
        return None

    for archivo in csvs:
        file_id = archivo['id']
        nombre_archivo = archivo['name']
        size_drive = str(archivo.get('size') or '')
        modified_drive = str(archivo.get('modifiedTime') or '')

        if archivo_ya_sincronizado(raw_collection, file_id, modified_drive):
            archivos_saltados += 1
            continue

        texto_csv = descargar_csv_como_texto(service, file_id)
        if texto_csv is None:
            print(f"CSV vacio, omitido: {nombre_archivo}")
            continue

        try:
            df = extraer_df_diario(nombre_archivo, texto_csv)
            if df is None or df.empty:
                continue

            raw_collection.delete_many({'file_id': file_id})
            guardar_raw_en_mongo(raw_collection, file_id, nombre_archivo, modified_drive, df)
            archivos_actualizados += 1

        except Exception as e:
            print(f"Error procesando {nombre_archivo}: {e}")

    df_final = recalcular_consolidado_desde_raw(raw_collection, consolidated_collection)
    client.close()

    if df_final is not None:
        print(f"🔄 Archivos actualizados: {archivos_actualizados}")
    print(f"⏭️ Archivos saltados por estar ya sincronizados: {archivos_saltados}")

    return df_final


def bootstrap_desde_drive_csv_locales(archivos_drive):
    archivos_locales = glob.glob(os.path.join(CARPETA_BOOTSTRAP, '*.csv'))
    if not archivos_locales:
        return None, {'files': {}}

    mapa_drive = {archivo['name']: archivo for archivo in archivos_drive if archivo['name'].lower().endswith('.csv')}
    lista_dataframes = []

    client, raw_collection, consolidated_collection = obtener_collecciones_mongo()
    if client is None or raw_collection is None or consolidated_collection is None:
        print("❌ Mongo no está configurado; no se puede hacer bootstrap.")
        return None

    for ruta_local in archivos_locales:
        nombre_archivo = os.path.basename(ruta_local)
        meta = mapa_drive.get(nombre_archivo)
        file_id = meta['id'] if meta else nombre_archivo
        modified_time = str(meta.get('modifiedTime') if meta else '')

        try:
            df = extraer_df_diario(nombre_archivo, ruta_local)
            if df is None or df.empty:
                continue

            raw_collection.delete_many({'file_id': file_id})
            guardar_raw_en_mongo(raw_collection, file_id, nombre_archivo, modified_time, df)
            lista_dataframes.append(file_id)
        except Exception as e:
            print(f"Error bootstrap {nombre_archivo}: {e}")

    if not lista_dataframes:
        client.close()
        return None

    df_final = recalcular_consolidado_desde_raw(raw_collection, consolidated_collection)
    client.close()

    return df_final



# =========================================================
# 🚀 MAIN
# =========================================================

if __name__ == '__main__':

    try:
        service = conectar_drive()
        archivos = listar_csv(service)

        df_resultado = procesar_todos_los_csv_de_drive(service, archivos)

        if df_resultado is not None and not df_resultado.empty:
            print("\n✅ Actualizado correctamente")
            print(f"📊 Días: {len(df_resultado)}")
        else:
            print("❌ Sin datos")

    except Exception as e:
        print(f"Error: {e}")
