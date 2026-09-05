"use client";

import { useMemo, useState } from "react";
import { Tablero, type DefinicionPanel } from "@/components/tablero";
import { Cargando, ErrorCarga, Vacio } from "@/components/estados";
import { Deslizador, MultiSelector, NavegadorMes, Segmentado, RangoFechas } from "@/components/controles";
import { GraficaBarras, GraficaDonut, GraficaLineas } from "@/components/charts/graficas";
import { CalendarioAnual, MapaCalor, RejillaKpis, Tabla } from "@/components/charts/visuales";
import { usePaleta } from "@/components/tema";
import { useDatos } from "@/lib/datos";
import { miles, pct } from "@/lib/formato";
import {
  DIAS_CORTOS,
  DIAS_ES,
  MESES_CORTOS,
  MESES_ES,
  claveDia,
  claveMesActual,
  desdeClaveDia,
  diasEnMes,
  formatoCorto,
  formatoMesLargo,
  indiceDiaSemana,
  sumarMeses,
} from "@/lib/fechas";
import type { DiaPasos, RespuestaPasos } from "@/lib/tipos";

type Racha = { inicio: string; fin: string; dias: number; cumple: boolean };

function mediaMovil(valores: number[], ventana: number): number[] {
  if (ventana <= 1) return valores.slice();
  const salida: number[] = [];
  let suma = 0;
  for (let i = 0; i < valores.length; i++) {
    suma += valores[i];
    if (i >= ventana) suma -= valores[i - ventana];
    salida.push(suma / Math.min(i + 1, ventana));
  }
  return salida;
}

function calcularRachas(dias: DiaPasos[], meta: number): Racha[] {
  if (!dias.length) return [];
  const rachas: Racha[] = [];
  let actual: Racha | null = null;
  for (const dia of dias) {
    const cumple = dia.v >= meta;
    if (actual && actual.cumple === cumple) {
      actual.fin = dia.f;
      actual.dias += 1;
    } else {
      if (actual) rachas.push(actual);
      actual = { inicio: dia.f, fin: dia.f, dias: 1, cumple };
    }
  }
  if (actual) rachas.push(actual);
  return rachas;
}

export function PestanaPasos() {
  const { datos, cargando, error, recargar } = useDatos<RespuestaPasos>("/api/pasos");
  const paleta = usePaleta();

  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [meses, setMeses] = useState<string[]>([]);
  const [diasSemana, setDiasSemana] = useState<string[]>([]);
  const [meta, setMeta] = useState(10000);
  const [ventana, setVentana] = useState("7");
  const [imputados, setImputados] = useState("si");
  const [preset, setPreset] = useState("todo");
  const [mesFoco, setMesFoco] = useState(claveMesActual);

  const todos = useMemo(() => datos?.dias ?? [], [datos]);

  const aplicarPreset = (valor: string) => {
    setPreset(valor);
    if (!todos.length) return;
    const ultimo = desdeClaveDia(todos[todos.length - 1].f);
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
    const dias = valor === "30" ? 30 : valor === "90" ? 90 : 365;
    const inicio = new Date(ultimo);
    inicio.setDate(inicio.getDate() - dias + 1);
    setDesde(claveDia(inicio));
    setHasta(claveDia(ultimo));
  };

  const filtrados = useMemo(() => {
    return todos.filter((dia) => {
      if (desde && dia.f < desde) return false;
      if (hasta && dia.f > hasta) return false;
      if (imputados === "no" && dia.imp) return false;
      const fecha = desdeClaveDia(dia.f);
      if (meses.length && !meses.includes(String(fecha.getMonth()))) return false;
      if (diasSemana.length && !diasSemana.includes(String(indiceDiaSemana(fecha)))) return false;
      return true;
    });
  }, [todos, desde, hasta, meses, diasSemana, imputados]);

  const serie = useMemo(() => {
    const valores = filtrados.map((d) => d.v);
    const mm = mediaMovil(valores, Number(ventana));
    return filtrados.map((d, i) => ({
      f: d.f,
      v: d.v,
      mm: ventana === "0" ? null : Math.round(mm[i]),
      imp: d.imp,
    }));
  }, [filtrados, ventana]);

  const resumen = useMemo(() => {
    if (!filtrados.length) {
      return { total: 0, media: 0, maximo: 0, diaMaximo: "", cumplidos: 0, porcentaje: 0, rachaActual: 0 };
    }
    const total = filtrados.reduce((acc, d) => acc + d.v, 0);
    const maximoDia = filtrados.reduce((mejor, d) => (d.v > mejor.v ? d : mejor), filtrados[0]);
    const cumplidos = filtrados.filter((d) => d.v >= meta).length;
    let rachaActual = 0;
    for (let i = filtrados.length - 1; i >= 0; i--) {
      if (filtrados[i].v >= meta) rachaActual++;
      else break;
    }
    return {
      total,
      media: total / filtrados.length,
      maximo: maximoDia.v,
      diaMaximo: maximoDia.f,
      cumplidos,
      porcentaje: (cumplidos / filtrados.length) * 100,
      rachaActual,
    };
  }, [filtrados, meta]);

  // Datos por dia del mes que se esta paseando, al margen de los filtros globales de fecha.
  const diasMesFoco = useMemo(() => {
    const base = imputados === "no" ? todos.filter((d) => !d.imp) : todos;
    const mapa = new Map(base.map((d) => [d.f, d]));
    const total = diasEnMes(mesFoco);
    return Array.from({ length: total }, (_, i) => {
      const f = `${mesFoco}-${String(i + 1).padStart(2, "0")}`;
      const dia = mapa.get(f);
      return { dia: i + 1, f, v: dia ? dia.v : null, imp: dia?.imp ?? false };
    });
  }, [todos, mesFoco, imputados]);

  const resumenMesFoco = useMemo(() => {
    const conDatos = diasMesFoco.filter((d): d is typeof d & { v: number } => d.v !== null);
    if (!conDatos.length) {
      return { conDatos: 0, media: 0, total: 0, maximo: 0, diaMaximo: "", cumplidos: 0, porcentaje: 0 };
    }
    const total = conDatos.reduce((acc, d) => acc + d.v, 0);
    const maximoDia = conDatos.reduce((mejor, d) => (d.v > mejor.v ? d : mejor), conDatos[0]);
    const cumplidos = conDatos.filter((d) => d.v >= meta).length;
    return {
      conDatos: conDatos.length,
      media: total / conDatos.length,
      total,
      maximo: maximoDia.v,
      diaMaximo: maximoDia.f,
      cumplidos,
      porcentaje: (cumplidos / conDatos.length) * 100,
    };
  }, [diasMesFoco, meta]);

  const primerMesDatos = useMemo(() => (todos.length ? todos[0].f.slice(0, 7) : mesFoco), [todos, mesFoco]);
  const ultimoMesNavegable = useMemo(() => {
    const ultimoConDatos = todos.length ? todos[todos.length - 1].f.slice(0, 7) : mesFoco;
    return ultimoConDatos > claveMesActual() ? ultimoConDatos : claveMesActual();
  }, [todos, mesFoco]);

  const rachas = useMemo(() => calcularRachas(filtrados, meta), [filtrados, meta]);
  const rachasCumplidas = useMemo(
    () => rachas.filter((r) => r.cumple).sort((a, b) => b.dias - a.dias),
    [rachas],
  );

  const porDiaSemana = useMemo(() => {
    const acumulado = DIAS_ES.map(() => ({ suma: 0, cuenta: 0 }));
    for (const dia of filtrados) {
      const idx = indiceDiaSemana(desdeClaveDia(dia.f));
      acumulado[idx].suma += dia.v;
      acumulado[idx].cuenta += 1;
    }
    return DIAS_CORTOS.map((nombre, i) => ({
      dia: nombre,
      media: acumulado[i].cuenta ? Math.round(acumulado[i].suma / acumulado[i].cuenta) : 0,
    }));
  }, [filtrados]);

  const porMes = useMemo(() => {
    const mapa = new Map<string, { suma: number; cuenta: number }>();
    for (const dia of filtrados) {
      const clave = dia.f.slice(0, 7);
      const previo = mapa.get(clave) ?? { suma: 0, cuenta: 0 };
      previo.suma += dia.v;
      previo.cuenta += 1;
      mapa.set(clave, previo);
    }
    return [...mapa.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([clave, v]) => ({
        mes: clave,
        media: Math.round(v.suma / v.cuenta),
        total: v.suma,
      }));
  }, [filtrados]);

  const histograma = useMemo(() => {
    if (!filtrados.length) return [];
    const ancho = 2000;
    const mapa = new Map<number, number>();
    for (const dia of filtrados) {
      const cubo = Math.floor(dia.v / ancho) * ancho;
      mapa.set(cubo, (mapa.get(cubo) ?? 0) + 1);
    }
    return [...mapa.entries()]
      .sort(([a], [b]) => a - b)
      .map(([cubo, cuenta]) => ({
        rango: `${cubo / 1000}-${(cubo + ancho) / 1000}k`,
        inicio: cubo,
        dias: cuenta,
      }));
  }, [filtrados]);

  const frecuenciaRachas = useMemo(() => {
    const mapa = new Map<number, number>();
    for (const r of rachasCumplidas) mapa.set(r.dias, (mapa.get(r.dias) ?? 0) + 1);
    return [...mapa.entries()].sort(([a], [b]) => a - b).map(([dias, veces]) => ({ dias: `${dias}`, veces }));
  }, [rachasCumplidas]);

  const heatmap = useMemo(() => {
    const mesesPresentes = [...new Set(filtrados.map((d) => desdeClaveDia(d.f).getMonth()))].sort(
      (a, b) => a - b,
    );
    const acumulado = new Map<string, { suma: number; cuenta: number }>();
    for (const dia of filtrados) {
      const fecha = desdeClaveDia(dia.f);
      const clave = `${fecha.getMonth()}-${indiceDiaSemana(fecha)}`;
      const previo = acumulado.get(clave) ?? { suma: 0, cuenta: 0 };
      previo.suma += dia.v;
      previo.cuenta += 1;
      acumulado.set(clave, previo);
    }
    const valores = mesesPresentes.map((mes) =>
      DIAS_CORTOS.map((_, d) => {
        const celda = acumulado.get(`${mes}-${d}`);
        return celda ? Math.round(celda.suma / celda.cuenta) : null;
      }),
    );
    return { filas: mesesPresentes.map((m) => MESES_CORTOS[m]), valores };
  }, [filtrados]);

  const calendario = useMemo(() => {
    const mapa = new Map<string, number>();
    for (const dia of filtrados) mapa.set(dia.f, dia.v);
    const anios = [...new Set(filtrados.map((d) => Number(d.f.slice(0, 4))))];
    return { mapa, anio: anios.length ? Math.max(...anios) : new Date().getFullYear() };
  }, [filtrados]);

  const comparativaAnios = useMemo(() => {
    const anios = [...new Set(filtrados.map((d) => d.f.slice(0, 4)))].sort();
    if (anios.length < 2) return { anios: [], datos: [] as Record<string, number>[] };
    const acumulados = new Map<string, number>();
    const porDia = new Map<number, Record<string, number>>();
    for (const dia of filtrados) {
      const fecha = desdeClaveDia(dia.f);
      const anio = dia.f.slice(0, 4);
      const inicioAnio = new Date(fecha.getFullYear(), 0, 1);
      const diaDelAnio = Math.floor((fecha.getTime() - inicioAnio.getTime()) / 86400000) + 1;
      const previo = acumulados.get(anio) ?? 0;
      const nuevo = previo + dia.v;
      acumulados.set(anio, nuevo);
      const fila = porDia.get(diaDelAnio) ?? { dia: diaDelAnio };
      fila[anio] = nuevo;
      porDia.set(diaDelAnio, fila);
    }
    return {
      anios,
      datos: [...porDia.values()].sort((a, b) => a.dia - b.dia),
    };
  }, [filtrados]);

  const topDias = useMemo(() => [...filtrados].sort((a, b) => b.v - a.v).slice(0, 12), [filtrados]);
  const peoresDias = useMemo(() => [...filtrados].sort((a, b) => a.v - b.v).slice(0, 12), [filtrados]);

  if (cargando) return <Cargando mensaje="Cargando pasos desde MongoDB..." />;
  if (error) return <ErrorCarga mensaje={error} onReintentar={recargar} />;
  if (!todos.length) return <Vacio mensaje="No hay registros de pasos a partir del 1 de enero de 2025." />;

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
        etiqueta="Meta diaria"
        valor={meta}
        min={2000}
        max={25000}
        paso={500}
        onChange={setMeta}
        formato={(v) => miles(v)}
      />
      <Segmentado
        etiqueta="Media móvil"
        valor={ventana}
        onChange={setVentana}
        opciones={[
          { valor: "0", texto: "No" },
          { valor: "7", texto: "7 d" },
          { valor: "30", texto: "30 d" },
        ]}
      />
      <Segmentado
        etiqueta="Días imputados"
        valor={imputados}
        onChange={setImputados}
        opciones={[
          { valor: "si", texto: "Incluir" },
          { valor: "no", texto: "Excluir" },
        ]}
      />
    </>
  );

  const paneles: DefinicionPanel[] = [
    {
      id: "resumen",
      titulo: "Resumen del periodo",
      ayuda: `${filtrados.length} días · ${datos?.meta.rellenados ?? 0} imputados en total`,
      base: { x: 0, y: 0, w: 12, h: 3, minH: 3 },
      contenido: (
        <RejillaKpis
          items={[
            { etiqueta: "Días", valor: miles(filtrados.length) },
            { etiqueta: "Media diaria", valor: miles(resumen.media) },
            { etiqueta: "Acumulado", valor: miles(resumen.total) },
            {
              etiqueta: "Récord",
              valor: miles(resumen.maximo),
              ayuda: resumen.diaMaximo ? formatoCorto(resumen.diaMaximo) : undefined,
            },
            {
              etiqueta: "Meta cumplida",
              valor: pct(resumen.porcentaje, 0),
              ayuda: `${resumen.cumplidos} de ${filtrados.length} días`,
              color: paleta.estado.bueno,
            },
            { etiqueta: "Racha actual", valor: `${resumen.rachaActual} d` },
          ]}
        />
      ),
    },
    {
      id: "linea-tiempo",
      titulo: "Pasos por día",
      ayuda: ventana === "0" ? undefined : `media móvil de ${ventana} días`,
      base: { x: 0, y: 3, w: 8, h: 9, minH: 5 },
      contenido: (
        <GraficaLineas
          datos={serie}
          x="f"
          series={[
            { clave: "v", nombre: "Pasos", tipo: "barra", color: paleta.series[0] },
            ...(ventana === "0"
              ? []
              : [
                  {
                    clave: "mm",
                    nombre: `Media ${ventana} días`,
                    tipo: "linea" as const,
                    color: paleta.series[1],
                  },
                ]),
          ]}
          formatoValor={miles}
          formatoX={(f) => formatoCorto(String(f))}
          referencias={[{ valor: meta, etiqueta: `Meta ${miles(meta)}`, color: paleta.estado.bueno }]}
        />
      ),
    },
    {
      id: "cumplimiento",
      titulo: "Cumplimiento de la meta",
      ayuda: `objetivo ${miles(meta)} pasos`,
      base: { x: 8, y: 3, w: 4, h: 9, minH: 5 },
      contenido: (
        <GraficaDonut
          datos={[
            { nombre: "Meta cumplida", valor: resumen.cumplidos, color: paleta.estado.bueno },
            {
              nombre: "Por debajo",
              valor: Math.max(0, filtrados.length - resumen.cumplidos),
              color: paleta.tinta.eje,
            },
          ]}
          formatoValor={(v) => `${miles(v)} días`}
          centro={{ valor: pct(resumen.porcentaje, 0), etiqueta: "de los días", color: paleta.estado.bueno }}
        />
      ),
    },
    {
      id: "mes-foco",
      titulo: "Mes en detalle",
      ayuda: `${resumenMesFoco.conDatos} de ${diasEnMes(mesFoco)} días con datos`,
      base: { x: 0, y: 12, w: 8, h: 9, minH: 5 },
      contenido: (
        <div className="flex h-full flex-col gap-2">
          <NavegadorMes
            etiqueta={formatoMesLargo(mesFoco)}
            onAnterior={() => setMesFoco((m) => sumarMeses(m, -1))}
            onSiguiente={() => setMesFoco((m) => sumarMeses(m, 1))}
            onHoy={() => setMesFoco(claveMesActual())}
            deshabilitarAnterior={mesFoco <= primerMesDatos}
            deshabilitarSiguiente={mesFoco >= ultimoMesNavegable}
            enHoy={mesFoco === claveMesActual()}
          />
          <div className="min-h-0 flex-1">
            <GraficaBarras
              datos={diasMesFoco}
              x="dia"
              series={[{ clave: "v", nombre: "Pasos" }]}
              formatoValor={(v) => miles(v)}
              coloresPorPunto={(punto) =>
                punto.v === null
                  ? paleta.tinta.eje
                  : punto.v >= meta
                    ? paleta.estado.bueno
                    : paleta.series[0]
              }
              referencias={[{ valor: meta, etiqueta: `Meta ${miles(meta)}`, color: paleta.estado.bueno }]}
              extraTooltip={(punto) => (punto.v === null ? "Sin datos" : formatoCorto(punto.f))}
            />
          </div>
        </div>
      ),
    },
    {
      id: "mes-foco-resumen",
      titulo: "Resumen del mes",
      base: { x: 8, y: 12, w: 4, h: 9, minH: 5 },
      contenido: (
        <RejillaKpis
          ancha={false}
          items={[
            { etiqueta: "Media diaria", valor: miles(resumenMesFoco.media) },
            { etiqueta: "Acumulado", valor: miles(resumenMesFoco.total) },
            {
              etiqueta: "Récord",
              valor: miles(resumenMesFoco.maximo),
              ayuda: resumenMesFoco.diaMaximo ? formatoCorto(resumenMesFoco.diaMaximo) : undefined,
            },
            {
              etiqueta: "Meta cumplida",
              valor: pct(resumenMesFoco.porcentaje, 0),
              ayuda: `${resumenMesFoco.cumplidos} de ${resumenMesFoco.conDatos} días`,
              color: paleta.estado.bueno,
            },
          ]}
        />
      ),
    },
    {
      id: "dia-semana",
      titulo: "Media por día de la semana",
      base: { x: 0, y: 21, w: 4, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porDiaSemana}
          x="dia"
          series={[{ clave: "media", nombre: "Media de pasos" }]}
          formatoValor={miles}
          referencias={[{ valor: meta, etiqueta: "Meta", color: paleta.estado.bueno }]}
        />
      ),
    },
    {
      id: "por-mes",
      titulo: "Media diaria por mes",
      base: { x: 4, y: 21, w: 8, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porMes}
          x="mes"
          series={[{ clave: "media", nombre: "Media de pasos" }]}
          formatoValor={miles}
          anguloX={-45}
          referencias={[{ valor: meta, etiqueta: "Meta", color: paleta.estado.bueno }]}
        />
      ),
    },
    {
      id: "histograma",
      titulo: "Distribución de días",
      ayuda: "días por rango de pasos",
      base: { x: 0, y: 28, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={histograma}
          x="rango"
          series={[{ clave: "dias", nombre: "Días" }]}
          formatoValor={(v) => `${miles(v)} días`}
          coloresPorPunto={(punto) =>
            Number(punto.inicio) >= meta ? paleta.estado.bueno : paleta.series[0]
          }
        />
      ),
    },
    {
      id: "frecuencia-rachas",
      titulo: "Rachas por duración",
      ayuda: "veces que se repitió cada racha",
      base: { x: 6, y: 28, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={frecuenciaRachas}
          x="dias"
          series={[{ clave: "veces", nombre: "Veces", color: paleta.estado.bueno }]}
          formatoValor={(v) => `${v} veces`}
          etiquetasDirectas
        />
      ),
    },
    {
      id: "mejores-rachas",
      titulo: "Mejores rachas cumpliendo la meta",
      base: { x: 0, y: 35, w: 4, h: 7, minH: 4 },
      contenido: (
        <Tabla
          filas={rachasCumplidas.slice(0, 25)}
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
      id: "mejores-dias",
      titulo: "Mejores días",
      base: { x: 4, y: 35, w: 4, h: 7, minH: 4 },
      contenido: (
        <Tabla
          filas={topDias}
          claveFila={(fila) => fila.f}
          columnas={[
            { clave: "f", titulo: "Fecha", render: (f) => formatoCorto(f.f) },
            {
              clave: "f",
              titulo: "Día",
              render: (f) => DIAS_ES[indiceDiaSemana(desdeClaveDia(f.f))],
            },
            { clave: "v", titulo: "Pasos", alineacion: "derecha", render: (f) => miles(f.v) },
          ]}
        />
      ),
    },
    {
      id: "peores-dias",
      titulo: "Peores días",
      base: { x: 8, y: 35, w: 4, h: 7, minH: 4 },
      contenido: (
        <Tabla
          filas={peoresDias}
          claveFila={(fila) => fila.f}
          columnas={[
            { clave: "f", titulo: "Fecha", render: (f) => formatoCorto(f.f) },
            {
              clave: "f",
              titulo: "Día",
              render: (f) => DIAS_ES[indiceDiaSemana(desdeClaveDia(f.f))],
            },
            { clave: "v", titulo: "Pasos", alineacion: "derecha", render: (f) => miles(f.v) },
          ]}
        />
      ),
    },
    {
      id: "heatmap",
      titulo: "Mes contra día de la semana",
      ayuda: "media de pasos",
      base: { x: 0, y: 42, w: 6, h: 8, minH: 5 },
      contenido: (
        <MapaCalor
          filas={heatmap.filas}
          columnas={DIAS_CORTOS}
          valores={heatmap.valores}
          formatoValor={miles}
          etiquetaValor="Media de pasos por mes y día de la semana"
        />
      ),
    },
    {
      id: "comparativa",
      titulo: "Acumulado por año",
      ayuda: comparativaAnios.anios.length < 2 ? "necesita dos años de datos" : undefined,
      base: { x: 6, y: 42, w: 6, h: 8, minH: 5 },
      contenido: (
        <GraficaLineas
          datos={comparativaAnios.datos}
          x="dia"
          series={comparativaAnios.anios.map((anio, i) => ({
            clave: anio,
            nombre: anio,
            color: paleta.series[i % paleta.series.length],
          }))}
          formatoValor={miles}
          formatoX={(v) => `día ${v}`}
        />
      ),
    },
    {
      id: "calendario",
      titulo: `Calendario de actividad ${calendario.anio}`,
      base: { x: 0, y: 50, w: 12, h: 5, minH: 4 },
      contenido: (
        <CalendarioAnual
          anio={calendario.anio}
          valoresPorDia={calendario.mapa}
          formatoValor={miles}
          etiqueta="Pasos por día"
        />
      ),
    },
  ];

  return <Tablero claveAlmacen="pasos" version={3} paneles={paneles} filtros={filtros} />;
}
