import { claveDia, sumarDias } from "./fechas";
import type {
  Actividad,
  Movimiento,
  ObjetivosLol,
  PartidaLol,
  Registro,
  RespuestaActividades,
  RespuestaPasos,
  TipoActividad,
  ZonasFc,
  ZonasRitmo,
} from "./tipos";

/**
 * Datos sinteticos para revisar el panel sin credenciales.
 * Se activan con ?demo=1 en la peticion o con DEMO_DATOS=1 en el entorno.
 */

function prng(semilla: number) {
  let estado = semilla >>> 0;
  return () => {
    estado = (estado * 1664525 + 1013904223) >>> 0;
    return estado / 4294967296;
  };
}

export function demoActivo(url: string): boolean {
  if (process.env.DEMO_DATOS === "1") return true;
  try {
    return new URL(url).searchParams.get("demo") === "1";
  } catch {
    return false;
  }
}

export function pasosDemo(): RespuestaPasos {
  const azar = prng(7);
  const hoy = new Date();
  const inicio = new Date(hoy.getFullYear() - 1, 0, 1);
  const dias: RespuestaPasos["dias"] = [];

  for (let d = inicio; d <= hoy; d = sumarDias(d, 1)) {
    const finde = d.getDay() === 0 || d.getDay() === 6;
    const base = finde ? 6500 : 9800;
    const estacion = Math.sin((d.getMonth() / 12) * Math.PI * 2) * 1200;
    const ruido = (azar() - 0.5) * 6000;
    const valor = Math.max(300, Math.round(base + estacion + ruido));
    const vacio = azar() < 0.04;
    dias.push({ f: claveDia(d), v: vacio ? Math.round(200 + azar() * 300) : valor, imp: vacio });
  }

  return {
    dias,
    meta: {
      rellenados: dias.filter((d) => d.imp).length,
      inf: 200,
      sup: 500,
      desde: dias[0]?.f ?? null,
      hasta: dias[dias.length - 1]?.f ?? null,
    },
  };
}

const CAMPEONES = ["Ahri", "Yasuo", "Lux", "Jinx", "Thresh", "Lee Sin", "Darius", "Kaisa", "Sett", "Viego"];
const ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];
const COLAS = [420, 440, 450, 400];

/** Objetivos verosimiles: el equipo que gana suele llevarse mas. */
function objetivosDemo(azar: () => number, gana: boolean): ObjetivosLol {
  const sesgo = gana ? 0.62 : 0.38;
  const primero = () => azar() < sesgo;
  const cuantos = (tope: number) => Math.round(azar() * tope * (gana ? 1 : 0.5));
  return {
    sangre: { total: cuantos(30), primero: primero() },
    dragon: { total: cuantos(4), primero: primero() },
    grubs: { total: cuantos(6), primero: primero() },
    heraldo: { total: cuantos(1), primero: primero() },
    torre: { total: cuantos(11), primero: primero() },
    baron: { total: cuantos(2), primero: primero() },
    atakhan: { total: cuantos(1), primero: primero() },
    inhibidor: { total: cuantos(3), primero: primero() },
  };
}

export function lolDemo(): { partidas: PartidaLol[]; puuid: string; riotId: string } {
  const azar = prng(21);
  const partidas: PartidaLol[] = [];
  const hoy = Date.now();

  for (let i = 0; i < 420; i++) {
    const dias = Math.floor(azar() * 400);
    const hora = 10 + Math.floor(azar() * 13);
    const fecha = new Date(hoy - dias * 86400000);
    fecha.setHours(hora, Math.floor(azar() * 60), 0, 0);

    const duracion = 900 + azar() * 1800;
    const win = azar() < 0.52;
    const kills = Math.round(azar() * 12);
    const deaths = Math.round(azar() * 9);
    const assists = Math.round(azar() * 15);
    const rol = ROLES[Math.floor(azar() * ROLES.length)];

    partidas.push({
      id: `DEMO_${i}`,
      fecha: fecha.getTime(),
      campeon: CAMPEONES[Math.floor(azar() * CAMPEONES.length)],
      tipoDanio: azar() < 0.5 ? "AP" : "AD",
      rol,
      win,
      lado: azar() < 0.5 ? "Azul" : "Rojo",
      kills,
      deaths,
      assists,
      kda: (kills + assists) / Math.max(1, deaths),
      danio: Math.round(8000 + azar() * 26000),
      vision: Math.round(10 + azar() * 40),
      oro: Math.round(7000 + (duracion / 60) * 320 + azar() * 3000),
      cs: Math.round((duracion / 60) * (4 + azar() * 4)),
      duracion,
      cola: COLAS[Math.floor(azar() * COLAS.length)],
      objetivos: objetivosDemo(azar, win),
      objetivosRival: objetivosDemo(azar, !win),
      companeros: {
        top: CAMPEONES[Math.floor(azar() * CAMPEONES.length)],
        jungla: CAMPEONES[Math.floor(azar() * CAMPEONES.length)],
        mid: CAMPEONES[Math.floor(azar() * CAMPEONES.length)],
        adc: CAMPEONES[Math.floor(azar() * CAMPEONES.length)],
        support: CAMPEONES[Math.floor(azar() * CAMPEONES.length)],
      },
      danioCompaneros: { top: "AD", jungla: "AD", mid: "AP", adc: "AD", support: "AP" },
    });
  }

  partidas.sort((a, b) => a.fecha - b.fecha);
  return { partidas, puuid: "demo-puuid", riotId: "Demo" };
}

export function registroDemo(): Registro[] {
  const azar = prng(99);
  const registros: Registro[] = [];
  const hoy = new Date();
  const inicio = new Date(hoy.getFullYear() - 1, 0, 1);

  for (let d = new Date(inicio); d <= hoy; d = sumarDias(d, 1)) {
    if (azar() < 0.35) continue;
    const veces = azar() < 0.2 ? 2 : 1;
    for (let k = 0; k < veces; k++) {
      const fecha = new Date(d);
      fecha.setHours(8 + Math.floor(azar() * 14), Math.floor(azar() * 60), 0, 0);
      registros.push({
        t: fecha.getTime(),
        dia: claveDia(fecha),
        minutos: Math.round(20 + azar() * 70),
      });
    }
  }

  registros.sort((a, b) => a.t - b.t);
  return registros;
}

const CONCEPTOS: [string, number, number][] = [
  ["COMPRA MERCADONA", -60, -12],
  ["BIZUM RECIBIDO", 10, 45],
  ["DOMINOS PIZZA", -28, -14],
  ["AMAZON MARKETPLACE", -75, -8],
  ["MOVISTAR FIBRA", -42, -42],
  ["STEAM GAMES", -35, -5],
  ["TESORO PUBLICO NOMINA", 900, 1300],
  ["ALSA BILLETE", -32, -12],
  ["CARREFOUR EXPRESS", -45, -9],
  ["PELUQUERIA CENTRO", -18, -12],
];

/** Ruta sintetica en forma de lazo, para que la miniatura del mapa tenga una forma reconocible. */
function trazaDemo(azar: () => number, lat0: number, lon0: number, puntos: number): [number, number][] {
  const radio = 0.004 + azar() * 0.01;
  const excentricidad = 0.6 + azar() * 0.6;
  const giro = azar() * Math.PI * 2;
  const traza: [number, number][] = [];
  for (let i = 0; i < puntos; i++) {
    const t = (i / (puntos - 1)) * Math.PI * 2;
    const ruido = (azar() - 0.5) * radio * 0.15;
    const lat = lat0 + Math.sin(t + giro) * radio + ruido;
    const lon = lon0 + Math.cos(t + giro) * radio * excentricidad + ruido;
    traza.push([Number(lat.toFixed(6)), Number(lon.toFixed(6))]);
  }
  return traza;
}

/** Reparte una duracion entre varias claves con pesos base + ruido, normalizado. */
function repartir<K extends string>(azar: () => number, duracion: number, pesos: [K, number][]): Record<K, number> {
  const brutos = pesos.map(([clave, peso]) => [clave, Math.max(0, peso + (azar() - 0.5) * peso * 0.6)] as [K, number]);
  const total = brutos.reduce((acc, [, v]) => acc + v, 0) || 1;
  const resultado = {} as Record<K, number>;
  for (const [clave, v] of brutos) resultado[clave] = Math.round((v / total) * duracion);
  return resultado;
}

function zonasFcDemo(azar: () => number, tipo: TipoActividad, duracionActiva: number): ZonasFc | null {
  if (tipo === "TRAINING" || duracionActiva <= 0 || azar() < 0.15) return null;
  const pesos: [keyof ZonasFc, number][] =
    tipo === "RUNNING"
      ? [["z1", 0.05], ["z2", 0.15], ["z3", 0.35], ["z4", 0.3], ["z5", 0.15]]
      : [["z1", 0.35], ["z2", 0.4], ["z3", 0.18], ["z4", 0.06], ["z5", 0.01]];
  return repartir(azar, duracionActiva, pesos);
}

function zonasRitmoDemo(azar: () => number, tipo: TipoActividad, duracionActiva: number): ZonasRitmo | null {
  if (tipo === "TRAINING" || duracionActiva <= 0 || azar() < 0.15) return null;
  const pesos: [keyof ZonasRitmo, number][] =
    tipo === "RUNNING"
      ? [["rapido", 0.25], ["medio", 0.4], ["trote", 0.2], ["caminando", 0.1], ["parado", 0.05]]
      : [["rapido", 0.01], ["medio", 0.04], ["trote", 0.1], ["caminando", 0.65], ["parado", 0.2]];
  return repartir(azar, duracionActiva, pesos);
}

function mejorMarcaDemo(azar: () => number, distanciaKm: number, ritmoBase: number, objetivoKm: number): number | null {
  if (distanciaKm < objetivoKm) return null;
  const factor = 0.9 + (1 - objetivoKm / 10) * 0.1;
  return Math.round(ritmoBase * factor * objetivoKm * (0.97 + azar() * 0.06));
}

export function actividadesDemo(): RespuestaActividades {
  const azar = prng(55);
  const hoy = new Date();
  const inicio = new Date(hoy.getFullYear(), 0, 1);
  const actividades: Actividad[] = [];
  const latBase = 40.4168;
  const lonBase = -3.7038;

  const pesos: [TipoActividad, number][] = [
    ["WALKING", 0.48],
    ["TRAINING", 0.36],
    ["RUNNING", 0.14],
    ["SWIMMING", 0.02],
  ];
  const elegirTipo = (): TipoActividad => {
    const r = azar();
    let acumulado = 0;
    for (const [tipo, peso] of pesos) {
      acumulado += peso;
      if (r < acumulado) return tipo;
    }
    return "WALKING";
  };

  let i = 0;
  for (let d = new Date(inicio); d <= hoy; d = sumarDias(d, 1)) {
    if (azar() < 0.55) continue;

    const tipo = elegirTipo();
    const fecha = new Date(d);
    fecha.setHours(7 + Math.floor(azar() * 14), Math.floor(azar() * 60), 0, 0);

    const conGps = (tipo === "RUNNING" || tipo === "WALKING") && azar() < 0.6;
    const distancia =
      tipo === "TRAINING" ? 0 : tipo === "SWIMMING" ? 0.5 + azar() * 1.5 : tipo === "RUNNING" ? 3 + azar() * 12 : 0.5 + azar() * 5;
    const velMedia = tipo === "RUNNING" ? 8 + azar() * 4 : tipo === "WALKING" ? 3.5 + azar() * 2 : 0;
    const duracionActiva = tipo === "TRAINING" ? 1200 + azar() * 3600 : velMedia > 0 ? Math.round((distancia / velMedia) * 3600) : 900 + azar() * 1800;

    const duracionActivaRedondeada = Math.round(duracionActiva);
    const ritmoBase = velMedia > 0 ? 3600 / velMedia : 420;

    actividades.push({
      id: `DEMO_${i}`,
      tipo,
      fecha: fecha.getTime(),
      duracionActiva: duracionActivaRedondeada,
      duracionTotal: Math.round(duracionActiva * (1 + azar() * 0.1)),
      distancia: Number(distancia.toFixed(2)),
      calorias: Math.round(duracionActiva * (0.08 + azar() * 0.1)),
      pasos: tipo === "SWIMMING" ? 0 : Math.round(distancia * (1250 + azar() * 250)),
      fcMedia: Math.round(90 + azar() * 50),
      fcMaxima: Math.round(140 + azar() * 45),
      velMedia: Number(velMedia.toFixed(2)),
      velMaxima: Number((velMedia * (1.2 + azar() * 0.4)).toFixed(2)),
      elevacion: conGps ? Math.round(azar() * 120) : null,
      mejor400: conGps ? mejorMarcaDemo(azar, distancia, ritmoBase, 0.4) : null,
      mejor1km: conGps ? mejorMarcaDemo(azar, distancia, ritmoBase, 1) : null,
      mejor2km: conGps ? mejorMarcaDemo(azar, distancia, ritmoBase, 2) : null,
      mejor5km: conGps ? mejorMarcaDemo(azar, distancia, ritmoBase, 5) : null,
      mejor10km: conGps ? mejorMarcaDemo(azar, distancia, ritmoBase, 10) : null,
      zonasFc: conGps ? zonasFcDemo(azar, tipo, duracionActivaRedondeada) : null,
      zonasRitmo: conGps ? zonasRitmoDemo(azar, tipo, duracionActivaRedondeada) : null,
      traza: conGps ? trazaDemo(azar, latBase, lonBase, 60 + Math.floor(azar() * 60)) : null,
      fuente: null,
    });
    i++;
  }

  actividades.sort((a, b) => a.fecha - b.fecha);
  return { actividades };
}

export function finanzasDemo(): Movimiento[] {
  const azar = prng(1234);
  const movimientos: Movimiento[] = [];
  const hoy = new Date();
  const inicio = new Date(hoy.getFullYear() - 1, 0, 1);
  let saldo = 2400;

  for (let d = new Date(inicio); d <= hoy; d = sumarDias(d, 1)) {
    const cuantos = azar() < 0.55 ? 1 + Math.floor(azar() * 2) : 0;
    for (let k = 0; k < cuantos; k++) {
      const [concepto, min, max] = CONCEPTOS[Math.floor(azar() * CONCEPTOS.length)];
      const importe = Number((min + azar() * (max - min)).toFixed(2));
      saldo = Number((saldo + importe).toFixed(2));
      const fecha = new Date(d);
      fecha.setHours(9 + Math.floor(azar() * 10));
      movimientos.push({
        dia: claveDia(fecha),
        t: fecha.getTime(),
        concepto,
        categoria: "",
        importe,
        saldo,
      });
    }
  }

  return movimientos;
}
