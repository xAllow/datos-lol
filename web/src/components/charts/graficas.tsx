"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  LabelList,
  Line,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { usePaleta } from "@/components/tema";
import { ejeNumero } from "@/lib/formato";
import { CajaTooltip, Leyenda, SerieDef, SinDatos, useEjes } from "./base";

export type Referencia = { valor: number; etiqueta: string; color?: string; eje?: "x" | "y" };

/** Evita ticks repetidos ("1, 1, 2, 2") cuando la serie solo tiene enteros. */
function seriesEnteras(datos: Record<string, any>[], claves: string[]): boolean {
  for (const punto of datos) {
    for (const clave of claves) {
      const valor = punto[clave];
      if (valor === null || valor === undefined) continue;
      if (!Number.isInteger(Number(valor))) return false;
    }
  }
  return true;
}

type PropsBarras = {
  datos: Record<string, any>[];
  x: string;
  series: SerieDef[];
  apilado?: boolean;
  horizontal?: boolean;
  formatoValor?: (valor: number) => string;
  formatoEjeValor?: (valor: number) => string;
  formatoX?: (valor: any) => string;
  referencias?: Referencia[];
  coloresPorPunto?: (punto: Record<string, any>, indice: number) => string;
  etiquetasDirectas?: boolean;
  anguloX?: number;
  anchoEjeCategoria?: number;
  extraTooltip?: (punto: any) => React.ReactNode;
};

export function GraficaBarras({
  datos,
  x,
  series,
  apilado = false,
  horizontal = false,
  formatoValor,
  formatoEjeValor,
  formatoX,
  referencias = [],
  coloresPorPunto,
  etiquetasDirectas = false,
  anguloX = 0,
  anchoEjeCategoria = 90,
  extraTooltip,
}: PropsBarras) {
  const paleta = usePaleta();
  const ejes = useEjes();

  if (!datos.length) return <SinDatos />;

  const colorSerie = (s: SerieDef, i: number) => s.color ?? paleta.series[i % paleta.series.length];
  const conBorde = apilado || series.length > 1;
  const enteros = seriesEnteras(datos, series.map((s) => s.clave));

  const ejeCategoria = horizontal ? (
    <YAxis
      type="category"
      dataKey={x}
      tick={ejes.tick}
      tickLine={false}
      axisLine={ejes.axisLine}
      width={anchoEjeCategoria}
      tickFormatter={formatoX}
    />
  ) : (
    <XAxis
      type="category"
      dataKey={x}
      tick={{ ...ejes.tick, angle: anguloX, textAnchor: anguloX ? "end" : "middle" }}
      tickLine={false}
      axisLine={ejes.axisLine}
      height={anguloX ? 52 : 24}
      interval="preserveStartEnd"
      tickFormatter={formatoX}
    />
  );

  const ejeValor = horizontal ? (
    <XAxis
      type="number"
      tick={ejes.tick}
      tickLine={false}
      axisLine={false}
      allowDecimals={!enteros}
      tickFormatter={formatoEjeValor ?? ejeNumero}
    />
  ) : (
    <YAxis
      type="number"
      tick={ejes.tick}
      tickLine={false}
      axisLine={false}
      width={48}
      allowDecimals={!enteros}
      tickFormatter={formatoEjeValor ?? ejeNumero}
    />
  );

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={datos}
            layout={horizontal ? "vertical" : "horizontal"}
            margin={{ top: etiquetasDirectas ? 16 : 8, right: 12, bottom: 0, left: 0 }}
            barCategoryGap="18%"
          >
            <CartesianGrid stroke={ejes.grid} vertical={horizontal} horizontal={!horizontal} />
            {ejeCategoria}
            {ejeValor}
            <Tooltip
              cursor={ejes.cursor}
              content={
                <CajaTooltip
                  formatoValor={(v) => (formatoValor ? formatoValor(v) : String(v))}
                  formatoEtiqueta={formatoX}
                  extra={extraTooltip}
                />
              }
            />
            {referencias.map((r) => (
              <ReferenceLine
                key={r.etiqueta}
                {...(horizontal ? { x: r.valor } : { y: r.valor })}
                stroke={r.color ?? paleta.tinta.secundario}
                strokeDasharray="4 4"
                label={{
                  value: r.etiqueta,
                  position: horizontal ? "top" : "insideTopRight",
                  fill: paleta.tinta.secundario,
                  fontSize: 11,
                }}
              />
            ))}
            {series.map((s, i) => (
              <Bar
                key={s.clave}
                dataKey={s.clave}
                name={s.nombre}
                stackId={apilado ? "pila" : undefined}
                fill={colorSerie(s, i)}
                stroke={conBorde ? ejes.superficie : undefined}
                strokeWidth={conBorde ? 2 : 0}
                radius={
                  horizontal
                    ? apilado && i < series.length - 1
                      ? 0
                      : [0, 4, 4, 0]
                    : apilado && i < series.length - 1
                      ? 0
                      : [4, 4, 0, 0]
                }
                isAnimationActive={false}
              >
                {coloresPorPunto &&
                  datos.map((punto, indice) => (
                    <Cell key={indice} fill={coloresPorPunto(punto, indice)} />
                  ))}
                {etiquetasDirectas && (
                  <LabelList
                    dataKey={s.clave}
                    position={horizontal ? "right" : "top"}
                    fill={paleta.tinta.secundario}
                    fontSize={10}
                    formatter={(v: any) => (formatoValor ? formatoValor(Number(v)) : String(v))}
                  />
                )}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      {series.length > 1 && (
        <Leyenda series={series.map((s, i) => ({ nombre: s.nombre, color: colorSerie(s, i) }))} />
      )}
    </div>
  );
}

type PropsLineas = {
  datos: Record<string, any>[];
  x: string;
  series: (SerieDef & { tipo?: "linea" | "area" | "barra"; punteada?: boolean })[];
  formatoValor?: (valor: number) => string;
  formatoEjeValor?: (valor: number) => string;
  formatoX?: (valor: any) => string;
  referencias?: Referencia[];
  puntos?: boolean;
};

export function GraficaLineas({
  datos,
  x,
  series,
  formatoValor,
  formatoEjeValor,
  formatoX,
  referencias = [],
  puntos = false,
}: PropsLineas) {
  const paleta = usePaleta();
  const ejes = useEjes();

  if (!datos.length) return <SinDatos />;

  const colorSerie = (s: SerieDef, i: number) => s.color ?? paleta.series[i % paleta.series.length];
  const enteros = seriesEnteras(datos, series.map((s) => s.clave));

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={datos} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={ejes.grid} vertical={false} />
            <XAxis
              dataKey={x}
              tick={ejes.tick}
              tickLine={false}
              axisLine={ejes.axisLine}
              height={24}
              minTickGap={24}
              tickFormatter={formatoX}
            />
            <YAxis
              tick={ejes.tick}
              tickLine={false}
              axisLine={false}
              width={48}
              allowDecimals={!enteros}
              tickFormatter={formatoEjeValor ?? ejeNumero}
            />
            <Tooltip
              cursor={{ stroke: paleta.tinta.eje, strokeWidth: 1 }}
              content={
                <CajaTooltip
                  formatoValor={(v) => (formatoValor ? formatoValor(v) : String(v))}
                  formatoEtiqueta={formatoX}
                />
              }
            />
            {referencias.map((r) => (
              <ReferenceLine
                key={r.etiqueta}
                y={r.valor}
                stroke={r.color ?? paleta.tinta.secundario}
                strokeDasharray="4 4"
                label={{
                  value: r.etiqueta,
                  position: "insideTopRight",
                  fill: paleta.tinta.secundario,
                  fontSize: 11,
                }}
              />
            ))}
            {series.map((s, i) => {
              const color = colorSerie(s, i);
              if (s.tipo === "barra") {
                return (
                  <Bar
                    key={s.clave}
                    dataKey={s.clave}
                    name={s.nombre}
                    fill={color}
                    radius={[4, 4, 0, 0]}
                    isAnimationActive={false}
                  />
                );
              }
              if (s.tipo === "area") {
                return (
                  <Area
                    key={s.clave}
                    dataKey={s.clave}
                    name={s.nombre}
                    stroke={color}
                    strokeWidth={2}
                    fill={color}
                    fillOpacity={0.12}
                    dot={false}
                    isAnimationActive={false}
                  />
                );
              }
              return (
                <Line
                  key={s.clave}
                  dataKey={s.clave}
                  name={s.nombre}
                  stroke={color}
                  strokeWidth={2}
                  strokeDasharray={s.punteada ? "5 4" : undefined}
                  dot={puntos ? { r: 4, fill: color, stroke: ejes.superficie, strokeWidth: 2 } : false}
                  activeDot={{ r: 5, stroke: ejes.superficie, strokeWidth: 2 }}
                  connectNulls
                  isAnimationActive={false}
                />
              );
            })}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {series.length > 1 && (
        <Leyenda series={series.map((s, i) => ({ nombre: s.nombre, color: colorSerie(s, i) }))} />
      )}
    </div>
  );
}

export function GraficaArea({
  datos,
  x,
  clave,
  nombre,
  color,
  formatoValor,
  formatoX,
}: {
  datos: Record<string, any>[];
  x: string;
  clave: string;
  nombre: string;
  color?: string;
  formatoValor?: (valor: number) => string;
  formatoX?: (valor: any) => string;
}) {
  const paleta = usePaleta();
  const ejes = useEjes();
  if (!datos.length) return <SinDatos />;
  const tono = color ?? paleta.series[0];

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={datos} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`grad-${clave}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={tono} stopOpacity={0.28} />
            <stop offset="100%" stopColor={tono} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={ejes.grid} vertical={false} />
        <XAxis
          dataKey={x}
          tick={ejes.tick}
          tickLine={false}
          axisLine={ejes.axisLine}
          height={24}
          minTickGap={28}
          tickFormatter={formatoX}
        />
        <YAxis tick={ejes.tick} tickLine={false} axisLine={false} width={56} tickFormatter={ejeNumero} />
        <Tooltip
          cursor={{ stroke: paleta.tinta.eje, strokeWidth: 1 }}
          content={
            <CajaTooltip
              formatoValor={(v) => (formatoValor ? formatoValor(v) : String(v))}
              formatoEtiqueta={formatoX}
            />
          }
        />
        <Area
          dataKey={clave}
          name={nombre}
          stroke={tono}
          strokeWidth={2}
          fill={`url(#grad-${clave})`}
          dot={false}
          activeDot={{ r: 5, stroke: ejes.superficie, strokeWidth: 2 }}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function GraficaDonut({
  datos,
  formatoValor,
  centro,
}: {
  datos: { nombre: string; valor: number; color?: string }[];
  formatoValor?: (valor: number) => string;
  centro?: { valor: string; etiqueta: string; color?: string };
}) {
  const paleta = usePaleta();
  const ejes = useEjes();
  const total = datos.reduce((acc, d) => acc + d.valor, 0);

  if (!datos.length || total <= 0) return <SinDatos />;

  const conColor = datos.map((d, i) => ({ ...d, color: d.color ?? paleta.series[i % paleta.series.length] }));

  return (
    <div className="flex h-full flex-col">
      <div className="relative min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={conColor}
              dataKey="valor"
              nameKey="nombre"
              innerRadius="62%"
              outerRadius="88%"
              paddingAngle={2}
              stroke={ejes.superficie}
              strokeWidth={2}
              isAnimationActive={false}
            >
              {conColor.map((d) => (
                <Cell key={d.nombre} fill={d.color} />
              ))}
            </Pie>
            <Tooltip
              content={
                <CajaTooltip
                  formatoValor={(v) =>
                    `${formatoValor ? formatoValor(v) : v} (${((v / total) * 100).toFixed(1)}%)`
                  }
                />
              }
            />
          </PieChart>
        </ResponsiveContainer>
        {centro && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span
              className="tabular text-2xl font-semibold leading-none"
              style={{ color: centro.color ?? "var(--tinta)" }}
            >
              {centro.valor}
            </span>
            <span className="mt-1 text-[11px]" style={{ color: "var(--tinta-3)" }}>
              {centro.etiqueta}
            </span>
          </div>
        )}
      </div>
      <Leyenda series={conColor.map((d) => ({ nombre: d.nombre, color: d.color! }))} />
    </div>
  );
}

export function GraficaDispersion({
  grupos,
  x,
  y,
  nombreX,
  nombreY,
  formatoX,
  formatoY,
}: {
  grupos: { nombre: string; color?: string; datos: Record<string, any>[] }[];
  x: string;
  y: string;
  nombreX: string;
  nombreY: string;
  formatoX?: (valor: number) => string;
  formatoY?: (valor: number) => string;
}) {
  const paleta = usePaleta();
  const ejes = useEjes();

  const conColor = grupos.map((g, i) => ({ ...g, color: g.color ?? paleta.series[i % paleta.series.length] }));
  const vacio = conColor.every((g) => !g.datos.length);
  if (vacio) return <SinDatos />;

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            <CartesianGrid stroke={ejes.grid} />
            <XAxis
              type="number"
              dataKey={x}
              name={nombreX}
              tick={ejes.tick}
              tickLine={false}
              axisLine={ejes.axisLine}
              height={24}
              tickFormatter={formatoX}
            />
            <YAxis
              type="number"
              dataKey={y}
              name={nombreY}
              tick={ejes.tick}
              tickLine={false}
              axisLine={false}
              width={52}
              tickFormatter={formatoY}
            />
            <ZAxis range={[36, 36]} />
            <Tooltip
              cursor={{ strokeDasharray: "3 3", stroke: paleta.tinta.eje }}
              content={
                <CajaTooltip
                  formatoValor={(v, clave) =>
                    clave === x ? (formatoX ? formatoX(v) : String(v)) : formatoY ? formatoY(v) : String(v)
                  }
                />
              }
            />
            {conColor.map((g) => (
              <Scatter
                key={g.nombre}
                name={g.nombre}
                data={g.datos}
                fill={g.color}
                fillOpacity={0.65}
                stroke={ejes.superficie}
                strokeWidth={1}
                isAnimationActive={false}
              />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <Leyenda series={conColor.map((g) => ({ nombre: g.nombre, color: g.color! }))} />
    </div>
  );
}
