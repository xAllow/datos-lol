import os
import io
import glob
from pathlib import Path
import pandas as pd
import sys
import json

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
ARCHIVOS_POR_LOTE = 50  # archivos que se agrupan en cada escritura a Mongo


# =========================================================
# ☁️ GOOGLE DRIVE
# =========================================================

def conectar_drive():
    creds_json_env = os.getenv("GDRIVE_CREDENTIALS_JSON")

    if creds_json_env:
        # Estamos en CI (GitHub Actions): las credenciales vienen como JSON en variable de entorno
        info = json.loads(creds_json_env)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=SCOPES
        )
    elif SERVICE_ACCOUNT_FILE.exists():
        # Estamos en local: las credenciales vienen del archivo credentials.json
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=SCOPES
        )
    else:
        raise RuntimeError(
            "No se encontraron credenciales de Google Drive. "
            "Define GDRIVE_CREDENTIALS_JSON como variable de entorno o coloca credentials.json en el directorio."
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
            fields="nextPageToken, files(id, name, modifiedTime)",
            pageSize=1000,
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


def mapa_sincronizados(raw_collection):
    """Estado de todos los archivos ya guardados, en un unico viaje a Mongo.

    Antes se preguntaba archivo por archivo con find_one: con ~1000 CSV eran
    ~1000 idas y vueltas a Atlas (unos 28 s) solo para descubrir que no habia
    nada nuevo que procesar.
    """
    agrupado = raw_collection.aggregate([
        {'$group': {'_id': '$file_id', 'modifiedTime': {'$max': '$modifiedTime'}}}
    ])

    return {doc['_id']: doc.get('modifiedTime') for doc in agrupado}


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


def leer_consolidado(consolidated_collection):
    """El consolidado que ya esta en Mongo, para cuando no hay nada que recalcular."""
    documentos = list(consolidated_collection.find({}, {'_id': 0, 'fecha': 1, 'pasos': 1}))
    if not documentos:
        return None

    df = pd.DataFrame(documentos)
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')

    return df.dropna(subset=['fecha']).sort_values('fecha')


def recalcular_consolidado_desde_raw(raw_collection, consolidated_collection):
    from pymongo import UpdateOne

    # La mediana por dia la calcula Mongo: bajar los ~6000 registros crudos para
    # agruparlos en pandas era traerse muchos mas datos de los necesarios.
    #
    # Antes se usaba el maximo, pero Health Connect exporta el mismo dia por
    # varias vias (archivo diario, ventana movil de 30 dias, semanal, mensual)
    # y de vez en cuando alguna de esas vias sale inflada (un dia con ~20k
    # pasos segun 20+ archivos que coinciden, pero el archivo mensual de ese
    # mes reporta ~100k para ese mismo dia). Con el maximo, ese unico archivo
    # con el dato erroneo ganaba siempre. La mediana ignora ese tipo de valor
    # atipico mientras la mayoria de fuentes esten de acuerdo.
    documentos = list(raw_collection.aggregate([
        {'$group': {'_id': '$fecha', 'pasos': {'$median': {'input': '$pasos', 'method': 'approximate'}}}},
        {'$sort': {'_id': 1}},
    ]))

    if not documentos:
        consolidated_collection.delete_many({})
        return None

    df = pd.DataFrame(documentos).rename(columns={'_id': 'fecha'})
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    df = df.dropna(subset=['fecha']).sort_values('fecha')

    if df.empty:
        consolidated_collection.delete_many({})
        return None

    registros = [
        (registro['fecha'].date().isoformat(), round(registro['pasos']))
        for registro in df.to_dict('records')
    ]
    dias = [dia for dia, _ in registros]

    # Upsert en vez de borrar y reinsertar: asi el panel nunca lee la coleccion
    # vacia si consulta justo mientras se esta escribiendo.
    consolidated_collection.bulk_write([
        UpdateOne({'fecha': dia}, {'$set': {'fecha': dia, 'pasos': paso}}, upsert=True)
        for dia, paso in registros
    ])
    consolidated_collection.delete_many({'fecha': {'$nin': dias}})

    return df


# =========================================================
# 📊 PARSEO DE ARCHIVOS
# =========================================================

def formato_soportado(nombre_archivo):
    """Los dos unicos formatos que sabe leer extraer_df_diario.

    Se comprueba antes de descargar: cualquier otro CSV de la carpeta se bajaba
    entero en cada ejecucion solo para descubrir que no se sabe interpretar.
    """
    if "Health Connect" in nombre_archivo and nombre_archivo.startswith("Pasos"):
        return True

    return "Huawei Health" in nombre_archivo


def extraer_df_diario(nombre_archivo, lector_csv):
    FUENTES_HEALTH_CONNECT = [
        'com.sec.android.app.shealth',
        'com.huami.watch.hmwatchmanager'
    ]

    if "Health Connect" in nombre_archivo and nombre_archivo.startswith("Pasos"):
        df = pd.read_csv(lector_csv, header=None)

        if df.empty:
            return None

        # Desde ~sept. 2026 la app exporta con cabecera "Fecha,Hora,Pasos" y ya
        # sin columna de dispositivo: Health Connect entrega el total unificado,
        # asi que no hace falta (ni se puede) filtrar por origen.
        formato_nuevo = str(df.iloc[0, 0]).strip() == "Fecha"

        if formato_nuevo:
            if df.shape[1] < 3:
                return None
            df = df.iloc[1:, :3].copy()
            df.columns = ['fecha_hora_inicio', 'hora_fin', 'pasos']
        else:
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
        df = df.dropna(subset=['fecha'])

        if df.empty:
            return None

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

    archivos_actualizados = 0
    archivos_saltados = 0
    archivos_ignorados = 0
    archivos_sin_datos = 0

    client, raw_collection, consolidated_collection = obtener_collecciones_mongo()
    if client is None or raw_collection is None or consolidated_collection is None:
        print("❌ Mongo no está configurado; no se puede guardar el resultado.")
        return None

    from pymongo import DeleteMany, InsertOne

    sincronizados = mapa_sincronizados(raw_collection)
    operaciones = []
    pendientes = 0

    for archivo in csvs:
        file_id = archivo['id']
        nombre_archivo = archivo['name']
        modified_drive = str(archivo.get('modifiedTime') or '')

        if file_id and sincronizados.get(file_id) == modified_drive:
            archivos_saltados += 1
            continue

        if not formato_soportado(nombre_archivo):
            archivos_ignorados += 1
            continue

        texto_csv = descargar_csv_como_texto(service, file_id)
        if texto_csv is None:
            print(f"CSV vacio, omitido: {nombre_archivo}")
            continue

        try:
            df = extraer_df_diario(nombre_archivo, texto_csv)

            # Se acumulan las escrituras de varios archivos en un solo bulk_write:
            # antes cada archivo costaba dos idas y vueltas a Mongo.
            operaciones.append(DeleteMany({'file_id': file_id}))

            if df is None or df.empty:
                # El archivo no aporta ningun dia (p.ej. cae entero en marzo de
                # 2026, que se excluye mas abajo). Aun asi queda constancia de
                # que ya se proceso: si no, se volveria a descargar en cada
                # ejecucion para siempre. El marcador no lleva fecha real, asi
                # que la agregacion del consolidado lo descarta sin problema.
                operaciones.append(InsertOne({
                    'file_id': file_id,
                    'name': nombre_archivo,
                    'modifiedTime': modified_drive,
                    'fecha': None,
                    'pasos': 0,
                }))
                archivos_sin_datos += 1
            else:
                operaciones.extend(
                    InsertOne({
                        'file_id': file_id,
                        'name': nombre_archivo,
                        'modifiedTime': modified_drive,
                        'fecha': str(registro['fecha']),
                        'pasos': int(registro['pasos']),
                    })
                    for registro in df.to_dict('records')
                )
                archivos_actualizados += 1

            pendientes += 1

            # Se vuelca cada cierto numero de archivos para no perder el avance
            # si el proceso se corta a mitad.
            if pendientes >= ARCHIVOS_POR_LOTE:
                raw_collection.bulk_write(operaciones)
                operaciones = []
                pendientes = 0

        except Exception as e:
            print(f"Error procesando {nombre_archivo}: {e}")

    if operaciones:
        raw_collection.bulk_write(operaciones)

    if archivos_actualizados:
        df_final = recalcular_consolidado_desde_raw(raw_collection, consolidated_collection)
        print(f"🔄 Archivos actualizados: {archivos_actualizados}")
    else:
        # Sin archivos nuevos el consolidado no puede haber cambiado.
        df_final = leer_consolidado(consolidated_collection)

    client.close()

    print(f"⏭️ Archivos saltados por estar ya sincronizados: {archivos_saltados}")
    if archivos_ignorados:
        print(f"🚫 Archivos con un formato que no se sabe leer: {archivos_ignorados}")
    if archivos_sin_datos:
        print(f"➖ Archivos procesados sin dias utiles (p.ej. marzo 2026): {archivos_sin_datos}")

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
