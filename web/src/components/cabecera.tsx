"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Monitor, Moon, Sun } from "lucide-react";

export type ClavePestana = "pasos" | "lol" | "actividades" | "registro" | "finanzas";

const PESTANAS: { clave: ClavePestana; texto: string }[] = [
  { clave: "pasos", texto: "Pasos" },
  { clave: "lol", texto: "League of Legends" },
  { clave: "actividades", texto: "Actividades" },
  { clave: "registro", texto: "Registro" },
  { clave: "finanzas", texto: "Finanzas" },
];

export function Cabecera({
  activa,
  onCambiar,
}: {
  activa: ClavePestana;
  onCambiar: (clave: ClavePestana) => void;
}) {
  return (
    <header
      className="sticky top-0 z-40 border-b backdrop-blur"
      style={{ background: "color-mix(in srgb, var(--plano) 88%, transparent)" }}
    >
      <div className="mx-auto flex max-w-[1800px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5 sm:px-6">
        <h1 className="text-[15px] font-semibold tracking-tight">Panel de vida</h1>

        <nav className="flex items-center gap-0.5" aria-label="Secciones">
          {PESTANAS.map((p) => {
            const activo = p.clave === activa;
            return (
              <button
                key={p.clave}
                type="button"
                onClick={() => onCambiar(p.clave)}
                aria-current={activo ? "page" : undefined}
                className="rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors"
                style={{
                  background: activo ? "var(--superficie-2)" : "transparent",
                  color: activo ? "var(--tinta)" : "var(--tinta-3)",
                }}
              >
                {p.texto}
              </button>
            );
          })}
        </nav>

        <div className="ml-auto">
          <SelectorTema />
        </div>
      </div>
    </header>
  );
}

function SelectorTema() {
  const { theme, setTheme } = useTheme();
  const [montado, setMontado] = useState(false);

  useEffect(() => setMontado(true), []);

  const opciones = [
    { valor: "light", icono: Sun, titulo: "Modo claro" },
    { valor: "dark", icono: Moon, titulo: "Modo oscuro" },
    { valor: "system", icono: Monitor, titulo: "Segun el sistema" },
  ];

  return (
    <div
      className="flex items-center gap-0.5 rounded-lg border p-0.5"
      style={{ background: "var(--superficie)" }}
      role="group"
      aria-label="Tema"
    >
      {opciones.map(({ valor, icono: Icono, titulo }) => {
        const activo = montado && theme === valor;
        return (
          <button
            key={valor}
            type="button"
            title={titulo}
            aria-label={titulo}
            aria-pressed={activo}
            onClick={() => setTheme(valor)}
            className="flex h-7 w-7 items-center justify-center rounded-md transition-colors"
            style={{
              background: activo ? "var(--superficie-2)" : "transparent",
              color: activo ? "var(--tinta)" : "var(--tinta-3)",
            }}
          >
            <Icono size={14} />
          </button>
        );
      })}
    </div>
  );
}
