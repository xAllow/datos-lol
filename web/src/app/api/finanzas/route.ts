import { NextResponse } from "next/server";
import { cachear } from "@/lib/cache";
import { parseCsv, parseNumeroEs } from "@/lib/csv";
import { categorizar } from "@/lib/categorias";
import { claveDia, parsearFechaFlexible } from "@/lib/fechas";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import type { Movimiento, RespuestaFinanzas } from "@/lib/tipos";
import { demoActivo, finanzasDemo } from "@/lib/demo";

async function cargarFinanzas(url: string): Promise<RespuestaFinanzas> {
  const respuesta = await fetch(url, { cache: "no-store" });
  if (!respuesta.ok) {
    throw new Error(`la hoja respondio ${respuesta.status}`);
  }
  const texto = await respuesta.text();
  const lineas = texto.split(/\r?\n/);
  const inicio = Math.max(
    0,
    lineas.findIndex((linea) => linea.toLowerCase().startsWith("fecha,concepto,")),
  );
  const filas = parseCsv(lineas.slice(inicio).join("\n"));
  if (!filas.length) return { movimientos: [] };

  const cabecera = filas[0].map((c) => c.trim().toLowerCase());
  const idx = {
    fecha: cabecera.indexOf("fecha"),
    concepto: cabecera.indexOf("concepto"),
    importe: cabecera.indexOf("importe"),
    saldo: cabecera.indexOf("saldo"),
  };

  const movimientos: Movimiento[] = [];
  for (let i = 1; i < filas.length; i++) {
    const fila = filas[i];
    const fecha = parsearFechaFlexible(fila[idx.fecha] ?? "");
    if (!fecha) continue;
    const concepto = String(fila[idx.concepto] ?? "").trim();
    const importe = parseNumeroEs(fila[idx.importe]);
    const saldo = parseNumeroEs(fila[idx.saldo]);
    movimientos.push({
      dia: claveDia(fecha),
      t: fecha.getTime(),
      concepto,
      categoria: categorizar(concepto),
      importe,
      saldo,
    });
  }

  movimientos.sort((a, b) => a.t - b.t || a.saldo - b.saldo);
  return { movimientos };
}

export async function GET(peticion: Request) {
  if (demoActivo(peticion.url)) {
    const movimientos = finanzasDemo().map((m) => ({ ...m, categoria: categorizar(m.concepto) }));
    return NextResponse.json({ movimientos });
  }
  const url = process.env.BANK_CSV_URL;
  if (!url) {
    return NextResponse.json({ error: "Falta configurar BANK_CSV_URL en el entorno." }, { status: 503 });
  }
  try {
    const datos = await cachear("finanzas", 5 * 60 * 1000, () => cargarFinanzas(url));
    return NextResponse.json(datos);
  } catch (error) {
    const mensaje = error instanceof Error ? error.message : "Error desconocido";
    return NextResponse.json({ error: `No se pudieron cargar los movimientos: ${mensaje}` }, { status: 500 });
  }
}
