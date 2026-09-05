const nf0 = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0, useGrouping: true });
const nf1 = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nfEur = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export const miles = (n: number) => nf0.format(Math.round(n || 0));
/** Numeros cortos para los ejes: sin unidades ni palabras. */
export const ejeNumero = (n: number) => (Math.abs(n) >= 10000 ? compacto(n) : nf0.format(Math.round(n || 0)));
export const dec1 = (n: number) => nf1.format(n || 0);
export const dec2 = (n: number) => nf2.format(n || 0);
export const euros = (n: number) => nfEur.format(n || 0);
export const pct = (n: number, decimales = 1) =>
  `${(decimales === 0 ? nf0 : decimales === 2 ? nf2 : nf1).format(n || 0)}%`;

export function compacto(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${dec1(n / 1_000_000)}M`;
  if (abs >= 1_000) return `${dec1(n / 1_000)}k`;
  return miles(n);
}
