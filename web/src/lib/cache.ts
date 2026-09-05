type Entrada = { expira: number; valor: unknown };

const almacen = new Map<string, Entrada>();

/** Cache en memoria del proceso: evita golpear Mongo o Sheets en cada peticion. */
export async function cachear<T>(clave: string, ttlMs: number, fn: () => Promise<T>): Promise<T> {
  const ahora = Date.now();
  const previo = almacen.get(clave);
  if (previo && previo.expira > ahora) {
    return previo.valor as T;
  }
  const valor = await fn();
  almacen.set(clave, { expira: ahora + ttlMs, valor });
  return valor;
}

export function invalidarCache(clave?: string) {
  if (clave) almacen.delete(clave);
  else almacen.clear();
}
