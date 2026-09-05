"use client";

import { useMemo, useState } from "react";
import { Tablero, type DefinicionPanel } from "@/components/tablero";
import { Cargando, ErrorCarga, Vacio } from "@/components/estados";
import { Buscador, Deslizador, MultiSelector, RangoFechas, Segmentado } from "@/components/controles";
import { GraficaArea, GraficaBarras, GraficaDonut } from "@/components/charts/graficas";
import { CalendarioAnual, ListaBarras, RejillaKpis, Tabla } from "@/components/charts/visuales";
import { usePaleta } from "@/components/tema";
import { useDatos } from "@/lib/datos";
import { euros, miles } from "@/lib/formato";
import {
  DIAS_CORTOS,
  DIAS_ES,
  MESES_ES,
  claveDia,
  formatoCorto,
  formatoMes,
  indiceDiaSemana,
} from "@/lib/fechas";
import type { Movimiento, RespuestaFinanzas } from "@/lib/tipos";

export function PestanaFinanzas() {
  const { datos, cargando, error, recargar } = useDatos<RespuestaFinanzas>("/api/finanzas");
  const paleta = usePaleta();

  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [preset, setPreset] = useState("todo");
  const [meses, setMeses] = useState<string[]>([]);
  const [categorias, setCategorias] = useState<string[]>([]);
  const [tipo, setTipo] = useState("todos");
  const [busqueda, setBusqueda] = useState("");
  const [importeMinimo, setImporteMinimo] = useState(0);

  const todos = useMemo(() => datos?.movimientos ?? [], [datos]);

  const aplicarPreset = (valor: string) => {
    setPreset(valor);
    if (!todos.length) return;
    const ultimo = new Date(todos[todos.length - 1].t);
    if (valor === "todo") {
      setDesde("");
      setHasta("");
      return;
    }
    if (valor === "anio") {
      setDesde(`${ultimo.getFullYear()}-01-01`);
      setHasta(claveDia(ultimo));
      return;
    }
    const dias = valor === "30" ? 30 : 90;
    const inicio = new Date(ultimo);
    inicio.setDate(inicio.getDate() - dias + 1);
    setDesde(claveDia(inicio));
    setHasta(claveDia(ultimo));
  };

  const opcionesCategoria = useMemo(() => {
    const cuenta = new Map<string, number>();
    for (const m of todos) cuenta.set(m.categoria, (cuenta.get(m.categoria) ?? 0) + 1);
    return [...cuenta.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([categoria, n]) => ({ valor: categoria, texto: `${categoria} (${n})` }));
  }, [todos]);

  const movimientos = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    return todos.filter((m) => {
      if (desde && m.dia < desde) return false;
      if (hasta && m.dia > hasta) return false;
      if (categorias.length && !categorias.includes(m.categoria)) return false;
      if (tipo === "ingresos" && m.importe <= 0) return false;
      if (tipo === "gastos" && m.importe >= 0) return false;
      if (Math.abs(m.importe) < importeMinimo) return false;
      if (meses.length && !meses.includes(String(new Date(m.t).getMonth()))) return false;
      if (texto && !m.concepto.toLowerCase().includes(texto)) return false;
      return true;
    });
  }, [todos, desde, hasta, categorias, tipo, importeMinimo, meses, busqueda]);

  const resumen = useMemo(() => {
    const ingresos = movimientos.filter((m) => m.importe > 0).reduce((a, m) => a + m.importe, 0);
    const gastos = movimientos.filter((m) => m.importe < 0).reduce((a, m) => a + m.importe, 0);
    const dias = new Set(movimientos.map((m) => m.dia)).size;
    return {
      saldoActual: todos.length ? todos[todos.length - 1].saldo : 0,
      ingresos,
      gastos,
      ahorro: ingresos + gastos,
      movimientos: movimientos.length,
      gastoDiario: dias ? gastos / dias : 0,
    };
  }, [movimientos, todos]);

  const evolucionSaldo = useMemo(
    () => movimientos.map((m) => ({ dia: m.dia, saldo: m.saldo, concepto: m.concepto })),
    [movimientos],
  );

  const porMes = useMemo(() => {
    const mapa = new Map<string, { ingresos: number; gastos: number }>();
    for (const m of movimientos) {
      const clave = m.dia.slice(0, 7);
      const previo = mapa.get(clave) ?? { ingresos: 0, gastos: 0 };
      if (m.importe > 0) previo.ingresos += m.importe;
      else previo.gastos += Math.abs(m.importe);
      mapa.set(clave, previo);
    }
    return [...mapa.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([mes, v]) => ({ mes, ...v, ahorro: v.ingresos - v.gastos }));
  }, [movimientos]);

  const porCategoria = useMemo(() => {
    const mapa = new Map<string, { total: number; movimientos: number }>();
    for (const m of movimientos) {
      if (m.importe >= 0) continue;
      const previo = mapa.get(m.categoria) ?? { total: 0, movimientos: 0 };
      previo.total += Math.abs(m.importe);
      previo.movimientos += 1;
      mapa.set(m.categoria, previo);
    }
    return [...mapa.entries()]
      .map(([categoria, v]) => ({ categoria, ...v }))
      .sort((a, b) => b.total - a.total);
  }, [movimientos]);

  const donutCategorias = useMemo(() => {
    const principales = porCategoria.slice(0, 7);
    const resto = porCategoria.slice(7).reduce((a, c) => a + c.total, 0);
    const items = principales.map((c, i) => ({
      nombre: c.categoria,
      valor: Number(c.total.toFixed(2)),
      color: paleta.series[i % paleta.series.length],
    }));
    if (resto > 0) items.push({ nombre: "Otras", valor: Number(resto.toFixed(2)), color: paleta.tinta.eje });
    return items;
  }, [porCategoria, paleta]);

  const topConceptos = useMemo(() => {
    const mapa = new Map<string, { total: number; veces: number }>();
    for (const m of movimientos) {
      if (m.importe >= 0) continue;
      const previo = mapa.get(m.concepto) ?? { total: 0, veces: 0 };
      previo.total += Math.abs(m.importe);
      previo.veces += 1;
      mapa.set(m.concepto, previo);
    }
    return [...mapa.entries()]
      .sort((a, b) => b[1].total - a[1].total)
      .slice(0, 12)
      .map(([concepto, v]) => ({
        etiqueta: concepto,
        valor: v.total,
        detalle: `${v.veces} movimiento${v.veces === 1 ? "" : "s"}`,
      }));
  }, [movimientos]);

  const porDiaSemana = useMemo(() => {
    const cubos = DIAS_ES.map(() => ({ gastos: 0, ingresos: 0 }));
    for (const m of movimientos) {
      const idx = indiceDiaSemana(new Date(m.t));
      if (m.importe < 0) cubos[idx].gastos += Math.abs(m.importe);
      else cubos[idx].ingresos += m.importe;
    }
    return DIAS_CORTOS.map((dia, i) => ({ dia, ...cubos[i] }));
  }, [movimientos]);

  const calendario = useMemo(() => {
    const mapa = new Map<string, number>();
    for (const m of movimientos) {
      if (m.importe >= 0) continue;
      mapa.set(m.dia, (mapa.get(m.dia) ?? 0) + Math.abs(m.importe));
    }
    const anios = [...new Set(movimientos.map((m) => Number(m.dia.slice(0, 4))))];
    return { mapa, anio: anios.length ? Math.max(...anios) : new Date().getFullYear() };
  }, [movimientos]);

  if (cargando) return <Cargando mensaje="Cargando movimientos bancarios..." />;
  if (error) return <ErrorCarga mensaje={error} onReintentar={recargar} />;
  if (!todos.length) return <Vacio mensaje="No hay movimientos bancarios disponibles." />;

  const filtros = (
    <>
      <Segmentado
        etiqueta="Periodo"
        valor={preset}
        onChange={aplicarPreset}
        opciones={[
          { valor: "30", texto: "30 d" },
          { valor: "90", texto: "90 d" },
          { valor: "anio", texto: "Año" },
          { valor: "todo", texto: "Todo" },
        ]}
      />
      <RangoFechas
        desde={desde}
        hasta={hasta}
        onChange={(d, h) => {
          setDesde(d);
          setHasta(h);
          setPreset("personalizado");
        }}
      />
      <MultiSelector
        etiqueta="Meses"
        valores={meses}
        onChange={setMeses}
        opciones={MESES_ES.map((m, i) => ({ valor: String(i), texto: m }))}
      />
      <MultiSelector
        etiqueta="Categoría"
        valores={categorias}
        onChange={setCategorias}
        opciones={opcionesCategoria}
        ancho="w-52"
      />
      <Segmentado
        etiqueta="Tipo"
        valor={tipo}
        onChange={setTipo}
        opciones={[
          { valor: "todos", texto: "Todo" },
          { valor: "ingresos", texto: "Ingresos" },
          { valor: "gastos", texto: "Gastos" },
        ]}
      />
      <Deslizador
        etiqueta="Importe mínimo"
        valor={importeMinimo}
        min={0}
        max={500}
        paso={10}
        onChange={setImporteMinimo}
        formato={(v) => `${v} €`}
        ancho="w-32"
      />
      <Buscador etiqueta="Concepto" valor={busqueda} onChange={setBusqueda} marcador="Buscar concepto..." />
    </>
  );

  const paneles: DefinicionPanel[] = [
    {
      id: "resumen",
      titulo: "Resumen",
      ayuda: `${movimientos.length} movimientos filtrados`,
      base: { x: 0, y: 0, w: 12, h: 3, minH: 3 },
      contenido: (
        <RejillaKpis
          items={[
            { etiqueta: "Saldo actual", valor: euros(resumen.saldoActual) },
            { etiqueta: "Ingresos", valor: euros(resumen.ingresos), color: paleta.estado.bueno },
            { etiqueta: "Gastos", valor: euros(resumen.gastos), color: paleta.estado.critico },
            {
              etiqueta: "Ahorro",
              valor: euros(resumen.ahorro),
              color: resumen.ahorro >= 0 ? paleta.estado.bueno : paleta.estado.critico,
            },
            { etiqueta: "Movimientos", valor: miles(resumen.movimientos) },
            { etiqueta: "Gasto por día activo", valor: euros(resumen.gastoDiario) },
          ]}
        />
      ),
    },
    {
      id: "saldo",
      titulo: "Evolución del saldo",
      base: { x: 0, y: 3, w: 8, h: 8, minH: 5 },
      contenido: (
        <GraficaArea
          datos={evolucionSaldo}
          x="dia"
          clave="saldo"
          nombre="Saldo"
          formatoValor={euros}
          formatoX={(v) => formatoCorto(String(v))}
        />
      ),
    },
    {
      id: "categorias-donut",
      titulo: "Reparto de gastos",
      ayuda: "por categoría",
      base: { x: 8, y: 3, w: 4, h: 8, minH: 5 },
      contenido: <GraficaDonut datos={donutCategorias} formatoValor={euros} />,
    },
    {
      id: "mensual",
      titulo: "Ingresos y gastos por mes",
      base: { x: 0, y: 11, w: 8, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porMes}
          x="mes"
          series={[
            { clave: "ingresos", nombre: "Ingresos", color: paleta.estado.bueno },
            { clave: "gastos", nombre: "Gastos", color: paleta.estado.critico },
          ]}
          formatoValor={euros}
          formatoEjeValor={(v) => `${Math.round(v)}`}
          formatoX={(v) => formatoMes(String(v))}
          anguloX={-45}
        />
      ),
    },
    {
      id: "ahorro",
      titulo: "Ahorro neto mensual",
      base: { x: 8, y: 11, w: 4, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porMes}
          x="mes"
          series={[{ clave: "ahorro", nombre: "Ahorro" }]}
          formatoValor={euros}
          formatoEjeValor={(v) => `${Math.round(v)}`}
          formatoX={(v) => formatoMes(String(v))}
          anguloX={-45}
          coloresPorPunto={(punto) =>
            Number(punto.ahorro) >= 0 ? paleta.estado.bueno : paleta.estado.critico
          }
        />
      ),
    },
    {
      id: "top-categorias",
      titulo: "Gasto por categoría",
      base: { x: 0, y: 18, w: 4, h: 8, minH: 4 },
      contenido: (
        <ListaBarras
          items={porCategoria.map((c) => ({
            etiqueta: c.categoria,
            valor: c.total,
            detalle: `${c.movimientos} movimientos`,
          }))}
          formatoValor={euros}
          color={paleta.series[1]}
        />
      ),
    },
    {
      id: "top-conceptos",
      titulo: "Conceptos con más gasto",
      base: { x: 4, y: 18, w: 4, h: 8, minH: 4 },
      contenido: <ListaBarras items={topConceptos} formatoValor={euros} color={paleta.series[4]} />,
    },
    {
      id: "dia-semana",
      titulo: "Gasto por día de la semana",
      base: { x: 8, y: 18, w: 4, h: 8, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porDiaSemana}
          x="dia"
          series={[{ clave: "gastos", nombre: "Gastos", color: paleta.series[1] }]}
          formatoValor={euros}
          formatoEjeValor={(v) => `${Math.round(v)}`}
          extraTooltip={(punto) => `${euros(punto.ingresos)} de ingresos`}
        />
      ),
    },
    {
      id: "calendario",
      titulo: `Gasto diario ${calendario.anio}`,
      base: { x: 0, y: 26, w: 12, h: 5, minH: 4 },
      contenido: (
        <CalendarioAnual
          anio={calendario.anio}
          valoresPorDia={calendario.mapa}
          formatoValor={euros}
          etiqueta="Gasto por día"
        />
      ),
    },
    {
      id: "movimientos",
      titulo: "Movimientos",
      ayuda: "ordenados del más reciente al más antiguo",
      base: { x: 0, y: 32, w: 12, h: 10, minH: 5 },
      contenido: (
        <Tabla
          filas={[...movimientos].reverse().slice(0, 300)}
          claveFila={(fila, i) => `${fila.t}-${i}`}
          columnas={[
            { clave: "dia", titulo: "Fecha", render: (f: Movimiento) => formatoCorto(f.dia) },
            { clave: "concepto", titulo: "Concepto" },
            { clave: "categoria", titulo: "Categoría" },
            {
              clave: "importe",
              titulo: "Importe",
              alineacion: "derecha",
              render: (f: Movimiento) => (
                <span style={{ color: f.importe >= 0 ? paleta.estado.bueno : paleta.estado.critico }}>
                  {euros(f.importe)}
                </span>
              ),
            },
            { clave: "saldo", titulo: "Saldo", alineacion: "derecha", render: (f: Movimiento) => euros(f.saldo) },
          ]}
        />
      ),
    },
  ];

  return <Tablero claveAlmacen="finanzas" version={2} paneles={paneles} filtros={filtros} />;
}
