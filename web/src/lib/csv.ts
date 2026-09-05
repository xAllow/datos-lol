/** Parser CSV minimo con soporte de comillas dobles y saltos de linea escapados. */
export function parseCsv(texto: string): string[][] {
  const filas: string[][] = [];
  let fila: string[] = [];
  let campo = "";
  let enComillas = false;

  const limpio = texto.replace(/^﻿/, "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");

  for (let i = 0; i < limpio.length; i++) {
    const c = limpio[i];

    if (enComillas) {
      if (c === '"') {
        if (limpio[i + 1] === '"') {
          campo += '"';
          i++;
        } else {
          enComillas = false;
        }
      } else {
        campo += c;
      }
      continue;
    }

    if (c === '"') {
      enComillas = true;
    } else if (c === ",") {
      fila.push(campo);
      campo = "";
    } else if (c === "\n") {
      fila.push(campo);
      filas.push(fila);
      fila = [];
      campo = "";
    } else {
      campo += c;
    }
  }

  if (campo.length > 0 || fila.length > 0) {
    fila.push(campo);
    filas.push(fila);
  }

  return filas.filter((f) => f.some((v) => v.trim() !== ""));
}

/** Numeros en formato espanol: 1.234,56 -> 1234.56 */
export function parseNumeroEs(valor: unknown): number {
  if (valor === null || valor === undefined) return 0;
  let texto = String(valor).trim().replace(/\s|€/g, "");
  if (!texto) return 0;
  if (texto.includes(",")) {
    texto = texto.replace(/\./g, "").replace(",", ".");
  }
  const n = Number(texto);
  return Number.isFinite(n) ? n : 0;
}
