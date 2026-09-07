import { MongoClient, Db } from "mongodb";

const uri = process.env.MONGODB_URI;
const dbName = process.env.DB_NAME || "lol";

declare global {
  // eslint-disable-next-line no-var
  var _mongoClientPromise: Promise<MongoClient> | undefined;
}

export function mongoConfigurado(): boolean {
  return Boolean(uri);
}

function getClientPromise(): Promise<MongoClient> {
  if (!uri) {
    throw new Error(
      "Falta la variable de entorno MONGODB_URI. Copia .env.example a .env.local y rellenala.",
    );
  }
  if (!global._mongoClientPromise) {
    const client = new MongoClient(uri, {
      maxPoolSize: 5,
      serverSelectionTimeoutMS: 10000,
    });
    global._mongoClientPromise = client.connect();
  }
  return global._mongoClientPromise;
}

export async function getDb(): Promise<Db> {
  const client = await getClientPromise();
  return client.db(dbName);
}

export const COLECCION_PASOS = process.env.COLLECTION_NAME || "pasos";
export const COLECCION_LOL = process.env.LOL_COLLECTION_NAME || "partidas";
export const COLECCION_ACTIVIDADES = process.env.ACTIVIDADES_COLLECTION_NAME || "actividades";
