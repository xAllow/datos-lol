export type DiaPasos = { f: string; v: number; imp: boolean };

export type RespuestaPasos = {
  dias: DiaPasos[];
  meta: {
    rellenados: number;
    inf: number;
    sup: number;
    desde: string | null;
    hasta: string | null;
  };
};

export type ClaveObjetivo =
  | "sangre"
  | "dragon"
  | "grubs"
  | "heraldo"
  | "torre"
  | "baron"
  | "atakhan"
  | "inhibidor";

/** Objetivos de un equipo: cuantos consiguio y si se llevo el primero. */
export type ObjetivosLol = Record<ClaveObjetivo, { total: number; primero: boolean }>;

export type PartidaLol = {
  id: string;
  fecha: number;
  campeon: string;
  tipoDanio: string | null;
  rol: string;
  win: boolean;
  lado: "Azul" | "Rojo" | "Desconocido";
  kills: number;
  deaths: number;
  assists: number;
  kda: number;
  danio: number;
  vision: number;
  oro: number;
  cs: number;
  duracion: number;
  cola: number | null;
  objetivos: ObjetivosLol;
  objetivosRival: ObjetivosLol;
  companeros: Record<string, string | null>;
  danioCompaneros: Record<string, string | null>;
};

export type RespuestaLol = {
  partidas: PartidaLol[];
  puuid: string | null;
  riotId: string | null;
};

export type Registro = { t: number; dia: string; minutos: number };

export type RespuestaRegistro = { registros: Registro[] };

export type Movimiento = {
  dia: string;
  t: number;
  concepto: string;
  categoria: string;
  importe: number;
  saldo: number;
};

export type RespuestaFinanzas = { movimientos: Movimiento[] };

export type TipoActividad = "RUNNING" | "WALKING" | "SWIMMING" | "TRAINING";

export type ZonasFc = { z1: number; z2: number; z3: number; z4: number; z5: number };

export type ZonasRitmo = {
  rapido: number;
  medio: number;
  trote: number;
  caminando: number;
  parado: number;
};

export type Actividad = {
  id: string;
  tipo: TipoActividad;
  fecha: number;
  duracionActiva: number;
  duracionTotal: number;
  distancia: number;
  calorias: number;
  pasos: number;
  fcMedia: number;
  fcMaxima: number;
  velMedia: number;
  velMaxima: number;
  elevacion: number | null;
  mejor400: number | null;
  mejor1km: number | null;
  mejor2km: number | null;
  mejor5km: number | null;
  mejor10km: number | null;
  zonasFc: ZonasFc | null;
  zonasRitmo: ZonasRitmo | null;
  traza: [number, number][] | null;
  fuente: string | null;
};

export type RespuestaActividades = { actividades: Actividad[] };
