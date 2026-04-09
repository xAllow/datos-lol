import os
from datetime import datetime
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "lol"
COLLECTION_NAME = "partidas"

def migrate_dates():
    if not MONGODB_URI:
        print("Error: MONGODB_URI no encontrada.")
        return

    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    # Campos a convertir de string a Date
    date_fields = ["info.gameCreation", "info.gameStartTimestamp", "info.gameEndTimestamp"]
    
    # Buscamos documentos donde gameCreation sea un string
    cursor = collection.find({"info.gameCreation": {"$type": "string"}})
    
    operations = []
    count = 0
    
    print("Iniciando migración de tipos de fecha...")
    
    for doc in cursor:
        info = doc.get("info", {})
        updates = {}
        
        for field in ["gameCreation", "gameStartTimestamp", "gameEndTimestamp"]:
            val = info.get(field)
            if isinstance(val, str):
                try:
                    # Formato usado anteriormente: "%Y-%m-%d %H:%M:%S"
                    dt = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                    updates[f"info.{field}"] = dt
                except ValueError:
                    print(f"No se pudo convertir {val} en el documento {doc.get('_id')}")

        if updates:
            operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": updates}))
            count += 1

        if len(operations) >= 100:
            collection.bulk_write(operations)
            operations = []
            print(f"Procesados {count} documentos...")

    if operations:
        collection.bulk_write(operations)
        print(f"Procesados {count} documentos finales.")

    print(f"Migración completada. Total de documentos actualizados: {count}")
    client.close()

if __name__ == "__main__":
    migrate_dates()
