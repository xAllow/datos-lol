import os
from datetime import datetime
from typing import Any

from pymongo import MongoClient, UpdateOne
from riotwatcher import ApiError, LolWatcher, RiotWatcher
from dotenv import load_dotenv

load_dotenv()

# Parametros estaticos (alineados con el notebook)
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")

REGION = "EUW1"
MATCH_REGION = "europe"
INICIO_SEASON = "2026-01-07T00:00:00Z"
QUEUE = 420
MATCH_TYPE = "ranked"

DB_NAME = "lol"
COLLECTION_NAME = "partidas"

GAME_NAME = "xAllow"
TAG_LINE = "ESP"


def to_epoch_seconds(date_str: str) -> int:
    return int(datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").timestamp())


def normalize_duration_seconds(value: Any) -> Any:
    if not isinstance(value, (int, float)):
        return value
    seconds = value / 1000
    return int(seconds) if float(seconds).is_integer() else round(seconds, 3)


def normalize_match_data(match_data: dict[str, Any]) -> dict[str, Any]:
    info = match_data.get("info", {})

    # Si no hay gameEndTimestamp, Riot puede devolver gameDuration en ms.
    if "gameDuration" in info and isinstance(info["gameDuration"], (int, float)):
        if "gameEndTimestamp" not in info or info["gameEndTimestamp"] is None:
            info["gameDuration"] = normalize_duration_seconds(info["gameDuration"])

    # Convertimos timestamps absolutos de ms a objetos datetime de Python (BSON Date en MongoDB).
    for field in ("gameCreation", "gameStartTimestamp", "gameEndTimestamp"):
        if field in info and isinstance(info[field], (int, float)):
            info[field] = datetime.fromtimestamp(info[field] / 1000)

    # Añadir champion_damage_type a cada participant
    try:
        import json
        with open("campeones.json", "r", encoding="utf-8") as f:
            campeones = json.load(f)
        champion_type_map = {c["name"]: c["type"] for c in campeones}
        if "participants" in info:
            for participant in info["participants"]:
                champ_name = participant.get("championName")
                participant["champion_damage_type"] = champion_type_map.get(champ_name, "UNKNOWN")
    except Exception as e:
        print(f"Error añadiendo champion_damage_type: {e}")

    return match_data


def get_puuid(riot_watcher: RiotWatcher) -> str:
    account = riot_watcher.account.by_riot_id(MATCH_REGION.upper(), GAME_NAME, TAG_LINE)
    return account["puuid"]


def main() -> None:
    riot_api_key = RIOT_API_KEY
    mongodb_uri = MONGODB_URI

    if not riot_api_key:
        raise ValueError("Falta RIOT_API_KEY en variables de entorno.")
    if not mongodb_uri:
        raise ValueError("Falta MONGODB_URI en variables de entorno.")

    lol_watcher = LolWatcher(riot_api_key)
    riot_watcher = RiotWatcher(riot_api_key)

    mongo_client = MongoClient(mongodb_uri)
    collection = mongo_client[DB_NAME][COLLECTION_NAME]

    # Unicidad por matchId para prevenir duplicados a nivel de BD.
    collection.create_index("metadata.matchId", unique=True)

    puuid = get_puuid(riot_watcher)
    print(f"PUUID objetivo: {puuid}")

    inicio_season = INICIO_SEASON

    ultima_partida = collection.find_one(
        {
            "metadata.participants": puuid,
            "info.gameCreation": {"$exists": True},
        },
        {"info.gameCreation": 1, "_id": 0},
        sort=[("info.gameCreation", -1)],
    )

    # Fallback: si los docs no tienen participants pero si gameCreation,
    # usamos la ultima fecha global para mantener la sincronizacion incremental.
    if not ultima_partida:
        ultima_partida = collection.find_one(
            {"info.gameCreation": {"$exists": True}},
            {"info.gameCreation": 1, "_id": 0},
            sort=[("info.gameCreation", -1)],
        )

    if ultima_partida and "info" in ultima_partida and "gameCreation" in ultima_partida["info"]:
        # Igual que en el notebook: usamos info.gameCreation como ultima_fecha.
        ultima_fecha = ultima_partida["info"]["gameCreation"]
        if isinstance(ultima_fecha, datetime):
            start_epoch = int(ultima_fecha.timestamp())
        elif isinstance(ultima_fecha, str):
            start_epoch = int(
                datetime.strptime(ultima_fecha, "%Y-%m-%d %H:%M:%S").timestamp()
            )
        else:
            start_epoch = int(ultima_fecha / 1000)
        print(f"Descargando desde ultima partida en Mongo: {datetime.fromtimestamp(start_epoch)}")
    else:
        start_epoch = to_epoch_seconds(inicio_season)
        print(f"Sin historial en Mongo. Descargando desde inicio de season: {inicio_season}")

    end_epoch = int(datetime.now().timestamp())

    match_ids: list[str] = []
    start = 0
    count = 100

    print("Consultando IDs de partidas...")
    while True:
        batch = lol_watcher.match.matchlist_by_puuid(
            MATCH_REGION,
            puuid,
            queue=QUEUE,
            type=MATCH_TYPE,
            start_time=start_epoch,
            end_time=end_epoch,
            start=start,
            count=count,
        )

        if not batch:
            break

        match_ids.extend(batch)

        if len(batch) < count:
            break

        start += count

    if not match_ids:
        print("No se encontraron partidas en el rango solicitado.")
        return

    existing = {
        doc["metadata"]["matchId"]
        for doc in collection.find(
            {"metadata.matchId": {"$in": match_ids}},
            {"metadata.matchId": 1, "_id": 0},
        )
    }
    new_ids = [m_id for m_id in match_ids if m_id not in existing]

    print(f"IDs obtenidos: {len(match_ids)}")
    print(f"IDs ya en Mongo: {len(existing)}")
    print(f"IDs nuevos a descargar: {len(new_ids)}")

    if not new_ids:
        print("No hay partidas nuevas para sincronizar.")
        return

    new_matches: list[dict[str, Any]] = []
    for idx, match_id in enumerate(new_ids, start=1):
        try:
            match_data = lol_watcher.match.by_id(MATCH_REGION, match_id)
        except ApiError as exc:
            print(f"Error descargando {match_id}: {exc}")
            continue

        new_matches.append(normalize_match_data(match_data))

        if idx % 50 == 0:
            print(f"Descargadas {idx}/{len(new_ids)} partidas...")

    if not new_matches:
        print("No se pudo descargar ninguna partida nueva.")
        return

    operations = [
        UpdateOne(
            {"metadata.matchId": match["metadata"]["matchId"]},
            {"$set": match},
            upsert=True,
        )
        for match in new_matches
    ]

    result = collection.bulk_write(operations, ordered=False)

    print("Sincronizacion finalizada:")
    print(f"- Upserts nuevos: {result.upserted_count}")
    print(f"- Documentos modificados: {result.modified_count}")
    print(f"- Partidas procesadas: {len(new_matches)}")


if __name__ == "__main__":
    main()
