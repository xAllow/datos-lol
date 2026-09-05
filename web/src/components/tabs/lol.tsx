"use client";

import { useMemo, useState } from "react";
import { Tablero, type DefinicionPanel } from "@/components/tablero";
import { Cargando, ErrorCarga, Vacio } from "@/components/estados";
import { Deslizador, MultiSelector, RangoFechas, Segmentado } from "@/components/controles";
import { GraficaBarras, GraficaDispersion, GraficaDonut, GraficaLineas } from "@/components/charts/graficas";
import { MapaCalor, RejillaKpis, Tabla } from "@/components/charts/visuales";
import { usePaleta } from "@/components/tema";
import { useDatos } from "@/lib/datos";
import { compacto, dec1, dec2, miles, pct } from "@/lib/formato";
import { DIAS_CORTOS, DIAS_ES, claveDia, indiceDiaSemana } from "@/lib/fechas";
import type { ClaveObjetivo, PartidaLol, RespuestaLol } from "@/lib/tipos";

const COLAS: Record<number, string> = {
  400: "Normal Draft",
  420: "Solo/Duo",
  430: "Normal Blind",
  440: "Flexible",
  450: "ARAM",
  490: "Quickplay",
  700: "Clash",
  830: "Co-op vs IA",
  840: "Co-op vs IA",
  850: "Co-op vs IA",
  900: "URF",
  1700: "Arena",
  1900: "URF",
};

const ROLES_ES: Record<string, string> = {
  TOP: "Top",
  JUNGLE: "Jungla",
  MIDDLE: "Mid",
  BOTTOM: "ADC",
  UTILITY: "Support",
  UNKNOWN: "Sin rol",
};

const OBJETIVOS_ES: { clave: ClaveObjetivo; primero: string; nombre: string }[] = [
  { clave: "sangre", primero: "Primera sangre", nombre: "Asesinatos" },
  { clave: "dragon", primero: "Primer dragon", nombre: "Dragones" },
  { clave: "grubs", primero: "Primeras grubs", nombre: "Grubs" },
  { clave: "heraldo", primero: "Primer heraldo", nombre: "Heraldos" },
  { clave: "torre", primero: "Primera torre", nombre: "Torres" },
  { clave: "baron", primero: "Primer baron", nombre: "Barones" },
  { clave: "atakhan", primero: "Primer atakhan", nombre: "Atakhan" },
];

/** Objetivos con grafica propia de winrate por cantidad conseguida. */
const OBJETIVOS_CONTEO: { clave: ClaveObjetivo; titulo: string; tope: number }[] = [
  { clave: "dragon", titulo: "dragones", tope: 4 },
  { clave: "grubs", titulo: "grubs", tope: 6 },
  { clave: "baron", titulo: "barones", tope: 2 },
  { clave: "heraldo", titulo: "heraldos", tope: 2 },
];

/** Los que se comparan bien entre si: fuera asesinatos (otra escala) y torres. */
const OBJETIVOS_MEDIA: ClaveObjetivo[] = ["dragon", "grubs", "heraldo", "baron", "torre"];

const LINEAS_COMPANERO: { clave: string; titulo: string }[] = [
  { clave: "top", titulo: "top" },
  { clave: "jungla", titulo: "jungla" },
  { clave: "mid", titulo: "mid" },
  { clave: "adc", titulo: "ADC" },
  { clave: "support", titulo: "support" },
];

const nombreCola = (id: number | null) => (id === null ? "Desconocida" : (COLAS[id] ?? `Cola ${id}`));

/** Tipo de dano del mid del equipo: el mio si juego ahi, si no el del companero. */
/** Winrate por cuantos objetivos de un tipo se llevo el equipo. El ultimo cubo agrupa "y mas". */
function porConteo(partidas: PartidaLol[], clave: ClaveObjetivo, tope: number) {
  const cubos = new Map<number, PartidaLol[]>();
  for (const p of partidas) {
    const n = Math.min(tope, p.objetivos?.[clave]?.total ?? 0);
    const lista = cubos.get(n) ?? [];
    lista.push(p);
    cubos.set(n, lista);
  }
  return [...cubos.entries()]
    .sort(([a], [b]) => a - b)
    .map(([n, lista]) => ({
      conteo: n === tope ? `${tope}+` : String(n),
      partidas: lista.length,
      wr: winrate(lista),
    }));
}

function danioMid(p: PartidaLol): string {
  const tipo = p.rol === "MIDDLE" ? p.tipoDanio : p.danioCompaneros?.mid;
  return tipo === "AD" || tipo === "AP" ? tipo : "Desconocido";
}

function winrate(partidas: PartidaLol[]): number {
  if (!partidas.length) return 0;
  return (partidas.filter((p) => p.win).length / partidas.length) * 100;
}

export function PestanaLol() {
  const { datos, cargando, error, recargar } = useDatos<RespuestaLol>("/api/lol");
  const paleta = usePaleta();

  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [preset, setPreset] = useState("todo");
  const [roles, setRoles] = useState<string[]>([]);
  const [campeones, setCampeones] = useState<string[]>([]);
  const [colas, setColas] = useState<string[]>([]);
  const [lado, setLado] = useState("todos");
  const [midDanio, setMidDanio] = useState("todos");
  const [resultado, setResultado] = useState("todos");
  const [duracionMin, setDuracionMin] = useState(0);
  const [horaDesde, setHoraDesde] = useState(0);
  const [horaHasta, setHoraHasta] = useState(23);

  const todas = useMemo(() => datos?.partidas ?? [], [datos]);

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

  const opcionesRol = useMemo(
    () =>
      [...new Set(todas.map((p) => p.rol))]
        .sort()
        .map((r) => ({ valor: r, texto: ROLES_ES[r] ?? r })),
    [todas],
  );

  const opcionesCampeon = useMemo(() => {
    const cuenta = new Map<string, number>();
    for (const p of todas) cuenta.set(p.campeon, (cuenta.get(p.campeon) ?? 0) + 1);
    return [...cuenta.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([campeon, n]) => ({ valor: campeon, texto: `${campeon} (${n})` }));
  }, [todas]);

  const opcionesCola = useMemo(() => {
    const cuenta = new Map<string, number>();
    for (const p of todas) {
      const nombre = nombreCola(p.cola);
      cuenta.set(nombre, (cuenta.get(nombre) ?? 0) + 1);
    }
    return [...cuenta.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([nombre, n]) => ({ valor: nombre, texto: `${nombre} (${n})` }));
  }, [todas]);

  const partidas = useMemo(() => {
    return todas.filter((p) => {
      const fecha = new Date(p.fecha);
      const dia = claveDia(fecha);
      if (desde && dia < desde) return false;
      if (hasta && dia > hasta) return false;
      if (roles.length && !roles.includes(p.rol)) return false;
      if (campeones.length && !campeones.includes(p.campeon)) return false;
      if (colas.length && !colas.includes(nombreCola(p.cola))) return false;
      if (lado !== "todos" && p.lado !== lado) return false;
      if (midDanio !== "todos" && danioMid(p) !== midDanio) return false;
      if (resultado === "victorias" && !p.win) return false;
      if (resultado === "derrotas" && p.win) return false;
      if (p.duracion / 60 < duracionMin) return false;
      const hora = fecha.getHours();
      if (hora < horaDesde || hora > horaHasta) return false;
      return true;
    });
  }, [
    todas,
    desde,
    hasta,
    roles,
    campeones,
    colas,
    lado,
    midDanio,
    resultado,
    duracionMin,
    horaDesde,
    horaHasta,
  ]);

  const resumen = useMemo(() => {
    if (!partidas.length) {
      return { total: 0, wr: 0, kda: 0, kills: 0, deaths: 0, assists: 0, duracion: 0, danio: 0, csMin: 0 };
    }
    const suma = (fn: (p: PartidaLol) => number) => partidas.reduce((acc, p) => acc + fn(p), 0);
    const n = partidas.length;
    return {
      total: n,
      wr: winrate(partidas),
      kda: suma((p) => p.kda) / n,
      kills: suma((p) => p.kills) / n,
      deaths: suma((p) => p.deaths) / n,
      assists: suma((p) => p.assists) / n,
      duracion: suma((p) => p.duracion) / n / 60,
      danio: suma((p) => p.danio) / n,
      csMin: suma((p) => (p.duracion ? p.cs / (p.duracion / 60) : 0)) / n,
    };
  }, [partidas]);

  const porCampeon = useMemo(() => {
    const mapa = new Map<string, PartidaLol[]>();
    for (const p of partidas) {
      const lista = mapa.get(p.campeon) ?? [];
      lista.push(p);
      mapa.set(p.campeon, lista);
    }
    return [...mapa.entries()]
      .map(([campeon, lista]) => ({
        campeon,
        partidas: lista.length,
        victorias: lista.filter((p) => p.win).length,
        derrotas: lista.filter((p) => !p.win).length,
        wr: winrate(lista),
        kills: lista.reduce((a, p) => a + p.kills, 0) / lista.length,
        deaths: lista.reduce((a, p) => a + p.deaths, 0) / lista.length,
        assists: lista.reduce((a, p) => a + p.assists, 0) / lista.length,
        kda: lista.reduce((a, p) => a + p.kda, 0) / lista.length,
      }))
      .sort((a, b) => b.partidas - a.partidas);
  }, [partidas]);

  const porRol = useMemo(() => {
    const mapa = new Map<string, PartidaLol[]>();
    for (const p of partidas) {
      const lista = mapa.get(p.rol) ?? [];
      lista.push(p);
      mapa.set(p.rol, lista);
    }
    return [...mapa.entries()]
      .map(([rol, lista]) => ({
        rol: ROLES_ES[rol] ?? rol,
        victorias: lista.filter((p) => p.win).length,
        derrotas: lista.filter((p) => !p.win).length,
        partidas: lista.length,
        wr: winrate(lista),
      }))
      .sort((a, b) => b.partidas - a.partidas);
  }, [partidas]);

  const porDuracion = useMemo(() => {
    const cubos = new Map<number, PartidaLol[]>();
    for (const p of partidas) {
      const cubo = Math.min(50, Math.floor(p.duracion / 60 / 5) * 5);
      const lista = cubos.get(cubo) ?? [];
      lista.push(p);
      cubos.set(cubo, lista);
    }
    return [...cubos.entries()]
      .sort(([a], [b]) => a - b)
      .map(([cubo, lista]) => ({
        rango: `${cubo}-${cubo + 5}`,
        partidas: lista.length,
        wr: winrate(lista),
      }));
  }, [partidas]);

  const porHora = useMemo(() => {
    const cubos = new Map<number, PartidaLol[]>();
    for (const p of partidas) {
      const hora = new Date(p.fecha).getHours();
      const lista = cubos.get(hora) ?? [];
      lista.push(p);
      cubos.set(hora, lista);
    }
    return [...cubos.entries()]
      .sort(([a], [b]) => a - b)
      .map(([hora, lista]) => ({
        hora: `${String(hora).padStart(2, "0")}h`,
        partidas: lista.length,
        wr: winrate(lista),
      }));
  }, [partidas]);

  const porDiaSemana = useMemo(() => {
    const cubos: PartidaLol[][] = DIAS_ES.map(() => []);
    for (const p of partidas) cubos[indiceDiaSemana(new Date(p.fecha))].push(p);
    return DIAS_CORTOS.map((dia, i) => ({
      dia,
      partidas: cubos[i].length,
      wr: winrate(cubos[i]),
    }));
  }, [partidas]);

  const porSemana = useMemo(() => {
    const cubos = new Map<string, PartidaLol[]>();
    for (const p of partidas) {
      const fecha = new Date(p.fecha);
      const lunes = new Date(fecha);
      lunes.setDate(fecha.getDate() - indiceDiaSemana(fecha));
      const clave = claveDia(lunes);
      const lista = cubos.get(clave) ?? [];
      lista.push(p);
      cubos.set(clave, lista);
    }
    return [...cubos.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([semana, lista]) => ({
        semana,
        partidas: lista.length,
        wr: winrate(lista),
      }));
  }, [partidas]);

  const heatmapHoraDia = useMemo(() => {
    const horas = [...new Set(partidas.map((p) => new Date(p.fecha).getHours()))].sort((a, b) => a - b);
    const acumulado = new Map<string, PartidaLol[]>();
    for (const p of partidas) {
      const fecha = new Date(p.fecha);
      const clave = `${fecha.getHours()}-${indiceDiaSemana(fecha)}`;
      const lista = acumulado.get(clave) ?? [];
      lista.push(p);
      acumulado.set(clave, lista);
    }
    const valores = horas.map((h) =>
      DIAS_CORTOS.map((_, d) => {
        const lista = acumulado.get(`${h}-${d}`);
        return lista && lista.length ? winrate(lista) : null;
      }),
    );
    return { filas: horas.map((h) => `${String(h).padStart(2, "0")}h`), valores };
  }, [partidas]);

  const dispersionOro = useMemo(() => {
    const puntos = (gana: boolean) =>
      partidas
        .filter((p) => p.win === gana && p.rol !== "UNKNOWN")
        .map((p) => ({ minutos: Number((p.duracion / 60).toFixed(1)), oro: p.oro, campeon: p.campeon }));
    return [
      { nombre: "Victoria", color: paleta.estado.bueno, datos: puntos(true) },
      { nombre: "Derrota", color: paleta.estado.critico, datos: puntos(false) },
    ];
  }, [partidas, paleta]);

  const sinergias = useMemo(() => {
    return LINEAS_COMPANERO.map(({ clave, titulo }) => {
      const mapa = new Map<string, PartidaLol[]>();
      for (const p of partidas) {
        const companero = p.companeros?.[clave];
        if (!companero) continue;
        const lista = mapa.get(companero) ?? [];
        lista.push(p);
        mapa.set(companero, lista);
      }
      const filas = [...mapa.entries()]
        .map(([campeon, lista]) => ({
          campeon,
          partidas: lista.length,
          victorias: lista.filter((p) => p.win).length,
          derrotas: lista.filter((p) => !p.win).length,
          wr: winrate(lista),
        }))
        .sort((a, b) => b.partidas - a.partidas)
        .slice(0, 10);
      return { clave, titulo, filas };
    });
  }, [partidas]);

  const porMid = useMemo(() => {
    const mapa = new Map<string, PartidaLol[]>();
    for (const p of partidas) {
      const tipo = danioMid(p);
      const lista = mapa.get(tipo) ?? [];
      lista.push(p);
      mapa.set(tipo, lista);
    }
    return ["AD", "AP", "Desconocido"]
      .filter((tipo) => mapa.has(tipo))
      .map((tipo) => {
        const lista = mapa.get(tipo)!;
        return {
          tipo,
          partidas: lista.length,
          victorias: lista.filter((p) => p.win).length,
          derrotas: lista.filter((p) => !p.win).length,
          wr: winrate(lista),
          kda: lista.reduce((a, p) => a + p.kda, 0) / lista.length,
        };
      });
  }, [partidas]);

  const porObjetivo = useMemo(() => {
    return OBJETIVOS_ES.map(({ clave, primero }) => {
      const con = partidas.filter((p) => p.objetivos?.[clave]?.primero);
      const sin = partidas.filter((p) => !p.objetivos?.[clave]?.primero);
      return {
        objetivo: primero,
        con: con.length,
        sin: sin.length,
        conseguido: winrate(con),
        perdido: winrate(sin),
        tasa: partidas.length ? (con.length / partidas.length) * 100 : 0,
      };
      // Atakhan solo existe en parches recientes: si nunca aparece, se descarta.
    }).filter((fila) => fila.con > 0);
  }, [partidas]);

  const conteoObjetivos = useMemo(
    () => OBJETIVOS_CONTEO.map((o) => ({ ...o, filas: porConteo(partidas, o.clave, o.tope) })),
    [partidas],
  );

  const objetivosMedios = useMemo(() => {
    const media = (lista: PartidaLol[], leer: (p: PartidaLol) => number) =>
      lista.length ? lista.reduce((a, p) => a + leer(p), 0) / lista.length : 0;
    return OBJETIVOS_MEDIA.map((clave) => {
      const nombre = OBJETIVOS_ES.find((o) => o.clave === clave)!.nombre;
      return {
        objetivo: nombre,
        mios: media(partidas, (p) => p.objetivos?.[clave]?.total ?? 0),
        rivales: media(partidas, (p) => p.objetivosRival?.[clave]?.total ?? 0),
      };
    });
  }, [partidas]);

  const ultimas = useMemo(() => [...partidas].reverse().slice(0, 60), [partidas]);

  if (cargando) return <Cargando mensaje="Cargando partidas desde MongoDB..." />;
  if (error) return <ErrorCarga mensaje={error} onReintentar={recargar} />;
  if (!todas.length) return <Vacio mensaje="No hay partidas guardadas para esta cuenta." />;

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
      <MultiSelector etiqueta="Rol" valores={roles} onChange={setRoles} opciones={opcionesRol} ancho="w-36" />
      <MultiSelector
        etiqueta="Campeón"
        valores={campeones}
        onChange={setCampeones}
        opciones={opcionesCampeon}
        ancho="w-44"
      />
      <MultiSelector etiqueta="Cola" valores={colas} onChange={setColas} opciones={opcionesCola} ancho="w-40" />
      <Segmentado
        etiqueta="Lado"
        valor={lado}
        onChange={setLado}
        opciones={[
          { valor: "todos", texto: "Ambos" },
          { valor: "Azul", texto: "Azul" },
          { valor: "Rojo", texto: "Rojo" },
        ]}
      />
      <Segmentado
        etiqueta="Dano del mid"
        valor={midDanio}
        onChange={setMidDanio}
        opciones={[
          { valor: "todos", texto: "Todo" },
          { valor: "AD", texto: "AD" },
          { valor: "AP", texto: "AP" },
        ]}
      />
      <Segmentado
        etiqueta="Resultado"
        valor={resultado}
        onChange={setResultado}
        opciones={[
          { valor: "todos", texto: "Todo" },
          { valor: "victorias", texto: "Ganadas" },
          { valor: "derrotas", texto: "Perdidas" },
        ]}
      />
      <Deslizador
        etiqueta="Duración mínima"
        valor={duracionMin}
        min={0}
        max={40}
        paso={5}
        onChange={setDuracionMin}
        formato={(v) => `${v} min`}
        ancho="w-28"
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

  const seriesVictoriaDerrota = [
    { clave: "victorias", nombre: "Victoria", color: paleta.estado.bueno },
    { clave: "derrotas", nombre: "Derrota", color: paleta.estado.critico },
  ];

  const colorMid = (tipo: string) =>
    tipo === "AD" ? paleta.series[1] : tipo === "AP" ? paleta.series[6] : paleta.tinta.apagado;

  const paneles: DefinicionPanel[] = [
    {
      id: "resumen",
      titulo: "Resumen",
      ayuda: `${partidas.length} partidas con los filtros actuales`,
      base: { x: 0, y: 0, w: 12, h: 3, minH: 3 },
      contenido: (
        <RejillaKpis
          items={[
            { etiqueta: "Partidas", valor: miles(resumen.total) },
            {
              etiqueta: "Winrate",
              valor: pct(resumen.wr, 1),
              color: resumen.wr >= 50 ? paleta.estado.bueno : paleta.estado.critico,
            },
            {
              etiqueta: "KDA",
              valor: dec2(resumen.kda),
              ayuda: `${dec1(resumen.kills)} / ${dec1(resumen.deaths)} / ${dec1(resumen.assists)}`,
            },
            { etiqueta: "Duración media", valor: `${dec1(resumen.duracion)} min` },
            { etiqueta: "Daño medio", valor: compacto(resumen.danio) },
            { etiqueta: "CS por minuto", valor: dec2(resumen.csMin) },
          ]}
        />
      ),
    },
    {
      id: "winrate-donut",
      titulo: "Victorias y derrotas",
      base: { x: 0, y: 3, w: 3, h: 7, minH: 5 },
      contenido: (
        <GraficaDonut
          datos={[
            {
              nombre: "Victoria",
              valor: partidas.filter((p) => p.win).length,
              color: paleta.estado.bueno,
            },
            {
              nombre: "Derrota",
              valor: partidas.filter((p) => !p.win).length,
              color: paleta.estado.critico,
            },
          ]}
          formatoValor={(v) => `${miles(v)} partidas`}
          centro={{
            valor: pct(resumen.wr, 1),
            etiqueta: "winrate",
            color: resumen.wr >= 50 ? paleta.estado.bueno : paleta.estado.critico,
          }}
        />
      ),
    },
    {
      id: "lado",
      titulo: "Winrate por lado",
      base: { x: 3, y: 3, w: 3, h: 7, minH: 5 },
      contenido: (
        <GraficaBarras
          datos={["Azul", "Rojo"].map((l) => {
            const lista = partidas.filter((p) => p.lado === l);
            return { lado: l, wr: winrate(lista), partidas: lista.length };
          })}
          x="lado"
          series={[{ clave: "wr", nombre: "Winrate" }]}
          formatoValor={(v) => pct(v, 1)}
          coloresPorPunto={(punto) => (punto.lado === "Azul" ? paleta.series[0] : paleta.series[7])}
          etiquetasDirectas
          referencias={[{ valor: 50, etiqueta: "50%", color: paleta.tinta.secundario }]}
          extraTooltip={(punto) => `${miles(punto.partidas)} partidas`}
        />
      ),
    },
    {
      id: "campeones",
      titulo: "Campeones más jugados",
      ayuda: "victorias y derrotas",
      base: { x: 6, y: 3, w: 6, h: 7, minH: 5 },
      contenido: (
        <GraficaBarras
          datos={porCampeon.slice(0, 8)}
          x="campeon"
          series={seriesVictoriaDerrota}
          apilado
          horizontal
          formatoValor={(v) => `${v} partidas`}
          anchoEjeCategoria={84}
        />
      ),
    },
    {
      id: "tabla-campeones",
      titulo: "Detalle por campeón",
      base: { x: 0, y: 10, w: 6, h: 8, minH: 5 },
      contenido: (
        <Tabla
          filas={porCampeon}
          claveFila={(fila) => fila.campeon}
          columnas={[
            { clave: "campeon", titulo: "Campeón" },
            { clave: "partidas", titulo: "Partidas", alineacion: "derecha" },
            {
              clave: "wr",
              titulo: "Winrate",
              alineacion: "derecha",
              render: (f) => (
                <span style={{ color: f.wr >= 50 ? paleta.estado.bueno : paleta.estado.critico }}>
                  {pct(f.wr, 0)}
                </span>
              ),
            },
            { clave: "kills", titulo: "K", alineacion: "derecha", render: (f) => dec1(f.kills) },
            { clave: "deaths", titulo: "D", alineacion: "derecha", render: (f) => dec1(f.deaths) },
            { clave: "assists", titulo: "A", alineacion: "derecha", render: (f) => dec1(f.assists) },
            { clave: "kda", titulo: "KDA", alineacion: "derecha", render: (f) => dec2(f.kda) },
          ]}
        />
      ),
    },
    {
      id: "roles",
      titulo: "Resultados por línea",
      base: { x: 6, y: 10, w: 6, h: 8, minH: 5 },
      contenido: (
        <GraficaBarras
          datos={porRol}
          x="rol"
          series={seriesVictoriaDerrota}
          apilado
          horizontal
          formatoValor={(v) => `${v} partidas`}
          anchoEjeCategoria={70}
        />
      ),
    },
    {
      id: "winrate-duracion",
      titulo: "Winrate según la duración",
      ayuda: "tramos de 5 minutos",
      base: { x: 0, y: 18, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaLineas
          datos={porDuracion}
          x="rango"
          series={[{ clave: "wr", nombre: "Winrate", color: paleta.series[0] }]}
          formatoValor={(v) => pct(v, 1)}
          puntos
          referencias={[{ valor: 50, etiqueta: "50%", color: paleta.tinta.secundario }]}
        />
      ),
    },
    {
      id: "distribucion-duracion",
      titulo: "Duración de las partidas",
      base: { x: 6, y: 18, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porDuracion}
          x="rango"
          series={[{ clave: "partidas", nombre: "Partidas" }]}
          formatoValor={(v) => `${miles(v)} partidas`}
          etiquetasDirectas
        />
      ),
    },
    {
      id: "winrate-hora",
      titulo: "Winrate por hora del día",
      base: { x: 0, y: 25, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porHora}
          x="hora"
          series={[{ clave: "wr", nombre: "Winrate" }]}
          formatoValor={(v) => pct(v, 1)}
          referencias={[{ valor: 50, etiqueta: "50%", color: paleta.tinta.secundario }]}
          extraTooltip={(punto) => `${miles(punto.partidas)} partidas`}
        />
      ),
    },
    {
      id: "partidas-hora",
      titulo: "Partidas por hora del día",
      base: { x: 6, y: 25, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porHora}
          x="hora"
          series={[{ clave: "partidas", nombre: "Partidas", color: paleta.series[2] }]}
          formatoValor={(v) => `${miles(v)} partidas`}
          extraTooltip={(punto) => `winrate ${pct(punto.wr, 1)}`}
        />
      ),
    },
    {
      id: "dia-semana",
      titulo: "Winrate por día de la semana",
      base: { x: 0, y: 32, w: 4, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porDiaSemana}
          x="dia"
          series={[{ clave: "wr", nombre: "Winrate" }]}
          formatoValor={(v) => pct(v, 1)}
          referencias={[{ valor: 50, etiqueta: "50%", color: paleta.tinta.secundario }]}
          extraTooltip={(punto) => `${miles(punto.partidas)} partidas`}
        />
      ),
    },
    {
      id: "heatmap",
      titulo: "Winrate por hora y día",
      base: { x: 4, y: 32, w: 4, h: 9, minH: 5 },
      contenido: (
        <MapaCalor
          filas={heatmapHoraDia.filas}
          columnas={DIAS_CORTOS}
          valores={heatmapHoraDia.valores}
          formatoValor={(v) => pct(v, 0)}
          etiquetaValor="Winrate por hora y día de la semana"
        />
      ),
    },
    {
      id: "oro",
      titulo: "Oro conseguido según la duración",
      base: { x: 8, y: 32, w: 4, h: 9, minH: 5 },
      contenido: (
        <GraficaDispersion
          grupos={dispersionOro}
          x="minutos"
          y="oro"
          nombreX="Minutos"
          nombreY="Oro"
          formatoX={(v) => `${dec1(v)} min`}
          formatoY={compacto}
        />
      ),
    },
    {
      id: "semanal-partidas",
      titulo: "Partidas por semana",
      base: { x: 0, y: 41, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={porSemana}
          x="semana"
          series={[{ clave: "partidas", nombre: "Partidas" }]}
          formatoValor={(v) => `${miles(v)} partidas`}
          formatoX={(v) => String(v).slice(5)}
          anguloX={-45}
        />
      ),
    },
    {
      id: "semanal-winrate",
      titulo: "Winrate por semana",
      base: { x: 6, y: 41, w: 6, h: 7, minH: 4 },
      contenido: (
        <GraficaLineas
          datos={porSemana}
          x="semana"
          series={[{ clave: "wr", nombre: "Winrate", color: paleta.series[0] }]}
          formatoValor={(v) => pct(v, 1)}
          formatoX={(v) => String(v).slice(5)}
          puntos
          referencias={[{ valor: 50, etiqueta: "50%", color: paleta.tinta.secundario }]}
        />
      ),
    },
    {
      id: "mid-reparto",
      titulo: "Mid AD o AP",
      ayuda: "tipo de dano del mid de mi equipo",
      base: { x: 0, y: 48, w: 4, h: 8, minH: 5 },
      contenido: (
        <GraficaDonut
          datos={porMid.map((f) => ({ nombre: f.tipo, valor: f.partidas, color: colorMid(f.tipo) }))}
          formatoValor={(v) => `${miles(v)} partidas`}
          centro={{ valor: miles(partidas.length), etiqueta: "partidas" }}
        />
      ),
    },
    {
      id: "mid-winrate",
      titulo: "Winrate segun el dano del mid",
      base: { x: 4, y: 48, w: 4, h: 8, minH: 5 },
      contenido: (
        <GraficaBarras
          datos={porMid}
          x="tipo"
          series={[{ clave: "wr", nombre: "Winrate" }]}
          formatoValor={(v) => pct(v, 1)}
          coloresPorPunto={(punto) => colorMid(punto.tipo)}
          etiquetasDirectas
          referencias={[{ valor: 50, etiqueta: "50%", color: paleta.tinta.secundario }]}
          extraTooltip={(punto) => `${miles(punto.partidas)} partidas - KDA ${dec2(punto.kda)}`}
        />
      ),
    },
    {
      id: "mid-resultados",
      titulo: "Partidas del mid por resultado",
      base: { x: 8, y: 48, w: 4, h: 8, minH: 5 },
      contenido: (
        <GraficaBarras
          datos={porMid}
          x="tipo"
          series={seriesVictoriaDerrota}
          apilado
          formatoValor={(v) => `${v} partidas`}
        />
      ),
    },
    {
      id: "objetivos-winrate",
      titulo: "Winrate por objetivo",
      ayuda: "comparando las partidas en las que me lo llevo y en las que no",
      base: { x: 0, y: 56, w: 6, h: 9, minH: 5 },
      contenido: (
        <GraficaBarras
          datos={porObjetivo}
          x="objetivo"
          series={[
            { clave: "conseguido", nombre: "Lo consigo", color: paleta.estado.bueno },
            { clave: "perdido", nombre: "No lo consigo", color: paleta.estado.critico },
          ]}
          horizontal
          formatoValor={(v) => pct(v, 1)}
          anchoEjeCategoria={104}
          referencias={[{ valor: 50, etiqueta: "50%", color: paleta.tinta.secundario }]}
          extraTooltip={(punto) => `${miles(punto.con)} a favor / ${miles(punto.sin)} en contra`}
        />
      ),
    },
    {
      id: "objetivos-tasa",
      titulo: "Cuantas veces me llevo el objetivo",
      ayuda: "porcentaje de partidas en las que consigo el primero",
      base: { x: 6, y: 56, w: 6, h: 9, minH: 5 },
      contenido: (
        <GraficaBarras
          datos={porObjetivo}
          x="objetivo"
          series={[{ clave: "tasa", nombre: "Partidas" }]}
          horizontal
          formatoValor={(v) => pct(v, 1)}
          anchoEjeCategoria={104}
          etiquetasDirectas
          referencias={[{ valor: 50, etiqueta: "50%", color: paleta.tinta.secundario }]}
          extraTooltip={(punto) => `${miles(punto.con)} de ${miles(punto.con + punto.sin)} partidas`}
        />
      ),
    },
    ...conteoObjetivos.map((objetivo, i) => ({
      id: `winrate-conteo-${objetivo.clave}`,
      titulo: `Winrate por ${objetivo.titulo}`,
      ayuda: `${objetivo.titulo} que consigue mi equipo en la partida`,
      base: { x: i * 3, y: 65, w: 3, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={objetivo.filas}
          x="conteo"
          series={[{ clave: "wr", nombre: "Winrate" }]}
          formatoValor={(v) => pct(v, 1)}
          etiquetasDirectas
          referencias={[{ valor: 50, etiqueta: "50%", color: paleta.tinta.secundario }]}
          extraTooltip={(punto) => `${miles(punto.partidas)} partidas`}
        />
      ),
    })),
    {
      id: "objetivos-medios",
      titulo: "Objetivos por partida: mi equipo y el rival",
      base: { x: 0, y: 72, w: 12, h: 7, minH: 4 },
      contenido: (
        <GraficaBarras
          datos={objetivosMedios}
          x="objetivo"
          series={[
            { clave: "mios", nombre: "Mi equipo", color: paleta.series[0] },
            { clave: "rivales", nombre: "Rival", color: paleta.series[1] },
          ]}
          horizontal
          formatoValor={(v) => dec2(v)}
          anchoEjeCategoria={78}
        />
      ),
    },
    ...sinergias.map((sinergia, i) => ({
      id: `sinergia-${sinergia.clave}`,
      titulo: `Compañero ${sinergia.titulo}`,
      ayuda: "resultados jugando con cada campeón",
      base: { x: (i % 3) * 4, y: 79 + Math.floor(i / 3) * 8, w: 4, h: 8, minH: 5 },
      contenido: (
        <GraficaBarras
          datos={sinergia.filas}
          x="campeon"
          series={seriesVictoriaDerrota}
          apilado
          horizontal
          formatoValor={(v) => `${v} partidas`}
          anchoEjeCategoria={80}
        />
      ),
    })),
    {
      id: "ultimas",
      titulo: "Últimas partidas",
      base: { x: 0, y: 95, w: 12, h: 9, minH: 5 },
      contenido: (
        <Tabla
          filas={ultimas}
          claveFila={(fila) => fila.id}
          columnas={[
            {
              clave: "fecha",
              titulo: "Fecha",
              render: (f) => new Date(f.fecha).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" }),
            },
            { clave: "campeon", titulo: "Campeón" },
            { clave: "rol", titulo: "Línea", render: (f) => ROLES_ES[f.rol] ?? f.rol },
            {
              clave: "win",
              titulo: "Resultado",
              render: (f) => (
                <span style={{ color: f.win ? paleta.estado.bueno : paleta.estado.critico }}>
                  {f.win ? "Victoria" : "Derrota"}
                </span>
              ),
            },
            {
              clave: "kills",
              titulo: "K / D / A",
              alineacion: "derecha",
              render: (f) => `${f.kills} / ${f.deaths} / ${f.assists}`,
            },
            { clave: "danio", titulo: "Daño", alineacion: "derecha", render: (f) => compacto(f.danio) },
            { clave: "oro", titulo: "Oro", alineacion: "derecha", render: (f) => compacto(f.oro) },
            {
              clave: "duracion",
              titulo: "Duración",
              alineacion: "derecha",
              render: (f) => `${dec1(f.duracion / 60)} min`,
            },
            { clave: "cola", titulo: "Cola", render: (f) => nombreCola(f.cola) },
          ]}
        />
      ),
    },
  ];

  return <Tablero claveAlmacen="lol" version={4} paneles={paneles} filtros={filtros} />;
}
