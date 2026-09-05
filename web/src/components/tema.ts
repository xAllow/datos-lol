"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { ESTADO, Modo, SERIES, TINTA, colorSecuencial } from "@/lib/paleta";

export type Paleta = {
  modo: Modo;
  series: string[];
  estado: typeof ESTADO;
  tinta: (typeof TINTA)["light"];
  secuencial: (t: number) => string;
  montado: boolean;
};

export function usePaleta(): Paleta {
  const { resolvedTheme } = useTheme();
  const [montado, setMontado] = useState(false);

  useEffect(() => setMontado(true), []);

  const modo: Modo = resolvedTheme === "dark" ? "dark" : "light";

  return {
    modo,
    series: SERIES[modo],
    estado: ESTADO,
    tinta: TINTA[modo],
    secuencial: (t: number) => colorSecuencial(t, modo),
    montado,
  };
}
