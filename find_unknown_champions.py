import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "lol"
COLLECTION_NAME = "partidas"

client = MongoClient(MONGODB_URI)
collection = client[DB_NAME][COLLECTION_NAME]

unknown_champions = set()
for doc in collection.find({"info.participants.champion_damage_type": "UNKNOWN"}):
    for participant in doc["info"]["participants"]:
        if participant.get("champion_damage_type") == "UNKNOWN":
            champ_name = participant.get("championName")
            if champ_name:
                unknown_champions.add(champ_name)

print("Campeones con champion_damage_type = 'UNKNOWN':")
for name in sorted(unknown_champions):
    print(name)
