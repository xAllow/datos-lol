import io
import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# =========================================================
# CONFIG
# =========================================================

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
SERVICE_ACCOUNT_FILE = BASE_DIR / 'credentials.json'
FOLDER_ID = '1gLIZVZ_1PH82Xu73UYZb9pHUStOXkcMT'

TIPOS = ('RUNNING', 'WALKING', 'SWIMMING', 'TRAINING')
NS = {
    'gpx': 'http://www.topografix.com/GPX/1/1',
    'gpxtpx': 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1',
}

# Referencia de FC maxima para las zonas (% de FC max, modelo de 5 zonas).
# Fija (no recalculada por sincronizacion) para que las zonas sean comparables
# entre actividades a lo largo del tiempo; el maximo real observado en los
# datos ronda 191, se deja margen razonable.
FC_MAX_REF = 195
ZONAS_FC_LIMITES = [
    ('z1', 0.0, 0.6),
    ('z2', 0.6, 0.7),
    ('z3', 0.7, 0.8),
    ('z4', 0.8, 0.9),
    ('z5', 0.9, 999.0),
]

# Bandas de ritmo (segundos por km) para desglosar el tiempo de una actividad.
# No dependen del tipo: una carrera con tramos de caminata cae igual en
# "caminando", y eso es justo la señal que se quiere ver.
ZONAS_RITMO_LIMITES = [
    ('rapido', 0, 300),        # < 5:00 /km
    ('medio', 300, 390),       # 5:00 - 6:30 /km
    ('trote', 390, 480),       # 6:30 - 8:00 /km
    ('caminando', 480, 900),   # 8:00 - 15:00 /km
    ('parado', 900, float('inf')),
]

# Distancias (metros) para las que se busca el mejor tiempo continuo.
DISTANCIAS_MARCA = [400, 1000, 2000, 5000, 10000]


# =========================================================
# GOOGLE DRIVE
# =========================================================

def conectar_drive():
    creds_json_env = os.getenv("GDRIVE_CREDENTIALS_JSON")

    if creds_json_env:
        info = json.loads(creds_json_env)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    elif SERVICE_ACCOUNT_FILE.exists():
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
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
COLLECTION_NAME = os.getenv('ACTIVIDADES_COLLECTION_NAME', 'actividades')


def listar_archivos(service):
    archivos = []
    page_token = None
    while True:
        respuesta = service.files().list(
            q=f"'{FOLDER_ID}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, modifiedTime)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()
        archivos.extend(respuesta.get('files', []))
        page_token = respuesta.get('nextPageToken')
        if not page_token:
            break
    print(f"Total archivos en Drive: {len(archivos)}")
    return archivos


def descargar_texto(service, file_id):
    buffer = io.BytesIO()
    request = service.files().get_media(fileId=file_id)
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    contenido = buffer.getvalue()
    if not contenido:
        return None
    return contenido.decode('utf-8-sig', errors='replace')


# =========================================================
# MONGO
# =========================================================

def obtener_coleccion():
    if not MONGODB_URI:
        return None, None
    from pymongo import MongoClient
    client = MongoClient(MONGODB_URI)
    return client, client[DB_NAME][COLLECTION_NAME]


def mapa_sincronizados(coleccion):
    """id -> modifiedTime del csv ya guardado, en una sola consulta."""
    return {doc['_id']: doc.get('modifiedTime') for doc in coleccion.find({}, {'modifiedTime': 1})}


# =========================================================
# AGRUPAR Y DEDUPLICAR NOMBRES
# =========================================================

PATRON_CSV = re.compile(
    r'^(RUNNING|WALKING|SWIMMING|TRAINING) (\d{4}\.\d{2}\.\d{2}) (\d{2}\.\d{2})(?: (.+))?\.csv$'
)


def agrupar_actividades(archivos):
    """Agrupa los CSV por (tipo, fecha, hora) y descarta duplicados de forma determinista.

    Health Sync reexporta un CSV extra cuando detecta que la misma actividad
    tambien llego por otra app conectada (Strava, Google Fit...). Los archivos
    de traza (.gpx/.tcx/.fit/.kml) nunca llevan ese sufijo: son siempre la
    grabacion nativa, uno por actividad, y se emparejan por nombre exacto.
    """
    grupos = {}
    for archivo in archivos:
        m = PATRON_CSV.match(archivo['name'])
        if not m:
            continue
        tipo, fecha, hora, _fuente = m.groups()
        clave = (tipo, fecha, hora)
        grupos.setdefault(clave, []).append(archivo)

    canonicos = {}
    for clave, candidatos in grupos.items():
        # El archivo sin sufijo de fuente es la grabacion nativa de Health Sync;
        # los que llevan " Strava"/" Google Fit"/etc son reexportes del mismo
        # evento. "Fitbit.csv" ordena antes que ".csv" por el espacio, asi que
        # no basta con ordenar alfabetico: hay que preferir el que no tiene sufijo.
        candidatos.sort(key=lambda a: (PATRON_CSV.match(a['name']).group(4) is not None, a['name']))
        canonicos[clave] = candidatos[0]
    return canonicos


def id_actividad(tipo, fecha, hora):
    return f"{tipo}_{fecha.replace('.', '-')}_{hora.replace('.', '-')}"


# =========================================================
# PARSEO DEL CSV RESUMEN
# =========================================================

def parsear_csv_actividad(texto):
    lineas = texto.splitlines()
    if len(lineas) < 2:
        return None

    cabecera = [c.strip() for c in lineas[0].split(',')]
    valores = lineas[1].split(',')
    fila = dict(zip(cabecera, valores))

    def num(clave, default=0.0):
        try:
            return float(fila.get(clave, default) or default)
        except ValueError:
            return default

    fecha_hora = fila.get('Fecha', '').strip()
    try:
        fecha_dt = datetime.strptime(fecha_hora, '%Y.%m.%d %H:%M:%S')
    except ValueError:
        return None

    fuente = fila.get('Aplicación de origen', '').strip()
    if not fuente or fuente.lower() == 'null':
        fuente = None
    elif fuente.startswith('unknown-'):
        fuente = fuente[len('unknown-'):]

    return {
        'fecha_dt': fecha_dt,
        'fuente': fuente,
        'duracionTotal': num('Tiempo transcurrido'),
        'duracionActiva': num('Tiempo activo'),
        'distancia': num('Distancia (km)'),
        'calorias': num('Calorías (kcal)'),
        'pasos': int(num('Pasos')),
        'fcMedia': int(num('Frecuencia cardíaca media')),
        'fcMaxima': int(num('Frecuencia cardíaca máxima')),
        'velMedia': num('Velocidad media'),
        'velMaxima': num('Máxima velocidad'),
    }


# =========================================================
# TRAZA GPS (.gpx)
# =========================================================

def haversine_metros(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parsear_gpx(texto):
    """Devuelve un dict con traza, elevacion, mejores tiempos y zonas, o None si no hay trkpt."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(texto)
    except ET.ParseError:
        return None

    trkpts = root.findall('.//gpx:trkpt', NS)
    if not trkpts:
        return None

    puntos = []
    for pt in trkpts:
        try:
            lat = float(pt.get('lat'))
            lon = float(pt.get('lon'))
        except (TypeError, ValueError):
            continue
        ele_el = pt.find('gpx:ele', NS)
        time_el = pt.find('gpx:time', NS)
        hr_el = pt.find('.//gpxtpx:hr', NS)
        ele = float(ele_el.text) if ele_el is not None and ele_el.text else None
        tiempo = None
        if time_el is not None and time_el.text:
            try:
                tiempo = datetime.fromisoformat(time_el.text.replace('Z', '+00:00'))
            except ValueError:
                tiempo = None
        hr = None
        if hr_el is not None and hr_el.text:
            try:
                hr = float(hr_el.text)
            except ValueError:
                hr = None
        puntos.append((lat, lon, ele, tiempo, hr))

    if len(puntos) < 2:
        return None

    # Elevacion acumulada: suma de las subidas entre puntos consecutivos.
    elevacion = 0.0
    tiene_elevacion = any(p[2] is not None for p in puntos)
    if tiene_elevacion:
        anterior = None
        for _, _, ele, _, _ in puntos:
            if ele is None:
                continue
            if anterior is not None and ele > anterior:
                elevacion += ele - anterior
            anterior = ele
    else:
        elevacion = None

    # Distancia y tiempo acumulados, base de mejores marcas y zonas de ritmo.
    dist_acum = [0.0]
    t_acum = [0.0]
    tiene_tiempo = all(p[3] is not None for p in puntos)
    t0 = puntos[0][3] if tiene_tiempo else None
    for i in range(1, len(puntos)):
        lat1, lon1, _, _, _ = puntos[i - 1]
        lat2, lon2, _, t2, _ = puntos[i]
        dist_acum.append(dist_acum[-1] + haversine_metros(lat1, lon1, lat2, lon2))
        t_acum.append((t2 - t0).total_seconds() if tiene_tiempo else t_acum[-1] + 1)

    distancia_total = dist_acum[-1]

    # Ventana deslizante clasica: para cada inicio, el primer punto donde se
    # cubre la distancia objetivo es el candidato mas rapido posible desde ese
    # inicio (alargar mas la ventana solo puede empeorar el tiempo). "der"
    # nunca retrocede. Se repite para cada distancia de marca (400m..10km).
    mejores = {}
    if tiene_tiempo:
        n = len(dist_acum)
        for objetivo in DISTANCIAS_MARCA:
            if distancia_total < objetivo:
                mejores[objetivo] = None
                continue
            mejor = None
            der = 0
            for izq in range(n):
                if der < izq:
                    der = izq
                while der < n - 1 and dist_acum[der] - dist_acum[izq] < objetivo:
                    der += 1
                if dist_acum[der] - dist_acum[izq] < objetivo:
                    break  # desde aqui en adelante ya no queda esa distancia por recorrer
                duracion = t_acum[der] - t_acum[izq]
                if mejor is None or duracion < mejor:
                    mejor = duracion
            mejores[objetivo] = mejor
    else:
        mejores = {objetivo: None for objetivo in DISTANCIAS_MARCA}

    # Zonas de ritmo: a cada tramo entre dos puntos se le asigna una banda
    # segun el ritmo instantaneo (suavizado con una ventana de ~15s para que
    # el ruido del GPS en paradas no meta tramos falsos de "rapido").
    zonas_ritmo = {clave: 0.0 for clave, _, _ in ZONAS_RITMO_LIMITES}
    if tiene_tiempo and distancia_total > 0:
        n = len(dist_acum)
        j = 0
        for i in range(1, n):
            while j < i and t_acum[i] - t_acum[j] > 15:
                j += 1
            dt_ventana = t_acum[i] - t_acum[j]
            dd_ventana = dist_acum[i] - dist_acum[j]
            ritmo = (dt_ventana / (dd_ventana / 1000)) if dd_ventana > 0.5 else float('inf')
            dt_tramo = t_acum[i] - t_acum[i - 1]
            for clave, lo, hi in ZONAS_RITMO_LIMITES:
                if lo <= ritmo < hi:
                    zonas_ritmo[clave] += dt_tramo
                    break
        if sum(zonas_ritmo.values()) == 0:
            zonas_ritmo = None
    else:
        zonas_ritmo = None

    # Zonas de frecuencia cardiaca: la FC viene en pocos puntos (Health Sync
    # solo la incluye "de vez en cuando"), asi que se arrastra la ultima
    # lectura conocida hacia adelante para repartir el tiempo entre tramos.
    zonas_fc = {clave: 0.0 for clave, _, _ in ZONAS_FC_LIMITES}
    ultima_hr = None
    tiene_hr = False
    for i in range(1, len(puntos)):
        hr_previo = puntos[i - 1][4]
        if hr_previo is not None:
            ultima_hr = hr_previo
            tiene_hr = True
        if ultima_hr is None:
            continue
        dt_tramo = t_acum[i] - t_acum[i - 1] if tiene_tiempo else 1.0
        fraccion = ultima_hr / FC_MAX_REF
        for clave, lo, hi in ZONAS_FC_LIMITES:
            if lo <= fraccion < hi:
                zonas_fc[clave] += dt_tramo
                break
    if not tiene_hr:
        zonas_fc = None

    # Traza reducida para dibujarla en el mapa: no hace falta guardar cada segundo.
    tope = 120
    paso = max(1, len(puntos) // tope)
    traza = [[round(lat, 6), round(lon, 6)] for lat, lon, _, _, _ in puntos[::paso]]

    return {
        'traza': traza,
        'elevacion': elevacion,
        'mejores': mejores,
        'zonasRitmo': zonas_ritmo,
        'zonasFc': zonas_fc,
    }


# =========================================================
# SINCRONIZACION
# =========================================================

def sincronizar(forzar=False):
    service = conectar_drive()
    archivos = listar_archivos(service)
    por_nombre = {a['name']: a for a in archivos}

    canonicos = agrupar_actividades(archivos)
    print(f"Actividades encontradas tras deduplicar: {len(canonicos)}")

    client, coleccion = obtener_coleccion()
    if client is None:
        print("Mongo no esta configurado; no se puede guardar el resultado.")
        return

    sincronizados = {} if forzar else mapa_sincronizados(coleccion)

    nuevas = 0
    saltadas = 0
    sin_gps = 0
    operaciones = []

    from pymongo import UpdateOne

    for (tipo, fecha, hora), archivo_csv in canonicos.items():
        clave_id = id_actividad(tipo, fecha, hora)
        modificado = str(archivo_csv.get('modifiedTime') or '')

        if sincronizados.get(clave_id) == modificado:
            saltadas += 1
            continue

        texto_csv = descargar_texto(service, archivo_csv['id'])
        if texto_csv is None:
            continue
        datos_csv = parsear_csv_actividad(texto_csv)
        if datos_csv is None:
            continue

        nombre_gpx = f"{fecha} {hora}-{tipo}.gpx"
        archivo_gpx = por_nombre.get(nombre_gpx)
        traza = elevacion = zonas_ritmo = zonas_fc = None
        mejores = {objetivo: None for objetivo in DISTANCIAS_MARCA}
        if archivo_gpx:
            texto_gpx = descargar_texto(service, archivo_gpx['id'])
            if texto_gpx:
                resultado = parsear_gpx(texto_gpx)
                if resultado:
                    traza = resultado['traza']
                    elevacion = resultado['elevacion']
                    mejores = resultado['mejores']
                    zonas_ritmo = resultado['zonasRitmo']
                    zonas_fc = resultado['zonasFc']
        if traza is None:
            sin_gps += 1

        documento = {
            '_id': clave_id,
            'id': clave_id,
            'tipo': tipo,
            'fecha': datos_csv['fecha_dt'].isoformat(),
            'modifiedTime': modificado,
            'archivo': archivo_csv['name'],
            'fuente': datos_csv['fuente'],
            'duracionActiva': datos_csv['duracionActiva'],
            'duracionTotal': datos_csv['duracionTotal'],
            'distancia': datos_csv['distancia'],
            'calorias': datos_csv['calorias'],
            'pasos': datos_csv['pasos'],
            'fcMedia': datos_csv['fcMedia'],
            'fcMaxima': datos_csv['fcMaxima'],
            'velMedia': datos_csv['velMedia'],
            'velMaxima': datos_csv['velMaxima'],
            'elevacion': elevacion,
            'mejor400': mejores.get(400),
            'mejor1km': mejores.get(1000),
            'mejor2km': mejores.get(2000),
            'mejor5km': mejores.get(5000),
            'mejor10km': mejores.get(10000),
            'zonasRitmo': zonas_ritmo,
            'zonasFc': zonas_fc,
            'traza': traza,
        }
        operaciones.append(UpdateOne(
            {'_id': clave_id},
            {'$set': documento, '$unset': {'mejorKm': ''}},
            upsert=True,
        ))
        nuevas += 1

    if operaciones:
        coleccion.bulk_write(operaciones)

    client.close()

    print(f"Actividades nuevas o actualizadas: {nuevas}")
    print(f"Actividades saltadas por estar ya sincronizadas: {saltadas}")
    print(f"Actividades sin traza GPS: {sin_gps}")


if __name__ == '__main__':
    # --forzar (o FORZAR_RESYNC=1) reprocesa todas las actividades aunque su
    # CSV no haya cambiado en Drive. Hace falta cuando cambia la logica de
    # parseo del GPX (zonas, mejores marcas...) y hay que rellenar los campos
    # nuevos en documentos que ya estaban sincronizados.
    forzar = '--forzar' in sys.argv or os.getenv('FORZAR_RESYNC') == '1'
    try:
        sincronizar(forzar=forzar)
        print("\nActualizado correctamente")
    except Exception as e:
        print(f"Error: {e}")
