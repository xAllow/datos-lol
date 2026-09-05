import { NextResponse } from "next/server";
import { cachear } from "@/lib/cache";
import { COLECCION_PASOS, getDb, mongoConfigurado } from "@/lib/mongo";
import { claveDia, desdeClaveDia, sumarDias } from "@/lib/fechas";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import type { DiaPasos, RespuestaPasos } from "@/lib/tipos";
import { demoActivo, pasosDemo } from "@/lib/demo";

/** PRNG determinista: el mismo dia siempre recibe el mismo valor imputado. */
function aleatorioEstable(semilla: string): number {
  let h = 2166136261;
  for (let i = 0; i < semilla.length; i++) {
    h ^= semilla.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 100000) / 100000;
}

function percentil(valoresOrdenados: number[], p: number): number {
  if (!valoresOrdenados.length) return 0;
  const idx = (valoresOrdenados.length - 1) * p;
  const bajo = Math.floor(idx);
  const alto = Math.ceil(idx);
  if (bajo === alto) return valoresOrdenados[bajo];
  return valoresOrdenados[bajo] + (valoresOrdenados[alto] - valoresOrdenados[bajo]) * (idx - bajo);
}

function normalizarFecha(valor: unknown): Date | null {
  if (!valor) return null;
  if (valor instanceof Date) return valor;
  if (typeof valor === "number") return new Date(valor);
  const texto = String(valor).trim();
  const iso = texto.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return new Date(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
  const euro = texto.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})/);
  if (euro) return new Date(Number(euro[3]), Number(euro[2]) - 1, Number(euro[1]));
  const d = new Date(texto);
  return Number.isNaN(d.getTime()) ? null : d;
}

async function cargarPasos(): Promise<RespuestaPasos> {
  const db = await getDb();
  const documentos = await db
    .collection(COLECCION_PASOS)
    .find({}, { projection: { _id: 0 } })
    .sort({ fecha: 1 })
    .toArray();

  const porDia = new Map<string, number>();
  for (const doc of documentos as Record<string, unknown>[]) {
    const fecha = normalizarFecha(doc.fecha);
    if (!fecha) continue;
    if (fecha.getFullYear() < 2025) continue;
    const bruto = doc.pasos_totales ?? doc.pasos ?? doc.steps ?? 0;
    const valor = Number(bruto);
    if (!Number.isFinite(valor)) continue;
    const clave = claveDia(fecha);
    porDia.set(clave, Math.max(porDia.get(clave) ?? 0, Math.round(valor)));
  }

  const claves = [...porDia.keys()].sort();
  if (!claves.length) {
    return { dias: [], meta: { rellenados: 0, inf: 0, sup: 0, desde: null, hasta: null } };
  }

  const inicio = desdeClaveDia(claves[0]);
  const fin = desdeClaveDia(claves[claves.length - 1]);
  const positivos = [...porDia.values()].filter((v) => v > 0).sort((a, b) => a - b);
  let inf = Math.round(percentil(positivos, 0.05));
  let sup = Math.round(percentil(positivos, 0.15));
  if (!positivos.length) {
    inf = 200;
    sup = 500;
  } else if (inf >= sup) {
    sup = inf + 150;
  }

  const dias: DiaPasos[] = [];
  let rellenados = 0;
  for (let d = inicio; d <= fin; d = sumarDias(d, 1)) {
    const clave = claveDia(d);
    const valor = porDia.get(clave) ?? 0;
    if (valor > 0) {
      dias.push({ f: clave, v: valor, imp: false });
    } else {
      rellenados++;
      const imputado = inf + Math.floor(aleatorioEstable(clave) * Math.max(1, sup - inf));
      dias.push({ f: clave, v: imputado, imp: true });
    }
  }

  return {
    dias,
    meta: { rellenados, inf, sup, desde: dias[0]?.f ?? null, hasta: dias[dias.length - 1]?.f ?? null },
  };
}

export async function GET(peticion: Request) {
  if (demoActivo(peticion.url)) {
    return NextResponse.json(pasosDemo());
  }
  if (!mongoConfigurado()) {
    return NextResponse.json({ error: "Falta configurar MONGODB_URI en el entorno." }, { status: 503 });
  }
  try {
    const datos = await cachear("pasos", 5 * 60 * 1000, cargarPasos);
    return NextResponse.json(datos);
  } catch (error) {
    const mensaje = error instanceof Error ? error.message : "Error desconocido";
    return NextResponse.json({ error: `No se pudieron cargar los pasos: ${mensaje}` }, { status: 500 });
  }
}
