import os
import json
from pymongo import MongoClient
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "lol"
COLLECTION_NAME = "partidas"

# Leer campeones.json
with open("campeones.json", "r", encoding="utf-8") as f:
    campeones = json.load(f)
champion_type_map = {c["name"]: c["type"] for c in campeones}

# Conectar a Mongo
client = MongoClient(MONGODB_URI)
collection = client[DB_NAME][COLLECTION_NAME]

# Actualizar documentos
for doc in collection.find({"info.participants": {"$exists": True}}):
    updated = False
    for participant in doc["info"]["participants"]:
        champ_name = participant.get("championName")
        if champ_name and "champion_damage_type" not in participant:
            participant["champion_damage_type"] = champion_type_map.get(champ_name, "UNKNOWN")
            updated = True
    if updated:
        collection.update_one({"_id": doc["_id"]}, {"$set": {"info.participants": doc["info"]["participants"]}})

print("Actualización completada.")
