import { NextResponse } from "next/server";
import { cachear } from "@/lib/cache";
import { COLECCION_ACTIVIDADES, getDb, mongoConfigurado } from "@/lib/mongo";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import type { Actividad, RespuestaActividades, TipoActividad, ZonasFc, ZonasRitmo } from "@/lib/tipos";
import { actividadesDemo, demoActivo } from "@/lib/demo";

const TIPOS_VALIDOS: TipoActividad[] = ["RUNNING", "WALKING", "SWIMMING", "TRAINING"];

function numOrNull(valor: unknown): number | null {
  return valor === null || valor === undefined ? null : Number(valor);
}

function zonasFc(valor: unknown): ZonasFc | null {
  if (!valor || typeof valor !== "object") return null;
  const z = valor as Record<string, unknown>;
  return {
    z1: Number(z.z1 ?? 0),
    z2: Number(z.z2 ?? 0),
    z3: Number(z.z3 ?? 0),
    z4: Number(z.z4 ?? 0),
    z5: Number(z.z5 ?? 0),
  };
}

function zonasRitmo(valor: unknown): ZonasRitmo | null {
  if (!valor || typeof valor !== "object") return null;
  const z = valor as Record<string, unknown>;
  return {
    rapido: Number(z.rapido ?? 0),
    medio: Number(z.medio ?? 0),
    trote: Number(z.trote ?? 0),
    caminando: Number(z.caminando ?? 0),
    parado: Number(z.parado ?? 0),
  };
}

function extraerActividad(doc: Record<string, any>): Actividad | null {
  if (!TIPOS_VALIDOS.includes(doc.tipo)) return null;
  const fecha = new Date(doc.fecha).getTime();
  if (!Number.isFinite(fecha)) return null;

  return {
    id: doc.id ?? doc._id,
    tipo: doc.tipo,
    fecha,
    duracionActiva: Number(doc.duracionActiva ?? 0),
    duracionTotal: Number(doc.duracionTotal ?? 0),
    distancia: Number(doc.distancia ?? 0),
    calorias: Number(doc.calorias ?? 0),
    pasos: Number(doc.pasos ?? 0),
    fcMedia: Number(doc.fcMedia ?? 0),
    fcMaxima: Number(doc.fcMaxima ?? 0),
    velMedia: Number(doc.velMedia ?? 0),
    velMaxima: Number(doc.velMaxima ?? 0),
    elevacion: numOrNull(doc.elevacion),
    mejor400: numOrNull(doc.mejor400),
    mejor1km: numOrNull(doc.mejor1km),
    mejor2km: numOrNull(doc.mejor2km),
    mejor5km: numOrNull(doc.mejor5km),
    mejor10km: numOrNull(doc.mejor10km),
    zonasFc: zonasFc(doc.zonasFc),
    zonasRitmo: zonasRitmo(doc.zonasRitmo),
    traza: Array.isArray(doc.traza) ? doc.traza : null,
    fuente: doc.fuente ?? null,
  };
}

async function cargarActividades(): Promise<RespuestaActividades> {
  const db = await getDb();
  const documentos = await db
    .collection(COLECCION_ACTIVIDADES)
    .find({}, { projection: { _id: 0 } })
    .sort({ fecha: 1 })
    .toArray();

  const actividades: Actividad[] = [];
  for (const doc of documentos as Record<string, any>[]) {
    const fila = extraerActividad(doc);
    if (fila) actividades.push(fila);
  }

  return { actividades };
}

export async function GET(peticion: Request) {
  if (demoActivo(peticion.url)) {
    return NextResponse.json(actividadesDemo());
  }
  if (!mongoConfigurado()) {
    return NextResponse.json({ error: "Falta configurar MONGODB_URI en el entorno." }, { status: 503 });
  }
  try {
    const datos = await cachear("actividades", 5 * 60 * 1000, cargarActividades);
    return NextResponse.json(datos);
  } catch (error) {
    const mensaje = error instanceof Error ? error.message : "Error desconocido";
    return NextResponse.json({ error: `No se pudieron cargar las actividades: ${mensaje}` }, { status: 500 });
  }
}
