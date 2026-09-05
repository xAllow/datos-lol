"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronDown, ChevronLeft, ChevronRight, Search, X } from "lucide-react";

export function Campo({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="etiqueta-control">{etiqueta}</span>
      {children}
    </label>
  );
}

export type Opcion = { valor: string; texto: string };

export function Selector({
  etiqueta,
  valor,
  opciones,
  onChange,
  ancho = "w-36",
}: {
  etiqueta: string;
  valor: string;
  opciones: Opcion[];
  onChange: (valor: string) => void;
  ancho?: string;
}) {
  return (
    <Campo etiqueta={etiqueta}>
      <select className={`control ${ancho}`} value={valor} onChange={(e) => onChange(e.target.value)}>
        {opciones.map((o) => (
          <option key={o.valor} value={o.valor}>
            {o.texto}
          </option>
        ))}
      </select>
    </Campo>
  );
}

export function Segmentado({
  etiqueta,
  valor,
  opciones,
  onChange,
}: {
  etiqueta: string;
  valor: string;
  opciones: Opcion[];
  onChange: (valor: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="etiqueta-control">{etiqueta}</span>
      <div
        className="flex h-8 items-center gap-0.5 rounded-lg border p-0.5"
        style={{ background: "var(--superficie)" }}
        role="group"
      >
        {opciones.map((o) => {
          const activo = o.valor === valor;
          return (
            <button
              key={o.valor}
              type="button"
              onClick={() => onChange(o.valor)}
              aria-pressed={activo}
              className="rounded-md px-2.5 text-xs font-medium transition-colors"
              style={{
                height: 26,
                background: activo ? "var(--superficie-2)" : "transparent",
                color: activo ? "var(--tinta)" : "var(--tinta-3)",
              }}
            >
              {o.texto}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function MultiSelector({
  etiqueta,
  valores,
  opciones,
  onChange,
  ancho = "w-44",
  textoVacio = "Todos",
}: {
  etiqueta: string;
  valores: string[];
  opciones: Opcion[];
  onChange: (valores: string[]) => void;
  ancho?: string;
  textoVacio?: string;
}) {
  const [abierto, setAbierto] = useState(false);
  const contenedor = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => {
      if (contenedor.current && !contenedor.current.contains(e.target as Node)) setAbierto(false);
    };
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAbierto(false);
    };
    document.addEventListener("mousedown", fuera);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", fuera);
      document.removeEventListener("keydown", escape);
    };
  }, [abierto]);

  const alternar = (valor: string) => {
    onChange(valores.includes(valor) ? valores.filter((v) => v !== valor) : [...valores, valor]);
  };

  const resumen =
    valores.length === 0
      ? textoVacio
      : valores.length === 1
        ? (opciones.find((o) => o.valor === valores[0])?.texto ?? valores[0])
        : `${valores.length} seleccionados`;

  return (
    <div className="flex flex-col gap-1" ref={contenedor}>
      <span className="etiqueta-control">{etiqueta}</span>
      <div className="relative">
        <button
          type="button"
          className={`control ${ancho} flex items-center justify-between gap-2 text-left`}
          onClick={() => setAbierto((v) => !v)}
          aria-expanded={abierto}
        >
          <span className="truncate" style={{ color: valores.length ? "var(--tinta)" : "var(--tinta-3)" }}>
            {resumen}
          </span>
          <ChevronDown size={14} style={{ color: "var(--tinta-3)" }} />
        </button>
        {abierto && (
          <div
            className="scroll-fino absolute left-0 z-50 mt-1 max-h-64 min-w-full overflow-auto rounded-lg border p-1"
            style={{ background: "var(--superficie)", boxShadow: "0 8px 24px rgba(0,0,0,0.16)" }}
          >
            {valores.length > 0 && (
              <button
                type="button"
                className="mb-1 flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-xs"
                style={{ color: "var(--tinta-3)" }}
                onClick={() => onChange([])}
              >
                <X size={12} /> Limpiar
              </button>
            )}
            {opciones.map((o) => {
              const activo = valores.includes(o.valor);
              return (
                <button
                  key={o.valor}
                  type="button"
                  className="flex w-full items-center gap-2 whitespace-nowrap rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-[var(--superficie-2)]"
                  onClick={() => alternar(o.valor)}
                >
                  <span
                    className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border"
                    style={{
                      background: activo ? "var(--acento)" : "transparent",
                      borderColor: activo ? "var(--acento)" : "var(--eje)",
                    }}
                  >
                    {activo && <Check size={10} color="#fff" strokeWidth={3} />}
                  </span>
                  {o.texto}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export function Deslizador({
  etiqueta,
  valor,
  min,
  max,
  paso = 1,
  onChange,
  formato = (v: number) => String(v),
  ancho = "w-40",
}: {
  etiqueta: string;
  valor: number;
  min: number;
  max: number;
  paso?: number;
  onChange: (valor: number) => void;
  formato?: (valor: number) => string;
  ancho?: string;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <span className="etiqueta-control flex items-center justify-between gap-3">
        <span>{etiqueta}</span>
        <span className="tabular" style={{ color: "var(--tinta)" }}>
          {formato(valor)}
        </span>
      </span>
      <input
        id={id}
        type="range"
        className={`${ancho} h-8 cursor-pointer accent-[var(--acento)]`}
        min={min}
        max={max}
        step={paso}
        value={valor}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

export function Buscador({
  etiqueta,
  valor,
  onChange,
  marcador = "Buscar...",
  ancho = "w-52",
}: {
  etiqueta: string;
  valor: string;
  onChange: (valor: string) => void;
  marcador?: string;
  ancho?: string;
}) {
  return (
    <Campo etiqueta={etiqueta}>
      <span className="relative flex items-center">
        <Search size={13} className="absolute left-2.5" style={{ color: "var(--tinta-3)" }} />
        <input
          type="search"
          className={`control ${ancho} pl-7`}
          value={valor}
          placeholder={marcador}
          onChange={(e) => onChange(e.target.value)}
        />
      </span>
    </Campo>
  );
}

export function RangoFechas({
  desde,
  hasta,
  onChange,
}: {
  desde: string;
  hasta: string;
  onChange: (desde: string, hasta: string) => void;
}) {
  return (
    <div className="flex items-end gap-2">
      <Campo etiqueta="Desde">
        <input
          type="date"
          className="control w-[140px]"
          value={desde}
          onChange={(e) => onChange(e.target.value, hasta)}
        />
      </Campo>
      <Campo etiqueta="Hasta">
        <input
          type="date"
          className="control w-[140px]"
          value={hasta}
          onChange={(e) => onChange(desde, e.target.value)}
        />
      </Campo>
    </div>
  );
}

export function BotonSecundario({
  children,
  onClick,
  titulo,
}: {
  children: React.ReactNode;
  onClick: () => void;
  titulo?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={titulo}
      className="control flex items-center gap-1.5 px-2.5 font-medium hover:bg-[var(--superficie-2)]"
      style={{ color: "var(--tinta-2)" }}
    >
      {children}
    </button>
  );
}

/** Cabecera para pasear mes a mes dentro de un panel: "‹ Septiembre 2026 ›" + volver a hoy. */
export function NavegadorMes({
  etiqueta,
  onAnterior,
  onSiguiente,
  onHoy,
  deshabilitarAnterior = false,
  deshabilitarSiguiente = false,
  enHoy = false,
}: {
  etiqueta: string;
  onAnterior: () => void;
  onSiguiente: () => void;
  onHoy?: () => void;
  deshabilitarAnterior?: boolean;
  deshabilitarSiguiente?: boolean;
  enHoy?: boolean;
}) {
  return (
    <div className="flex shrink-0 items-center gap-1">
      <button
        type="button"
        onClick={onAnterior}
        disabled={deshabilitarAnterior}
        aria-label="Mes anterior"
        className="control flex h-8 w-8 items-center justify-center p-0 disabled:cursor-not-allowed disabled:opacity-30"
      >
        <ChevronLeft size={14} />
      </button>
      <span
        className="tabular min-w-[120px] text-center text-[13px] font-medium"
        style={{ color: "var(--tinta)" }}
      >
        {etiqueta}
      </span>
      <button
        type="button"
        onClick={onSiguiente}
        disabled={deshabilitarSiguiente}
        aria-label="Mes siguiente"
        className="control flex h-8 w-8 items-center justify-center p-0 disabled:cursor-not-allowed disabled:opacity-30"
      >
        <ChevronRight size={14} />
      </button>
      {onHoy && !enHoy && (
        <button
          type="button"
          onClick={onHoy}
          className="control px-2.5 text-xs font-medium"
          style={{ color: "var(--tinta-2)" }}
        >
          Hoy
        </button>
      )}
    </div>
  );
}
