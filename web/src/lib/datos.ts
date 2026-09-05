"use client";

import { useCallback, useEffect, useState } from "react";

export type EstadoDatos<T> = {
  datos: T | null;
  cargando: boolean;
  error: string | null;
  recargar: () => void;
};

export function useDatos<T>(url: string): EstadoDatos<T> {
  const [datos, setDatos] = useState<T | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    let cancelado = false;
    setCargando(true);
    setError(null);

    const demo = typeof window !== "undefined" && window.location.search.includes("demo=1");
    const destino = demo ? `${url}?demo=1` : url;

    fetch(destino)
      .then(async (respuesta) => {
        const cuerpo = await respuesta.json().catch(() => ({}));
        if (!respuesta.ok) {
          throw new Error(cuerpo?.error || `La peticion fallo (${respuesta.status})`);
        }
        return cuerpo as T;
      })
      .then((valor) => {
        if (!cancelado) setDatos(valor);
      })
      .catch((e: unknown) => {
        if (!cancelado) setError(e instanceof Error ? e.message : "Error desconocido");
      })
      .finally(() => {
        if (!cancelado) setCargando(false);
      });

    return () => {
      cancelado = true;
    };
  }, [url, intento]);

  const recargar = useCallback(() => setIntento((n) => n + 1), []);

  return { datos, cargando, error, recargar };
}
