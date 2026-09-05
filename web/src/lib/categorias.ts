/** Reglas de categorizacion de movimientos bancarios (editables en un solo sitio). */
export const REGLAS: { categoria: string; claves: string[] }[] = [
  { categoria: "Bizum", claves: ["BIZUM"] },
  {
    categoria: "Alimentación (Súper)",
    claves: ["MERCADONA", "CARREFOUR", "CRF EXP", "BAZAR HONG YOU", "EXPRESS TAM", "EXPRESS TAMAYO", "SUPERMERCADO", "ALIMENTACION"],
  },
  {
    categoria: "Restauración / Comida",
    claves: ["DOMINOS PIZZA", "PIZZA", "MCDONALDS", "UBER", "EATS", "KIBAB", "DURUM", "CAFE", "CAFETERIA", "ASADOR", "RESTAURANTE", "CREMOLATTA", "BAR", "QUINTO A", "EL CENTIMO DE REGALO", "MADRE DE DIOS"],
  },
  { categoria: "Compras / Amazon", claves: ["AMAZON", "AMZN"] },
  { categoria: "Formación / Estudios", claves: ["AUTOESCUELA", "LIBRO", "LIBRARY", "AGAPEA"] },
  {
    categoria: "Transferencias Familia / Cuentas",
    claves: ["PAPA", "VICENTE", "ALVARO LUQUE", "TRANSF. ALVARO", "CONDONACION CUOTA MANT."],
  },
  { categoria: "Telecomunicaciones / Wifi", claves: ["MOVISTAR", "TELEFONICA", "JAZZTEL", "WIFI"] },
  { categoria: "Nómina / Ingresos del Estado", claves: ["TESORO PUBLICO"] },
  { categoria: "Comisiones / Intereses", claves: ["COMIS.TARJETA", "LIQ. DE INT", "INTERESES"] },
  { categoria: "Transporte / Viajes", claves: ["ALSA", "METRO", "BLABLACAR", "PAYPAL *BLABLACAR", "VIAJE"] },
  { categoria: "Cuidado Personal", claves: ["PELUQUERIA"] },
  { categoria: "Hogar / Suministros", claves: ["BOMBONA", "GIBRALFARO GAS", "LUZ", "AGUA", "LLEIDA.NET"] },
  { categoria: "Ocio / Gaming", claves: ["STEAM", "EPIC", "MICROSOFT STOR", "GIANTSGAMIN", "VERSE", "GOOGLE STATSFM"] },
];

export function categorizar(concepto: string): string {
  const texto = String(concepto ?? "").toUpperCase();
  for (const regla of REGLAS) {
    if (regla.claves.some((clave) => texto.includes(clave))) return regla.categoria;
  }
  return "Otros";
}
