import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "lol"
COLLECTION_NAME = "partidas"

client = MongoClient(MONGODB_URI)
collection = client[DB_NAME][COLLECTION_NAME]

for doc in collection.find({"info.participants": {"$exists": True}}):
    changed = False
    for participant in doc["info"]["participants"]:
        if "champion_damage_type" in participant:
            del participant["champion_damage_type"]
            changed = True
    if changed:
        collection.update_one({"_id": doc["_id"]}, {"$set": {"info.participants": doc["info"]["participants"]}})

print("Campo champion_damage_type eliminado de todos los participantes.")
