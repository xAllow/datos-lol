export const MESES_ES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

export const MESES_CORTOS = [
  "Ene", "Feb", "Mar", "Abr", "May", "Jun",
  "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
];

/** Lunes = 0 ... Domingo = 6 */
export const DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
export const DIAS_CORTOS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

/** Indice 0..6 con el lunes como primer dia. */
export function indiceDiaSemana(d: Date): number {
  return (d.getDay() + 6) % 7;
}

/** Clave YYYY-MM-DD en horario local. */
export function claveDia(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

export function desdeClaveDia(clave: string): Date {
  const [y, m, d] = clave.split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

export function sumarDias(d: Date, dias: number): Date {
  const copia = new Date(d.getTime());
  copia.setDate(copia.getDate() + dias);
  return copia;
}

export function formatoCorto(clave: string): string {
  const d = desdeClaveDia(clave);
  return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`;
}

export function formatoMes(claveMes: string): string {
  const [y, m] = claveMes.split("-").map(Number);
  return `${MESES_CORTOS[(m || 1) - 1]} ${String(y).slice(2)}`;
}

/** "Septiembre 2026" a partir de una clave YYYY-MM. */
export function formatoMesLargo(claveMes: string): string {
  const [y, m] = claveMes.split("-").map(Number);
  return `${MESES_ES[(m || 1) - 1]} ${y}`;
}

/** Clave YYYY-MM del mes actual en horario local. */
export function claveMesActual(): string {
  return claveDia(new Date()).slice(0, 7);
}

/** Desplaza una clave YYYY-MM un numero de meses (negativo hacia atras). */
export function sumarMeses(claveMes: string, n: number): string {
  const [y, m] = claveMes.split("-").map(Number);
  const fecha = new Date(y, (m || 1) - 1 + n, 1);
  return `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, "0")}`;
}

/** Numero de dias que tiene un mes YYYY-MM. */
export function diasEnMes(claveMes: string): number {
  const [y, m] = claveMes.split("-").map(Number);
  return new Date(y, m || 1, 0).getDate();
}

/** Semana ISO de una fecha. */
export function semanaIso(d: Date): { semana: number; anio: number } {
  const fecha = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const diaNum = fecha.getUTCDay() || 7;
  fecha.setUTCDate(fecha.getUTCDate() + 4 - diaNum);
  const inicioAnio = new Date(Date.UTC(fecha.getUTCFullYear(), 0, 1));
  const semana = Math.ceil(((fecha.getTime() - inicioAnio.getTime()) / 86400000 + 1) / 7);
  return { semana, anio: fecha.getUTCFullYear() };
}

/** Parseo tolerante de las fechas mixtas que llegan desde las hojas de calculo. */
export function parsearFechaFlexible(valor: string): Date | null {
  const texto = String(valor ?? "").trim();
  if (!texto) return null;

  const iso = texto.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/);
  if (iso) {
    return new Date(
      Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]),
      Number(iso[4] || 0), Number(iso[5] || 0), Number(iso[6] || 0),
    );
  }

  const euro = texto.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?:[T ](\d{1,2}):(\d{2})(?::(\d{2}))?)?/);
  if (euro) {
    return new Date(
      Number(euro[3]), Number(euro[2]) - 1, Number(euro[1]),
      Number(euro[4] || 0), Number(euro[5] || 0), Number(euro[6] || 0),
    );
  }

  const fallback = new Date(texto);
  return Number.isNaN(fallback.getTime()) ? null : fallback;
}
