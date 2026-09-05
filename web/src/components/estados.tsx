"use client";

import { AlertCircle, RefreshCw } from "lucide-react";

export function Cargando({ mensaje = "Cargando datos..." }: { mensaje?: string }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="tarjeta h-20 animate-pulse" />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="tarjeta h-56 animate-pulse" />
        ))}
      </div>
      <p className="text-center text-[12px]" style={{ color: "var(--tinta-3)" }}>
        {mensaje}
      </p>
    </div>
  );
}

export function ErrorCarga({ mensaje, onReintentar }: { mensaje: string; onReintentar: () => void }) {
  return (
    <div className="tarjeta flex flex-col items-start gap-3 p-5">
      <div className="flex items-center gap-2">
        <AlertCircle size={16} style={{ color: "var(--critico)" }} />
        <h2 className="text-sm font-semibold">No se pudieron cargar los datos</h2>
      </div>
      <p className="text-[13px]" style={{ color: "var(--tinta-2)" }}>
        {mensaje}
      </p>
      <button
        type="button"
        className="control flex items-center gap-1.5 px-3 text-[13px] font-medium hover:bg-[var(--superficie-2)]"
        onClick={onReintentar}
      >
        <RefreshCw size={13} /> Reintentar
      </button>
    </div>
  );
}

export function Vacio({ mensaje }: { mensaje: string }) {
  return (
    <div className="tarjeta p-5 text-[13px]" style={{ color: "var(--tinta-2)" }}>
      {mensaje}
    </div>
  );
}
