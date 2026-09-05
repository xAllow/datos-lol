import { NextResponse } from "next/server";
import { cachear } from "@/lib/cache";
import { parseCsv } from "@/lib/csv";
import { claveDia, parsearFechaFlexible } from "@/lib/fechas";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import type { Registro, RespuestaRegistro } from "@/lib/tipos";
import { demoActivo, registroDemo } from "@/lib/demo";

async function cargarRegistro(url: string): Promise<RespuestaRegistro> {
  const respuesta = await fetch(url, { cache: "no-store" });
  if (!respuesta.ok) {
    throw new Error(`la hoja respondio ${respuesta.status}`);
  }
  const filas = parseCsv(await respuesta.text());
  const registros: Registro[] = [];

  for (let i = 1; i < filas.length; i++) {
    const fila = filas[i];
    if (!fila || fila.length < 2) continue;
    const fecha = parsearFechaFlexible(fila[0]);
    if (!fecha) continue;
    const minutos = Number(String(fila[1] ?? "").trim().replace(",", "."));
    if (!Number.isFinite(minutos)) continue;
    registros.push({ t: fecha.getTime(), dia: claveDia(fecha), minutos });
  }

  registros.sort((a, b) => a.t - b.t);
  return { registros };
}

export async function GET(peticion: Request) {
  if (demoActivo(peticion.url)) {
    return NextResponse.json({ registros: registroDemo() });
  }
  const url = process.env.GOOGLE_SHEET_CSV_URL;
  if (!url) {
    return NextResponse.json(
      { error: "Falta configurar GOOGLE_SHEET_CSV_URL en el entorno." },
      { status: 503 },
    );
  }
  try {
    const datos = await cachear("registro", 5 * 60 * 1000, () => cargarRegistro(url));
    return NextResponse.json(datos);
  } catch (error) {
    const mensaje = error instanceof Error ? error.message : "Error desconocido";
    return NextResponse.json({ error: `No se pudo leer la hoja: ${mensaje}` }, { status: 500 });
  }
}
