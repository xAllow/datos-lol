"use client";

import { usePaleta } from "@/components/tema";

export type SerieDef = { clave: string; nombre: string; color?: string };

/** Caja de tooltip compartida por todas las graficas. */
export function CajaTooltip({
  active,
  payload,
  label,
  formatoValor,
  formatoEtiqueta,
  extra,
}: {
  active?: boolean;
  payload?: any[];
  label?: any;
  formatoValor?: (valor: number, clave: string) => string;
  formatoEtiqueta?: (etiqueta: any) => string;
  extra?: (punto: any) => React.ReactNode;
}) {
  if (!active || !payload || !payload.length) return null;

  const titulo = formatoEtiqueta ? formatoEtiqueta(label) : String(label ?? "");
  const original = payload[0]?.payload;

  return (
    <div
      className="rounded-lg border px-2.5 py-2 text-[12px]"
      style={{ background: "var(--superficie)", boxShadow: "0 6px 20px rgba(0,0,0,0.18)" }}
    >
      {titulo && (
        <div className="mb-1 font-medium" style={{ color: "var(--tinta)" }}>
          {titulo}
        </div>
      )}
      <div className="flex flex-col gap-0.5">
        {payload.map((p, i) => (
          <div key={`${p.dataKey}-${i}`} className="flex items-center gap-2">
            <span
              className="h-2 w-2 shrink-0 rounded-[2px]"
              style={{ background: p.color || p.fill || "var(--tinta-3)" }}
            />
            <span style={{ color: "var(--tinta-2)" }}>{p.name}</span>
            <span className="tabular ml-auto font-medium" style={{ color: "var(--tinta)" }}>
              {formatoValor ? formatoValor(Number(p.value), String(p.dataKey)) : String(p.value)}
            </span>
          </div>
        ))}
      </div>
      {extra && original ? (
        <div className="mt-1 border-t pt-1 text-[11px]" style={{ color: "var(--tinta-3)" }}>
          {extra(original)}
        </div>
      ) : null}
    </div>
  );
}

/** Leyenda propia: siempre presente cuando hay dos o mas series. */
export function Leyenda({ series }: { series: { nombre: string; color: string }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-1">
      {series.map((s) => (
        <span key={s.nombre} className="flex items-center gap-1.5 text-[11px]" style={{ color: "var(--tinta-2)" }}>
          <span className="h-2 w-2 rounded-[2px]" style={{ background: s.color }} />
          {s.nombre}
        </span>
      ))}
    </div>
  );
}

export function SinDatos({ mensaje = "Sin datos para estos filtros" }: { mensaje?: string }) {
  return (
    <div className="flex h-full items-center justify-center text-[12px]" style={{ color: "var(--tinta-3)" }}>
      {mensaje}
    </div>
  );
}

/** Ejes con estilo recesivo comun. */
export function useEjes() {
  const { tinta } = usePaleta();
  return {
    tick: { fill: tinta.apagado, fontSize: 11 },
    axisLine: { stroke: tinta.eje },
    grid: tinta.rejilla,
    cursor: { fill: tinta.rejilla, opacity: 0.45 },
    superficie: tinta.superficie,
  };
}
