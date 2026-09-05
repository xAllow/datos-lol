export type Modo = "light" | "dark";

/** Paleta categorica validada (orden fijo, nunca ciclado). */
export const SERIES: Record<Modo, string[]> = {
  light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
  dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
};

/** Estado: nunca se reutiliza como color de serie. */
export const ESTADO = {
  bueno: "#0ca30c",
  aviso: "#fab219",
  serio: "#ec835a",
  critico: "#d03b3b",
};

/** Rampa secuencial de un solo tono (azul), clara -> oscura. */
export const RAMPA_AZUL = [
  "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
  "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab",
  "#184f95", "#104281", "#0d366b",
];

export const TINTA: Record<Modo, {
  superficie: string;
  plano: string;
  primario: string;
  secundario: string;
  apagado: string;
  rejilla: string;
  eje: string;
  borde: string;
}> = {
  light: {
    superficie: "#fcfcfb",
    plano: "#f9f9f7",
    primario: "#0b0b0b",
    secundario: "#52514e",
    apagado: "#898781",
    rejilla: "#e1e0d9",
    eje: "#c3c2b7",
    borde: "rgba(11,11,11,0.10)",
  },
  dark: {
    superficie: "#1a1a19",
    plano: "#0d0d0d",
    primario: "#ffffff",
    secundario: "#c3c2b7",
    apagado: "#898781",
    rejilla: "#2c2c2a",
    eje: "#383835",
    borde: "rgba(255,255,255,0.10)",
  },
};

/** Color de una rampa secuencial a partir de un valor normalizado 0..1. */
export function colorSecuencial(t: number, modo: Modo): string {
  const seguro = Number.isFinite(t) ? Math.min(1, Math.max(0, t)) : 0;
  // En oscuro se recorta la parte mas clara de la rampa para no cegar.
  const rango = modo === "dark" ? RAMPA_AZUL.slice(1, 9) : RAMPA_AZUL.slice(0, 10);
  const idx = Math.round(seguro * (rango.length - 1));
  return rango[idx];
}
