"use client";

import { useMemo, useState } from "react";
import { Tablero, type DefinicionPanel } from "@/components/tablero";
import { Cargando, ErrorCarga, Vacio } from "@/components/estados";
import { Deslizador, MultiSelector, RangoFechas, Segmentado } from "@/components/controles";
import { GraficaBarras, GraficaLineas } from "@/components/charts/graficas";
import { CalendarioAnual, MapaCalor, RejillaKpis, Tabla } from "@/components/charts/visuales";
import { usePaleta } from "@/components/tema";
import { useDatos } from "@/lib/datos";
import { dec1, miles } from "@/lib/formato";
import {
  DIAS_CORTOS,
  DIAS_ES,
  MESES_ES,
  claveDia,
  desdeClaveDia,
  formatoCorto,
  formatoMes,
  indiceDiaSemana,
  sumarDias,
} from "@/lib/fechas";
import type { Registro, RespuestaRegistro } from "@/lib/tipos";

type Racha = { tipo: "Con registro" | "Sin registro"; inicio: string; fin: string; dias: number };

function calcularRachas(dias: Set<string>, desde: string, hasta: string): Racha[] {
  if (!desde || !hasta) return [];
  const rachas: Racha[] = [];
  let actual: Racha | null = null;
  for (let d = desdeClaveDia(desde); claveDia(d) <= hasta; d = sumarDias(d, 1)) {
    const clave = claveDia(d);
    const tipo: Racha["tipo"] = dias.has(clave) ? "Con registro" : "Sin registro";
    if (actual && actual.tipo === tipo) {
      actual.fin = clave;
      actual.dias += 1;
    } else {
      if (actual) rachas.push(actual);
      actual = { tipo, inicio: clave, fin: clave, dias: 1 };
    }
  }
  if (actual) rachas.push(actual);
  return rachas;
}

export function PestanaRegistro() {
  const { datos, cargando, error, recargar } = useDatos<RespuestaRegistro>("/api/registro");
  const paleta = usePaleta();

  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [preset, setPreset] = useState("todo");
  const [meses, setMeses] = useState<string[]>([]);
  const [diasSemana, setDiasSemana] = useState<string[]>([]);
  const [duracionMin, setDuracionMin] = useState(0);
  const [horaDesde, setHoraDesde] = useState(0);
  const [horaHasta, setHoraHasta] = useState(23);

  const todos = useMemo(() => datos?.registros ?? [], [datos]);

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

  const registros = useMemo(() => {
    return todos.filter((r) => {
      if (desde && r.dia < desde) return false;
      if (hasta && r.dia > hasta) return false;
      if (r.minutos < duracionMin) return false;
      const fecha = new Date(r.t);
      if (meses.length && !meses.includes(String(fecha.getMonth()))) return false;
      if (diasSemana.length && !diasSemana.includes(String(indiceDiaSemana(fecha)))) return false;
      const hora = fecha.getHours();
      if (hora < horaDesde || hora > horaHasta) return false;
      return true;
    });
  }, [todos, desde, hasta, duracionMin, meses, diasSemana, horaDesde, horaHasta]);

  const diasConRegistro = useMemo(() => new Set(registros.map((r) => r.dia)), [registros]);

  const limites = useMemo(() => {
    if (!registros.length) return { desde: "", hasta: "" };
    return { desde: registros[0].dia, hasta: registros[registros.length - 1].dia };
  }, [registros]);

  const rachas = useMemo(
    () => calcularRachas(diasConRegistro, limites.desde, limites.hasta),
    [diasConRegistro, limites],
  );

  const rachasCon = useMemo(
    () => rachas.filter((r) => r.tipo === "Con registro").sort((a, b) => b.dias - a.dias),
    [rachas],
  );
  const rachasSin = useMemo(
    () => rachas.filter((r) => r.tipo === "Sin registro").sort((a, b) => b.dias - a.dias),
    [rachas],
  );

  const resumen = useMemo(() => {
    const minutos = registros.reduce((acc, r) => acc + r.minutos, 0);
    const ultimaRacha = rachas.length ? rachas[rachas.length - 1] : null;
    return {
      total: registros.length,
      dias: diasConRegistro.size,
      minutos,
      media: registros.length ? minutos / registros.length : 0,
      porDia: diasConRegistro.size ? registros.length / diasConRegistro.size : 0,
      rachaActual: ultimaRacha ? ultimaRacha.dias : 0,
      tipoRachaActual: ultimaRacha?.tipo ?? "Sin registro",
      mejorRacha: rachasCon.length ? rachasCon[0].dias : 0,
    };
  }, [registros, diasConRegistro, rachas, rachasCon]);

  const porDia = useMemo(() => {
    const mapa = new Map<string, { registros: number; minutos: number }>();
    for (const r of registros) {
      const previo = mapa.get(r.dia) ?? { registros: 0, minutos: 0 };
      previo.registros += 1;
      previo.minutos += r.minutos;
      mapa.set(r.dia, previo);
    }
    return [...mapa.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([dia, v]) => ({ dia, ...v }));
  }, [registros]);

  const porMes = useMemo(() => {
    const mapa = new Map<string, { registros: number; minutos: number; dias: Set<string> }>();
    for (const r of registros) {
      const clave = r.dia.slice(0, 7);
      const previo = mapa.get(clave) ?? { registros: 0, minutos: 0, dias: new Set<string>() };
      previo.registros += 1;
      previo.minutos += r.minutos;
      previo.dias.add(r.dia);
      mapa.set(clave, previo);
    }
    return [...mapa.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([mes, v]) => ({
        mes,
        registros: v.registros,
        minutos: v.minutos,
        media: v.registros ? v.minutos / v.registros : 0,
        dias: v.dias.size,
      }));
  }, [registros]);

  const histograma = useMemo(() => {
    if (!registros.length) return [];
    const ancho = 15;
    const mapa = new Map<number, number>();
    for (const r of registros) {
      const cubo = Math.floor(r.minutos / ancho) * ancho;
      mapa.set(cubo, (mapa.get(cubo) ?? 0) + 1);
    }
    return [...mapa.entries()]
      .sort(([a], [b]) => a - b)
      .map(([cubo, cuenta]) => ({ rango: `${cubo}-${cubo + ancho}`, registros: cuenta }));
  }, [registros]);

  const porDiaSemana = useMemo(() => {
    const cubos = DIAS_ES.map(() => ({ registros: 0, minutos: 0 }));
    for (const r of registros) {
      const idx = indiceDiaSemana(new Date(r.t));
      cubos[idx].registros += 1;
      cubos[idx].minutos += r.minutos;
    }
    return DIAS_CORTOS.map((dia, i) => ({
      dia,
      registros: cubos[i].registros,
      media: cubos[i].registros ? cubos[i].minutos / cubos[i].registros : 0,
    }));
  }, [registros]);

  const porHora = useMemo(() => {
    const cubos = new Map<number, number>();
    for (const r of registros) {
      const hora = new Date(r.t).getHours();
      cubos.set(hora, (cubos.get(hora) ?? 0) + 1);
    }
    return [...cubos.entries()]
      .sort(([a], [b]) => a - b)
      .map(([hora, registros]) => ({ hora: `${String(hora).padStart(2, "0")}h`, registros }));
  }, [registros]);

  const heatmap = useMemo(() => {
    const horas = [...new Set(registros.map((r) => new Date(r.t).getHours()))].sort((a, b) => a - b);
    const acumulado = new Map<string, number>();
    for (const r of registros) {
      const fecha = new Date(r.t);
      const clave = `${fecha.getHours()}-${indiceDiaSemana(fecha)}`;
      acumulado.set(clave, (acumulado.get(clave) ?? 0) + 1);
    }
    const valores = horas.map((h) => DIAS_CORTOS.map((_, d) => acumulado.get(`${h}-${d}`) ?? null));
    return { filas: horas.map((h) => `${String(h).padStart(2, "0")}h`), valores };
  }, [registros]);

  const frecuenciaRachas = useMemo(() => {
    const mapa = new Map<number, { con: number; sin: number }>();
    for (const r of rachas) {
      const previo = mapa.get(r.dias) ?? { con: 0, sin: 0 };
      if (r.tipo === "Con registro") previo.con += 1;
      else previo.sin += 1;
      mapa.set(r.dias, previo);
    }
    return [...mapa.entries()]
      .sort(([a], [b]) => a - b)
      .map(([dias, v]) => ({ dias: `${dias} d`, ...v }));
  }, [rachas]);

  const calendario = useMemo(() => {
    const mapa = new Map<string, number>();
    for (const punto of porDia) mapa.set(punto.dia, punto.minutos);
    const anios = [...new Set(porDia.map((p) => Number(p.dia.slice(0, 4))))];
    return { mapa, anio: anios.length ? Math.max(...anios) : new Date().getFullYear() };
  }, [porDia]);

  if (cargando) return <Cargando mensaje="Leyendo la hoja de cálculo..." />;
  if (error) return <ErrorCarga mensaje={error} onReintentar={recargar} />;
  if (!todos.length) return <Vacio mensaje="La hoja de registro está vacía." />;

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
        etiqueta="Días"
        valores={diasSemana}
        onChange={setDiasSemana}
        opciones={DIAS_ES.map((d, i) => ({ valor: String(i), texto: d }))}
        ancho="w-40"
      />
      <Deslizador
        etiqueta="Duración mínima"
        valor={duracionMin}
        min={0}
        max={120}
        paso={5}
        onChange={setDuracionMin}
        formato={(v) => `${v} min`}
        ancho="w-32"
      />
      <Deslizador
        etiqueta="Hora desde"
        valor={horaDesde}
        min={0}
        max={23}
        onChange={(v) => setHoraDesde(Math.min(v, horaHasta))}
        formato={(v) => `${String(v).padStart(2, "0")}:00`}
        ancho="w-24"
      />
      <Deslizador
        etiqueta="Hora hasta"
        valor={horaHasta}
        min={0}
        max={23}
        onChange={(v) => setHoraHasta(Math.max(v, horaDesde))}
        formato={(v) => `${String(v).padStart(2, "0")}:59`}
        ancho="w-24"
      />
    </>
  );

  const paneles: DefinicionPanel[] = [
    {
      id: "resumen",
      titulo: "Resumen",
      ayuda: limites.desde ? `${formatoCorto(limites.desde)} → ${formatoCorto(limites.hasta)}` : undefined,
      base: { x: 0, y: 0, w: 12, h: 3, minH: 3 },
      contenido: (
        <RejillaKpis
          items={[
            { etiqueta: "Registros", valor: miles(resumen.total) },
            { etiqueta: "Días con registro", valor: miles(resumen.dias) },
            { etiqueta: "Registros por día", valor: dec1(resumen.porDia) },
            { etiqueta: "Duración media", valor: `${dec1(resumen.media)} min` },
            {
              etiqueta: "Racha actual",
              valor: `${resumen.rachaActual} d`,
              ayuda: resumen.tipoRachaActual.toLowerCase(),
              color: resumen.tipoRachaActual === "Con registro" ? paleta.estado.bueno : paleta.estado.critico,
            },
            { etiqueta: "Mejor racha", valor: `${resumen.mejorRacha} d`, color: paleta.estado.bueno },
          ]}
        />
      ),
    },
    {
      id: "linea-tiempo",
      titulo: "Registros por día",
      base: { x: 0, y: 3, w: 8, h: 8, minH: 5 },
      contenido: (
        <GraficaBarras
          datos={porDia}
          x="dia"
          series={[{ clave: "registros", nombre: "Registros" }]}
          formatoValor={(v) => `${miles(v)} registros`}
          formatoX={(v) => formatoCorto(String(v))}
          extraTooltip={(punto) => `${dec1(punto.minutos)} min en total`}
        />
      ),
    },
    {
      id: "duracion-dia",
      titulo: "Minutos por día",
      base: { x: 8, y: 3, w: 4, h: 8, minH: 5 },
      contenido: (
        <GraficaLineas
          datos={porDia}
          x="dia"
          series={[{ clave: "minutos", nombre: "Minutos", tipo: "area", color: paleta.series[2] }]}
          formatoValor={(v) => `${dec1(v)} min`}
          formatoX={(v) => formatoCorto(String(v))}
        />
      ),
    },
    {
      id: "por-mes",
      titulo: "Registros por mes",
      base: { x: 0, y: 11, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porMes}
          x="mes"
          series={[{ clave: "registros", nombre: "Registros" }]}
          formatoValor={(v) => `${miles(v)} registros`}
          formatoX={(v) => formatoMes(String(v))}
          anguloX={-45}
          extraTooltip={(punto) => `${punto.dias} días distintos`}
        />
      ),
    },
    {
      id: "duracion-mes",
      titulo: "Duración media por mes",
      base: { x: 6, y: 11, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaLineas
          datos={porMes}
          x="mes"
          series={[{ clave: "media", nombre: "Minutos de media", color: paleta.series[1] }]}
          formatoValor={(v) => `${dec1(v)} min`}
          formatoX={(v) => formatoMes(String(v))}
          puntos
        />
      ),
    },
    {
      id: "histograma",
      titulo: "Distribución de la duración",
      base: { x: 0, y: 18, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={histograma}
          x="rango"
          series={[{ clave: "registros", nombre: "Registros", color: paleta.series[2] }]}
          formatoValor={(v) => `${miles(v)} registros`}
          etiquetasDirectas
        />
      ),
    },
    {
      id: "frecuencia-rachas",
      titulo: "Rachas por duración",
      ayuda: "con y sin registro",
      base: { x: 6, y: 18, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={frecuenciaRachas}
          x="dias"
          series={[
            { clave: "con", nombre: "Con registro", color: paleta.estado.bueno },
            { clave: "sin", nombre: "Sin registro", color: paleta.estado.critico },
          ]}
          formatoValor={(v) => `${v} veces`}
        />
      ),
    },
    {
      id: "rachas-con",
      titulo: "Mejores rachas con registro",
      base: { x: 0, y: 25, w: 4, h: 7, minH: 4 },
      contenido: (
        <Tabla
          filas={rachasCon.slice(0, 25)}
          claveFila={(fila) => fila.inicio}
          columnas={[
            { clave: "inicio", titulo: "Desde", render: (f) => formatoCorto(f.inicio) },
            { clave: "fin", titulo: "Hasta", render: (f) => formatoCorto(f.fin) },
            { clave: "dias", titulo: "Días", alineacion: "derecha" },
          ]}
        />
      ),
    },
    {
      id: "rachas-sin",
      titulo: "Mayores huecos sin registro",
      base: { x: 4, y: 25, w: 4, h: 7, minH: 4 },
      contenido: (
        <Tabla
          filas={rachasSin.slice(0, 25)}
          claveFila={(fila) => fila.inicio}
          columnas={[
            { clave: "inicio", titulo: "Desde", render: (f) => formatoCorto(f.inicio) },
            { clave: "fin", titulo: "Hasta", render: (f) => formatoCorto(f.fin) },
            { clave: "dias", titulo: "Días", alineacion: "derecha" },
          ]}
        />
      ),
    },
    {
      id: "dia-semana",
      titulo: "Registros por día de la semana",
      base: { x: 8, y: 25, w: 4, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porDiaSemana}
          x="dia"
          series={[{ clave: "registros", nombre: "Registros" }]}
          formatoValor={(v) => `${miles(v)} registros`}
          extraTooltip={(punto) => `${dec1(punto.media)} min de media`}
        />
      ),
    },
    {
      id: "por-hora",
      titulo: "Registros por hora del día",
      base: { x: 0, y: 32, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porHora}
          x="hora"
          series={[{ clave: "registros", nombre: "Registros", color: paleta.series[4] }]}
          formatoValor={(v) => `${miles(v)} registros`}
        />
      ),
    },
    {
      id: "heatmap",
      titulo: "Hora contra día de la semana",
      base: { x: 6, y: 32, w: 6, h: 8, minH: 5 },
      contenido: (
        <MapaCalor
          filas={heatmap.filas}
          columnas={DIAS_CORTOS}
          valores={heatmap.valores}
          formatoValor={(v) => `${miles(v)}`}
          etiquetaValor="Número de registros por hora y día"
        />
      ),
    },
    {
      id: "calendario",
      titulo: `Calendario ${calendario.anio}`,
      ayuda: "minutos registrados",
      base: { x: 0, y: 40, w: 12, h: 5, minH: 4 },
      contenido: (
        <CalendarioAnual
          anio={calendario.anio}
          valoresPorDia={calendario.mapa}
          formatoValor={(v) => `${dec1(v)} min`}
          etiqueta="Minutos por día"
        />
      ),
    },
    {
      id: "ultimos",
      titulo: "Últimos registros",
      base: { x: 0, y: 46, w: 12, h: 8, minH: 5 },
      contenido: (
        <Tabla
          filas={[...registros].reverse().slice(0, 80)}
          claveFila={(fila, i) => `${fila.t}-${i}`}
          columnas={[
            {
              clave: "t",
              titulo: "Fecha",
              render: (f: Registro) =>
                new Date(f.t).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" }),
            },
            {
              clave: "dia",
              titulo: "Día",
              render: (f: Registro) => DIAS_ES[indiceDiaSemana(new Date(f.t))],
            },
            {
              clave: "minutos",
              titulo: "Duración",
              alineacion: "derecha",
              render: (f: Registro) => `${dec1(f.minutos)} min`,
            },
          ]}
        />
      ),
    },
  ];

  return <Tablero claveAlmacen="registro" version={2} paneles={paneles} filtros={filtros} />;
}
