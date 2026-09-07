"use client";

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { Tablero, type DefinicionPanel } from "@/components/tablero";
import { Cargando, ErrorCarga, Vacio } from "@/components/estados";
import { RangoFechas, Segmentado } from "@/components/controles";
import { GraficaBarras, GraficaLineas } from "@/components/charts/graficas";
import { RejillaKpis, Tabla } from "@/components/charts/visuales";
import type { RutaMapa } from "@/components/charts/mapa";
import { usePaleta } from "@/components/tema";
import { useDatos } from "@/lib/datos";
import { compacto, dec1, miles } from "@/lib/formato";
import { claveDia, formatoCorto } from "@/lib/fechas";
import type { Actividad, RespuestaActividades, TipoActividad } from "@/lib/tipos";

const MapaRuta = dynamic(() => import("@/components/charts/mapa").then((m) => m.MapaRuta), {
  ssr: false,
  loading: () => <Cargando mensaje="Cargando mapa..." />,
});

const TIPOS_ES: Record<TipoActividad, string> = {
  RUNNING: "Running",
  WALKING: "Caminata",
  SWIMMING: "Natación",
  TRAINING: "Entrenamiento",
};

const CATEGORIAS_DEPORTIVAS: TipoActividad[] = ["RUNNING", "WALKING", "SWIMMING"];

function formatoDuracion(segundos: number): string {
  const s = Math.max(0, Math.round(segundos));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}min`;
  const ss = s % 60;
  return `${m}min ${String(ss).padStart(2, "0")}s`;
}

function formatoRitmo(segundosPorKm: number | null | undefined): string {
  if (segundosPorKm === null || segundosPorKm === undefined || !Number.isFinite(segundosPorKm) || segundosPorKm <= 0) {
    return "—";
  }
  const m = Math.floor(segundosPorKm / 60);
  const s = Math.round(segundosPorKm % 60);
  return `${m}:${String(s).padStart(2, "0")} /km`;
}

function ritmoDesdeVelocidad(kmh: number): number | null {
  if (!kmh || kmh <= 0) return null;
  return 3600 / kmh;
}

function formatoTiempo(segundos: number | null | undefined): string {
  if (segundos === null || segundos === undefined || !Number.isFinite(segundos) || segundos <= 0) return "—";
  const s = Math.round(segundos);
  const m = Math.floor(s / 60);
  const ss = s % 60;
  return `${m}:${String(ss).padStart(2, "0")}`;
}

const MARCAS: { clave: "mejor400" | "mejor1km" | "mejor2km" | "mejor5km" | "mejor10km"; etiqueta: string }[] = [
  { clave: "mejor400", etiqueta: "400 m" },
  { clave: "mejor1km", etiqueta: "1 km" },
  { clave: "mejor2km", etiqueta: "2 km" },
  { clave: "mejor5km", etiqueta: "5 km" },
  { clave: "mejor10km", etiqueta: "10 km" },
];

const CATEGORIAS_CON_MARCA: ("RUNNING" | "WALKING")[] = ["RUNNING", "WALKING"];

function BarraZonas({
  zonas,
}: {
  zonas: { clave: string; etiqueta: string; segundos: number; color: string }[];
}) {
  const total = zonas.reduce((acc, z) => acc + z.segundos, 0);
  if (!total) return <Vacio mensaje="Sin datos de FC o ritmo en las actividades filtradas" />;

  return (
    <div className="flex h-full flex-col justify-center gap-3">
      <div className="flex h-4 w-full overflow-hidden rounded-full" style={{ background: "var(--superficie-2)" }}>
        {zonas
          .filter((z) => z.segundos > 0)
          .map((z) => (
            <div
              key={z.clave}
              style={{ width: `${(z.segundos / total) * 100}%`, background: z.color }}
              title={`${z.etiqueta}: ${formatoDuracion(z.segundos)} (${Math.round((z.segundos / total) * 100)}%)`}
            />
          ))}
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3 lg:grid-cols-5">
        {zonas.map((z) => (
          <div key={z.clave} className="flex items-center gap-1.5 text-[12px]">
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: z.color }} />
            <span className="truncate" style={{ color: "var(--tinta-2)" }}>
              {z.etiqueta}
            </span>
            <span className="tabular ml-auto shrink-0" style={{ color: "var(--tinta-3)" }}>
              {Math.round((z.segundos / total) * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function PestanaActividades() {
  const { datos, cargando, error, recargar } = useDatos<RespuestaActividades>("/api/actividades");
  const paleta = usePaleta();

  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [preset, setPreset] = useState("todo");
  const [tipo, setTipo] = useState("todas");

  const todas = useMemo(() => datos?.actividades ?? [], [datos]);

  const aplicarPreset = (valor: string) => {
    setPreset(valor);
    if (!todas.length) return;
    const ultima = new Date(todas[todas.length - 1].fecha);
    if (valor === "todo") {
      setDesde("");
      setHasta("");
      return;
    }
    if (valor === "anio") {
      setDesde(`${ultima.getFullYear()}-01-01`);
      setHasta(claveDia(ultima));
      return;
    }
    const dias = valor === "30" ? 30 : 90;
    const inicio = new Date(ultima);
    inicio.setDate(inicio.getDate() - dias + 1);
    setDesde(claveDia(inicio));
    setHasta(claveDia(ultima));
  };

  const colorTipo = (t: TipoActividad) =>
    t === "RUNNING" ? paleta.series[0] : t === "WALKING" ? paleta.series[2] : paleta.series[4];

  const filtradas = useMemo(() => {
    return todas.filter((a) => {
      const dia = claveDia(new Date(a.fecha));
      if (desde && dia < desde) return false;
      if (hasta && dia > hasta) return false;
      if (tipo !== "todas" && a.tipo !== tipo) return false;
      return true;
    });
  }, [todas, desde, hasta, tipo]);

  const deportivas = useMemo(
    () => filtradas.filter((a) => CATEGORIAS_DEPORTIVAS.includes(a.tipo)),
    [filtradas],
  );
  const entrenamientos = useMemo(() => filtradas.filter((a) => a.tipo === "TRAINING"), [filtradas]);

  const ritmoPonderado = (lista: Actividad[]): number | null => {
    const conRitmo = lista.filter((a) => a.tipo !== "SWIMMING" && a.distancia > 0 && a.velMedia > 0);
    const distanciaTotal = conRitmo.reduce((acc, a) => acc + a.distancia, 0);
    if (!distanciaTotal) return null;
    const tiempoTotal = conRitmo.reduce((acc, a) => acc + a.duracionActiva, 0);
    return tiempoTotal / distanciaTotal;
  };

  const resumen = useMemo(() => {
    const distancia = deportivas.reduce((acc, a) => acc + a.distancia, 0);
    const calorias = filtradas.reduce((acc, a) => acc + a.calorias, 0);
    const tiempoActivo = filtradas.reduce((acc, a) => acc + a.duracionActiva, 0);
    return { total: filtradas.length, distancia, calorias, tiempoActivo, ritmoMedio: ritmoPonderado(deportivas) };
  }, [filtradas, deportivas]);

  const registrosPersonales = useMemo(() => {
    return CATEGORIAS_DEPORTIVAS.map((cat) => {
      const lista = deportivas.filter((a) => a.tipo === cat);
      if (!lista.length) return null;
      return {
        tipo: cat,
        actividades: lista.length,
        ritmoMedio: ritmoPonderado(lista),
        mayorDistancia: Math.max(...lista.map((a) => a.distancia)),
        mayorDuracion: Math.max(...lista.map((a) => a.duracionActiva)),
        masCalorias: Math.max(...lista.map((a) => a.calorias)),
        fcMaxima: Math.max(...lista.map((a) => a.fcMaxima)),
      };
    }).filter((r): r is NonNullable<typeof r> => r !== null);
  }, [deportivas]);

  const mejoresMarcas = useMemo(() => {
    return MARCAS.map(({ clave, etiqueta }) => {
      const fila: { distancia: string; RUNNING: number | null; WALKING: number | null } = {
        distancia: etiqueta,
        RUNNING: null,
        WALKING: null,
      };
      for (const cat of CATEGORIAS_CON_MARCA) {
        const valores = deportivas
          .filter((a) => a.tipo === cat && a[clave] !== null)
          .map((a) => a[clave] as number);
        fila[cat] = valores.length ? Math.min(...valores) : null;
      }
      return fila;
    }).filter((f) => f.RUNNING !== null || f.WALKING !== null);
  }, [deportivas]);

  const zonasFcAgregadas = useMemo(() => {
    const total = { z1: 0, z2: 0, z3: 0, z4: 0, z5: 0 };
    for (const a of deportivas) {
      if (!a.zonasFc) continue;
      total.z1 += a.zonasFc.z1;
      total.z2 += a.zonasFc.z2;
      total.z3 += a.zonasFc.z3;
      total.z4 += a.zonasFc.z4;
      total.z5 += a.zonasFc.z5;
    }
    return [
      { clave: "z1", etiqueta: "Muy suave", segundos: total.z1, color: paleta.series[0] },
      { clave: "z2", etiqueta: "Suave", segundos: total.z2, color: paleta.estado.bueno },
      { clave: "z3", etiqueta: "Moderado", segundos: total.z3, color: paleta.estado.aviso },
      { clave: "z4", etiqueta: "Intenso", segundos: total.z4, color: paleta.estado.serio },
      { clave: "z5", etiqueta: "Máximo", segundos: total.z5, color: paleta.estado.critico },
    ];
  }, [deportivas, paleta]);

  const zonasRitmoAgregadas = useMemo(() => {
    const total = { rapido: 0, medio: 0, trote: 0, caminando: 0, parado: 0 };
    for (const a of deportivas) {
      if (!a.zonasRitmo) continue;
      total.rapido += a.zonasRitmo.rapido;
      total.medio += a.zonasRitmo.medio;
      total.trote += a.zonasRitmo.trote;
      total.caminando += a.zonasRitmo.caminando;
      total.parado += a.zonasRitmo.parado;
    }
    return [
      { clave: "rapido", etiqueta: "Rápido", segundos: total.rapido, color: paleta.secuencial(0.95) },
      { clave: "medio", etiqueta: "Medio", segundos: total.medio, color: paleta.secuencial(0.7) },
      { clave: "trote", etiqueta: "Trote", segundos: total.trote, color: paleta.secuencial(0.5) },
      { clave: "caminando", etiqueta: "Caminando", segundos: total.caminando, color: paleta.secuencial(0.3) },
      { clave: "parado", etiqueta: "Parado", segundos: total.parado, color: paleta.secuencial(0.1) },
    ];
  }, [deportivas, paleta]);

  const porActividad = useMemo(
    () =>
      deportivas.map((a) => ({
        fecha: a.fecha,
        etiqueta: formatoCorto(claveDia(new Date(a.fecha))),
        distancia: a.distancia,
        tipo: a.tipo,
        ritmo: a.velMedia > 0 ? ritmoDesdeVelocidad(a.velMedia) : null,
      })),
    [deportivas],
  );

  const rutasGenerales = useMemo<RutaMapa[]>(
    () =>
      deportivas
        .filter((a) => a.traza && a.traza.length > 1)
        .map((a) => ({ puntos: a.traza as [number, number][], color: colorTipo(a.tipo) })),
    [deportivas, paleta],
  );

  const ultimasRutas = useMemo(
    () =>
      [...deportivas]
        .filter((a) => a.traza && a.traza.length > 1)
        .reverse()
        .slice(0, 6),
    [deportivas],
  );

  const ultimasActividades = useMemo(() => [...filtradas].reverse().slice(0, 60), [filtradas]);

  if (cargando) return <Cargando mensaje="Cargando actividades desde MongoDB..." />;
  if (error) return <ErrorCarga mensaje={error} onReintentar={recargar} />;
  if (!todas.length) return <Vacio mensaje="No hay actividades guardadas." />;

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
      <Segmentado
        etiqueta="Tipo"
        valor={tipo}
        onChange={setTipo}
        opciones={[
          { valor: "todas", texto: "Todas" },
          { valor: "RUNNING", texto: "Running" },
          { valor: "WALKING", texto: "Caminata" },
          { valor: "SWIMMING", texto: "Natación" },
          { valor: "TRAINING", texto: "Entreno" },
        ]}
      />
    </>
  );

  const paneles: DefinicionPanel[] = [
    {
      id: "resumen",
      titulo: "Resumen",
      ayuda: `${filtradas.length} actividades con los filtros actuales`,
      base: { x: 0, y: 0, w: 12, h: 3, minH: 3 },
      contenido: (
        <RejillaKpis
          items={[
            { etiqueta: "Actividades", valor: miles(resumen.total) },
            { etiqueta: "Distancia (deportivas)", valor: `${dec1(resumen.distancia)} km` },
            { etiqueta: "Ritmo medio", valor: formatoRitmo(resumen.ritmoMedio), color: paleta.series[0] },
            { etiqueta: "Calorías", valor: compacto(resumen.calorias) },
            { etiqueta: "Tiempo activo", valor: formatoDuracion(resumen.tiempoActivo) },
          ]}
        />
      ),
    },
    {
      id: "records",
      titulo: "Récords personales",
      ayuda: "por categoría, Hevy queda fuera",
      base: { x: 0, y: 3, w: 12, h: 7, minH: 4 },
      contenido: (
        <Tabla
          filas={registrosPersonales}
          claveFila={(fila) => fila.tipo}
          columnas={[
            { clave: "tipo", titulo: "Categoría", render: (f) => TIPOS_ES[f.tipo] },
            { clave: "actividades", titulo: "Actividades", alineacion: "derecha" },
            {
              clave: "ritmoMedio",
              titulo: "Ritmo medio",
              alineacion: "derecha",
              render: (f) => <span style={{ color: paleta.series[0] }}>{formatoRitmo(f.ritmoMedio)}</span>,
            },
            {
              clave: "mayorDistancia",
              titulo: "Mayor distancia",
              alineacion: "derecha",
              render: (f) => `${dec1(f.mayorDistancia)} km`,
            },
            {
              clave: "mayorDuracion",
              titulo: "Mayor duración",
              alineacion: "derecha",
              render: (f) => formatoDuracion(f.mayorDuracion),
            },
            {
              clave: "masCalorias",
              titulo: "Más calorías",
              alineacion: "derecha",
              render: (f) => compacto(f.masCalorias),
            },
            { clave: "fcMaxima", titulo: "FC máxima", alineacion: "derecha", render: (f) => `${f.fcMaxima} ppm` },
          ]}
        />
      ),
    },
    {
      id: "mejores-marcas",
      titulo: "Mejores marcas",
      ayuda: "tiempo más rápido continuo a cada distancia, según GPS",
      base: { x: 0, y: 10, w: 6, h: 7, minH: 4 },
      contenido: (
        <Tabla
          filas={mejoresMarcas}
          claveFila={(fila) => fila.distancia}
          columnas={[
            { clave: "distancia", titulo: "Distancia" },
            {
              clave: "RUNNING",
              titulo: "Running",
              alineacion: "derecha",
              render: (f) => <span style={{ color: paleta.estado.bueno }}>{formatoTiempo(f.RUNNING)}</span>,
            },
            {
              clave: "WALKING",
              titulo: "Caminata",
              alineacion: "derecha",
              render: (f) => formatoTiempo(f.WALKING),
            },
          ]}
        />
      ),
    },
    {
      id: "zonas-fc",
      titulo: "Zonas de frecuencia cardíaca",
      ayuda: "% de tiempo activo en cada zona, según GPS con FC",
      base: { x: 6, y: 10, w: 6, h: 7, minH: 4 },
      contenido: <BarraZonas zonas={zonasFcAgregadas} />,
    },
    {
      id: "zonas-ritmo",
      titulo: "Zonas de ritmo",
      ayuda: "rápido <5:00, medio 5-6:30, trote 6:30-8:00, caminando 8-15, parado >15 min/km",
      base: { x: 0, y: 17, w: 6, h: 7, minH: 4 },
      contenido: <BarraZonas zonas={zonasRitmoAgregadas} />,
    },
    {
      id: "distancia-actividad",
      titulo: "Distancia por actividad",
      base: { x: 6, y: 17, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porActividad}
          x="etiqueta"
          series={[{ clave: "distancia", nombre: "Distancia" }]}
          formatoValor={(v) => `${dec1(v)} km`}
          coloresPorPunto={(punto) => colorTipo(punto.tipo)}
        />
      ),
    },
    {
      id: "ritmo-tiempo",
      titulo: "Ritmo por actividad",
      ayuda: "min/km, running y caminata",
      base: { x: 0, y: 24, w: 12, h: 7, minH: 4 },
      contenido: (
        <GraficaLineas
          datos={porActividad.filter((p) => p.ritmo !== null)}
          x="etiqueta"
          series={[{ clave: "ritmo", nombre: "Ritmo", color: paleta.series[0] }]}
          formatoValor={(v) => formatoRitmo(v)}
          puntos
        />
      ),
    },
    {
      id: "mapa-general",
      titulo: "Mapa de rutas",
      ayuda: `${rutasGenerales.length} rutas con GPS`,
      base: { x: 0, y: 31, w: 12, h: 10, minH: 6 },
      contenido: <MapaRuta rutas={rutasGenerales} interactivo />,
    },
    {
      id: "ultimas-rutas",
      titulo: "Últimas rutas",
      base: { x: 0, y: 41, w: 12, h: 9, minH: 6 },
      contenido: (
        <div className="grid h-full grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {ultimasRutas.length === 0 && <Vacio mensaje="Sin rutas con GPS" />}
          {ultimasRutas.map((a) => (
            <div key={a.id} className="flex flex-col gap-1">
              <div className="min-h-0 flex-1 overflow-hidden rounded-lg" style={{ height: 110 }}>
                <MapaRuta
                  rutas={[{ puntos: a.traza as [number, number][], color: colorTipo(a.tipo) }]}
                  interactivo={false}
                />
              </div>
              <span className="truncate text-[11px] font-medium" style={{ color: "var(--tinta)" }}>
                {TIPOS_ES[a.tipo]} · {dec1(a.distancia)} km
              </span>
              <span className="truncate text-[10px]" style={{ color: "var(--tinta-3)" }}>
                {formatoCorto(claveDia(new Date(a.fecha)))}
              </span>
            </div>
          ))}
        </div>
      ),
    },
    {
      id: "entrenamientos",
      titulo: "Entrenamientos (Hevy)",
      ayuda: "sin GPS, informativo",
      base: { x: 0, y: 50, w: 4, h: 8, minH: 4 },
      contenido: (
        <Tabla
          filas={entrenamientos.slice().reverse().slice(0, 30)}
          claveFila={(fila) => fila.id}
          columnas={[
            {
              clave: "fecha",
              titulo: "Fecha",
              render: (f) => formatoCorto(claveDia(new Date(f.fecha))),
            },
            {
              clave: "duracionActiva",
              titulo: "Duración",
              alineacion: "derecha",
              render: (f) => formatoDuracion(f.duracionActiva),
            },
            { clave: "calorias", titulo: "Kcal", alineacion: "derecha", render: (f) => compacto(f.calorias) },
            { clave: "fcMedia", titulo: "FC media", alineacion: "derecha", render: (f) => `${f.fcMedia}` },
          ]}
        />
      ),
    },
    {
      id: "ultimas-actividades",
      titulo: "Últimas actividades",
      base: { x: 4, y: 50, w: 8, h: 10, minH: 5 },
      contenido: (
        <Tabla
          filas={ultimasActividades}
          claveFila={(fila) => fila.id}
          columnas={[
            {
              clave: "fecha",
              titulo: "Fecha",
              render: (f) => new Date(f.fecha).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" }),
            },
            { clave: "tipo", titulo: "Tipo", render: (f) => TIPOS_ES[f.tipo] },
            {
              clave: "distancia",
              titulo: "Distancia",
              alineacion: "derecha",
              render: (f) => (f.distancia ? `${dec1(f.distancia)} km` : "—"),
            },
            {
              clave: "duracionActiva",
              titulo: "Duración",
              alineacion: "derecha",
              render: (f) => formatoDuracion(f.duracionActiva),
            },
            { clave: "calorias", titulo: "Kcal", alineacion: "derecha", render: (f) => compacto(f.calorias) },
            {
              clave: "velMedia",
              titulo: "Ritmo",
              alineacion: "derecha",
              render: (f) => formatoRitmo(ritmoDesdeVelocidad(f.velMedia)),
            },
          ]}
        />
      ),
    },
  ];

  return <Tablero claveAlmacen="actividades" version={2} paneles={paneles} filtros={filtros} />;
}
