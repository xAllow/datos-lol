"use client";

import { Fragment, useMemo, useState } from "react";
import { usePaleta } from "@/components/tema";
import { SinDatos } from "./base";
import { DIAS_CORTOS, MESES_CORTOS, claveDia, desdeClaveDia, indiceDiaSemana } from "@/lib/fechas";

/** Cifra destacada. Sin grafico: el numero es el mensaje. */
export function Kpi({
  etiqueta,
  valor,
  ayuda,
  color,
}: {
  etiqueta: string;
  valor: string;
  ayuda?: string;
  color?: string;
}) {
  return (
    <div className="flex h-full flex-col justify-center">
      <span className="etiqueta-control">{etiqueta}</span>
      <span
        className="mt-1 truncate text-[28px] font-semibold leading-tight"
        style={{ color: color ?? "var(--tinta)" }}
        title={valor}
      >
        {valor}
      </span>
      {ayuda && (
        <span className="mt-0.5 truncate text-[11px]" style={{ color: "var(--tinta-3)" }} title={ayuda}>
          {ayuda}
        </span>
      )}
    </div>
  );
}

export function RejillaKpis({
  items,
  ancha = true,
}: {
  items: React.ComponentProps<typeof Kpi>[];
  /** false para paneles estrechos: los breakpoints de Tailwind miden el viewport, no el panel. */
  ancha?: boolean;
}) {
  return (
    <div
      className={`grid h-full gap-x-4 gap-y-2 ${
        ancha ? "grid-cols-2 sm:grid-cols-3 lg:grid-cols-6" : "grid-cols-2"
      }`}
    >
      {items.map((item) => (
        <Kpi key={item.etiqueta} {...item} />
      ))}
    </div>
  );
}

export type ColumnaTabla<T> = {
  clave: keyof T & string;
  titulo: string;
  alineacion?: "izquierda" | "derecha";
  ancho?: string;
  render?: (fila: T) => React.ReactNode;
};

export function Tabla<T extends Record<string, any>>({
  columnas,
  filas,
  claveFila,
}: {
  columnas: ColumnaTabla<T>[];
  filas: T[];
  claveFila: (fila: T, indice: number) => string;
}) {
  if (!filas.length) return <SinDatos />;

  return (
    <div className="scroll-fino h-full overflow-auto">
      <table className="w-full border-collapse text-[12px]">
        <thead className="sticky top-0 z-10" style={{ background: "var(--superficie)" }}>
          <tr>
            {columnas.map((c, j) => (
              <th
                key={`${c.clave}-${j}`}
                className="border-b px-2 py-1.5 text-left font-medium"
                style={{
                  color: "var(--tinta-3)",
                  textAlign: c.alineacion === "derecha" ? "right" : "left",
                  width: c.ancho,
                }}
              >
                {c.titulo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, i) => (
            <tr key={claveFila(fila, i)} className="hover:bg-[var(--superficie-2)]">
              {columnas.map((c, j) => (
                <td
                  key={`${c.clave}-${j}`}
                  className="tabular whitespace-nowrap border-b px-2 py-1.5"
                  style={{
                    color: "var(--tinta-2)",
                    textAlign: c.alineacion === "derecha" ? "right" : "left",
                    borderColor: "var(--borde)",
                  }}
                >
                  {c.render ? c.render(fila) : String(fila[c.clave] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type Celda = { fila: string; columna: string; valor: number | null };

export function MapaCalor({
  filas,
  columnas,
  valores,
  formatoValor,
  etiquetaValor,
}: {
  filas: string[];
  columnas: string[];
  /** valores[fila][columna] */
  valores: (number | null)[][];
  formatoValor: (valor: number) => string;
  etiquetaValor: string;
}) {
  const paleta = usePaleta();
  const [activa, setActiva] = useState<Celda | null>(null);

  const { min, max } = useMemo(() => {
    const planos = valores.flat().filter((v): v is number => v !== null && Number.isFinite(v));
    if (!planos.length) return { min: 0, max: 0 };
    return { min: Math.min(...planos), max: Math.max(...planos) };
  }, [valores]);

  if (!filas.length || !columnas.length || max === 0) return <SinDatos />;

  const normal = (v: number) => (max === min ? 0.6 : (v - min) / (max - min));

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="min-h-0 flex-1 overflow-auto scroll-fino">
        <div
          className="grid h-full min-w-full gap-[2px]"
          style={{ gridTemplateColumns: `auto repeat(${columnas.length}, minmax(0, 1fr))` }}
        >
          <div />
          {columnas.map((c) => (
            <div key={c} className="truncate pb-1 text-center text-[10px]" style={{ color: "var(--tinta-3)" }}>
              {c}
            </div>
          ))}
          {filas.map((f, i) => (
            <Fragment key={`fila-${f}-${i}`}>
              <div
                className="flex items-center pr-2 text-[10px] whitespace-nowrap"
                style={{ color: "var(--tinta-3)" }}
              >
                {f}
              </div>
              {columnas.map((c, j) => {
                const valor = valores[i]?.[j] ?? null;
                const activo = activa?.fila === f && activa?.columna === c;
                return (
                  <div
                    key={`${f}-${c}`}
                    className="relative min-h-[16px] rounded-[3px]"
                    style={{
                      background: valor === null ? "var(--superficie-2)" : paleta.secuencial(normal(valor)),
                      outline: activo ? `2px solid ${paleta.tinta.primario}` : "none",
                      outlineOffset: -2,
                    }}
                    onMouseEnter={() => setActiva({ fila: f, columna: c, valor })}
                    onMouseLeave={() => setActiva(null)}
                    title={`${f} · ${c}: ${valor === null ? "sin datos" : formatoValor(valor)}`}
                  />
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>
      <div className="flex items-center justify-between gap-3 text-[10px]" style={{ color: "var(--tinta-3)" }}>
        <span className="truncate">
          {activa
            ? `${activa.fila} · ${activa.columna}: ${activa.valor === null ? "sin datos" : formatoValor(activa.valor)}`
            : etiquetaValor}
        </span>
        <span className="flex items-center gap-1">
          {formatoValor(min)}
          <span className="flex">
            {Array.from({ length: 7 }, (_, k) => (
              <span
                key={k}
                className="h-2.5 w-3"
                style={{ background: paleta.secuencial(k / 6) }}
              />
            ))}
          </span>
          {formatoValor(max)}
        </span>
      </div>
    </div>
  );
}

/** Calendario anual estilo contribuciones: una columna por semana ISO. */
export function CalendarioAnual({
  anio,
  valoresPorDia,
  formatoValor,
  etiqueta,
}: {
  anio: number;
  valoresPorDia: Map<string, number>;
  formatoValor: (valor: number) => string;
  etiqueta: string;
}) {
  const paleta = usePaleta();
  const [activo, setActivo] = useState<{ dia: string; valor: number } | null>(null);

  const semanas = useMemo(() => {
    const inicio = new Date(anio, 0, 1);
    const fin = new Date(anio, 11, 31);
    const primerLunes = new Date(inicio);
    primerLunes.setDate(inicio.getDate() - indiceDiaSemana(inicio));

    const columnas: { dia: string; mes: number; dentro: boolean }[][] = [];
    const cursor = new Date(primerLunes);
    while (cursor <= fin) {
      const semana: { dia: string; mes: number; dentro: boolean }[] = [];
      for (let d = 0; d < 7; d++) {
        semana.push({
          dia: claveDia(cursor),
          mes: cursor.getMonth(),
          dentro: cursor.getFullYear() === anio,
        });
        cursor.setDate(cursor.getDate() + 1);
      }
      columnas.push(semana);
    }
    return columnas;
  }, [anio]);

  const valores = [...valoresPorDia.values()].filter((v) => Number.isFinite(v));
  const max = valores.length ? Math.max(...valores) : 0;
  const min = valores.length ? Math.min(...valores) : 0;

  if (!valores.length) return <SinDatos mensaje={`Sin datos en ${anio}`} />;

  const etiquetasMes: { indice: number; mes: number }[] = [];
  semanas.forEach((semana, i) => {
    const primeroDentro = semana.find((d) => d.dentro);
    if (!primeroDentro) return;
    const mes = primeroDentro.mes;
    if (!etiquetasMes.length || etiquetasMes[etiquetasMes.length - 1].mes !== mes) {
      etiquetasMes.push({ indice: i, mes });
    }
  });

  return (
    <div className="flex h-full flex-col gap-1">
      <div className="scroll-fino flex min-h-0 flex-1 items-center overflow-x-auto">
        <div className="flex min-w-max flex-col gap-1">
          <div className="flex gap-[3px] pl-8">
            {semanas.map((_, i) => {
              const et = etiquetasMes.find((e) => e.indice === i);
              return (
                <span key={i} className="w-[11px] text-[9px]" style={{ color: "var(--tinta-3)" }}>
                  {et ? MESES_CORTOS[et.mes] : ""}
                </span>
              );
            })}
          </div>
          <div className="flex gap-[3px]">
            <div className="flex w-8 flex-col gap-[3px] pr-1">
              {DIAS_CORTOS.map((d, i) => (
                <span
                  key={d}
                  className="h-[11px] text-[9px] leading-[11px]"
                  style={{ color: "var(--tinta-3)", visibility: i % 2 ? "visible" : "hidden" }}
                >
                  {d}
                </span>
              ))}
            </div>
            {semanas.map((semana, i) => (
              <div key={i} className="flex flex-col gap-[3px]">
                {semana.map((celda) => {
                  const valor = valoresPorDia.get(celda.dia);
                  const tiene = celda.dentro && valor !== undefined;
                  const t = tiene && max > min ? (valor! - min) / (max - min) : tiene ? 0.6 : 0;
                  return (
                    <span
                      key={celda.dia}
                      className="h-[11px] w-[11px] rounded-[2px]"
                      style={{
                        background: tiene ? paleta.secuencial(t) : "var(--superficie-2)",
                        opacity: celda.dentro ? 1 : 0.35,
                      }}
                      title={`${celda.dia}: ${tiene ? formatoValor(valor!) : "sin datos"}`}
                      onMouseEnter={() => tiene && setActivo({ dia: celda.dia, valor: valor! })}
                      onMouseLeave={() => setActivo(null)}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="flex items-center justify-between text-[10px]" style={{ color: "var(--tinta-3)" }}>
        <span>
          {activo
            ? `${desdeClaveDia(activo.dia).toLocaleDateString("es-ES")}: ${formatoValor(activo.valor)}`
            : etiqueta}
        </span>
        <span className="flex items-center gap-1">
          {formatoValor(min)}
          <span className="flex">
            {Array.from({ length: 7 }, (_, k) => (
              <span key={k} className="h-2.5 w-3" style={{ background: paleta.secuencial(k / 6) }} />
            ))}
          </span>
          {formatoValor(max)}
        </span>
      </div>
    </div>
  );
}

/** Barras horizontales compactas para rankings dentro de un panel estrecho. */
export function ListaBarras({
  items,
  formatoValor,
  color,
}: {
  items: { etiqueta: string; valor: number; detalle?: string }[];
  formatoValor: (valor: number) => string;
  color?: string;
}) {
  const paleta = usePaleta();
  if (!items.length) return <SinDatos />;
  const max = Math.max(...items.map((i) => Math.abs(i.valor)), 1);
  const tono = color ?? paleta.series[0];

  return (
    <div className="scroll-fino flex h-full flex-col gap-1.5 overflow-auto pr-1">
      {items.map((item) => (
        <div key={item.etiqueta} className="flex flex-col gap-0.5">
          <div className="flex items-baseline justify-between gap-2 text-[12px]">
            <span className="truncate" style={{ color: "var(--tinta-2)" }} title={item.etiqueta}>
              {item.etiqueta}
            </span>
            <span className="tabular shrink-0 font-medium" style={{ color: "var(--tinta)" }}>
              {formatoValor(item.valor)}
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ background: "var(--superficie-2)" }}>
            <div
              className="h-full rounded-full"
              style={{ width: `${(Math.abs(item.valor) / max) * 100}%`, background: tono }}
            />
          </div>
          {item.detalle && (
            <span className="text-[10px]" style={{ color: "var(--tinta-3)" }}>
              {item.detalle}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
