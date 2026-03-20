import os
import json
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "lol"
COLLECTION_NAME = "partidas"

# Leer campeones.json
with open("campeones.json", "r", encoding="utf-8") as f:
    campeones = json.load(f)
champion_names_json = set(c["name"] for c in campeones)

client = MongoClient(MONGODB_URI)
collection = client[DB_NAME][COLLECTION_NAME]

champion_names_db = set()
for doc in collection.find({"info.participants": {"$exists": True}}):
    for participant in doc["info"]["participants"]:
        champ_name = participant.get("championName")
        if champ_name:
            champion_names_db.add(champ_name)

not_in_json = champion_names_db - champion_names_json
print("Nombres de championName en Mongo que no están en campeones.json:")
for name in sorted(not_in_json):
    print(name)

print("\nTotal en Mongo:", len(champion_names_db))
print("Total en campeones.json:", len(champion_names_json))
