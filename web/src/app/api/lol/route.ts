import { NextResponse } from "next/server";
import { cachear } from "@/lib/cache";
import { COLECCION_LOL, getDb, mongoConfigurado } from "@/lib/mongo";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import type { ClaveObjetivo, ObjetivosLol, PartidaLol, RespuestaLol } from "@/lib/tipos";
import { demoActivo, lolDemo } from "@/lib/demo";

const ROLES: Record<string, string> = {
  top: "TOP",
  jungla: "JUNGLE",
  mid: "MIDDLE",
  adc: "BOTTOM",
  support: "UTILITY",
};

const OBJETIVOS: Record<ClaveObjetivo, string> = {
  sangre: "champion",
  dragon: "dragon",
  grubs: "horde",
  heraldo: "riftHerald",
  torre: "tower",
  baron: "baron",
  atakhan: "atakhan",
  inhibidor: "inhibitor",
};

/** Los objetivos vienen por equipo en info.teams[].objectives. */
function leerObjetivos(equipo: Record<string, any> | undefined): ObjetivosLol {
  const crudos = equipo?.objectives ?? {};
  const salida = {} as ObjetivosLol;
  for (const [clave, campo] of Object.entries(OBJETIVOS) as [ClaveObjetivo, string][]) {
    const dato = crudos[campo] ?? {};
    salida[clave] = { total: Number(dato.kills ?? 0), primero: Boolean(dato.first) };
  }
  return salida;
}

function segundos(valor: unknown): number {
  const n = Number(valor);
  if (!Number.isFinite(n)) return 0;
  return n > 10000 ? n / 1000 : n;
}

async function resolverPuuid(): Promise<string | null> {
  if (process.env.LOL_PUUID) return process.env.LOL_PUUID;
  const db = await getDb();
  const coleccion = db.collection(COLECCION_LOL);

  const conTarget = await coleccion.findOne(
    { "metadata.targetPuuid": { $exists: true, $nin: [null, ""] } },
    { projection: { _id: 0, "metadata.targetPuuid": 1 }, sort: { "info.gameCreation": -1 } },
  );
  const target = (conTarget as Record<string, any> | null)?.metadata?.targetPuuid;
  if (target) return String(target);

  const agregado = await coleccion
    .aggregate([
      { $match: { "info.participants.puuid": { $exists: true } } },
      { $unwind: "$info.participants" },
      { $match: { "info.participants.puuid": { $exists: true, $nin: [null, ""] } } },
      { $group: { _id: "$info.participants.puuid", total: { $sum: 1 } } },
      { $sort: { total: -1 } },
      { $limit: 1 },
    ])
    .toArray();

  return agregado.length ? String(agregado[0]._id) : null;
}

function extraerPartida(
  doc: Record<string, any>,
  puuid: string | null,
  riotId: string | null,
): PartidaLol | null {
  const info = doc.info ?? {};
  const participantes: Record<string, any>[] = info.participants ?? [];

  let yo = puuid ? participantes.find((p) => p.puuid === puuid) : undefined;
  if (!yo && riotId) {
    yo = participantes.find((p) => p.riotIdGameName === riotId || p.summonerName === riotId);
  }
  if (!yo) return null;

  const kills = Number(yo.kills ?? 0);
  const deaths = Number(yo.deaths ?? 0);
  const assists = Number(yo.assists ?? 0);
  const teamId = Number(yo.teamId ?? 0);
  const lado = teamId === 100 ? "Azul" : teamId === 200 ? "Rojo" : "Desconocido";

  const companeros: Record<string, string | null> = {};
  const danioCompaneros: Record<string, string | null> = {};
  for (const [clave, codigo] of Object.entries(ROLES)) {
    const companero = participantes.find(
      (p) =>
        Number(p.teamId ?? 0) === teamId &&
        p.puuid !== yo!.puuid &&
        (p.teamPosition || p.individualPosition) === codigo,
    );
    companeros[clave] = companero?.championName ?? null;
    danioCompaneros[clave] = companero?.champion_damage_type ?? null;
  }

  const equipos: Record<string, any>[] = info.teams ?? [];
  const equipo = equipos.find((t) => Number(t.teamId) === teamId);
  const rival = equipos.find((t) => Number(t.teamId) !== teamId);

  return {
    id: doc.metadata?.matchId ?? `${info.gameCreation}`,
    fecha: Number(info.gameCreation ?? 0),
    campeon: yo.championName || "Desconocido",
    tipoDanio: yo.champion_damage_type ?? null,
    rol: yo.teamPosition || yo.individualPosition || yo.role || "UNKNOWN",
    win: Boolean(yo.win),
    lado,
    kills,
    deaths,
    assists,
    kda: (kills + assists) / Math.max(1, deaths),
    danio: Number(yo.totalDamageDealtToChampions ?? 0),
    vision: Number(yo.visionScore ?? 0),
    oro: Number(yo.goldEarned ?? 0),
    cs: Number(yo.totalMinionsKilled ?? 0) + Number(yo.neutralMinionsKilled ?? 0),
    duracion: segundos(info.gameDuration),
    cola: info.queueId ?? null,
    objetivos: leerObjetivos(equipo),
    objetivosRival: leerObjetivos(rival),
    companeros,
    danioCompaneros,
  };
}

async function cargarLol(): Promise<RespuestaLol> {
  const puuid = await resolverPuuid();
  const riotId = process.env.LOL_RIOT_ID || "xAllow";

  const db = await getDb();
  const condiciones: Record<string, unknown>[] = [];
  if (puuid) condiciones.push({ "info.participants.puuid": puuid });
  if (riotId) {
    condiciones.push({ "info.participants.riotIdGameName": riotId });
    condiciones.push({ "info.participants.summonerName": riotId });
  }
  const filtro = condiciones.length ? { $or: condiciones } : {};

  const documentos = await db
    .collection(COLECCION_LOL)
    .find(filtro, {
      projection: {
        _id: 0,
        "metadata.matchId": 1,
        "info.gameCreation": 1,
        "info.gameDuration": 1,
        "info.queueId": 1,
        "info.teams": 1,
        "info.participants": 1,
      },
    })
    .sort({ "info.gameCreation": 1 })
    .toArray();

  const partidas: PartidaLol[] = [];
  for (const doc of documentos as Record<string, any>[]) {
    const fila = extraerPartida(doc, puuid, riotId);
    if (fila && fila.fecha) partidas.push(fila);
  }
  partidas.sort((a, b) => a.fecha - b.fecha);

  return { partidas, puuid, riotId };
}

export async function GET(peticion: Request) {
  if (demoActivo(peticion.url)) {
    return NextResponse.json(lolDemo());
  }
  if (!mongoConfigurado()) {
    return NextResponse.json({ error: "Falta configurar MONGODB_URI en el entorno." }, { status: 503 });
  }
  try {
    const datos = await cachear("lol", 5 * 60 * 1000, cargarLol);
    return NextResponse.json(datos);
  } catch (error) {
    const mensaje = error instanceof Error ? error.message : "Error desconocido";
    return NextResponse.json({ error: `No se pudieron cargar las partidas: ${mensaje}` }, { status: 500 });
  }
}
