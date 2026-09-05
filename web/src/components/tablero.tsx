"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Responsive, WidthProvider, type Layout, type Layouts } from "react-grid-layout";
import { Eye, EyeOff, GripVertical, Lock, LockOpen, RotateCcw, SlidersHorizontal } from "lucide-react";

const Rejilla = WidthProvider(Responsive);

export type DefinicionPanel = {
  id: string;
  titulo: string;
  ayuda?: string;
  /** Posicion y tamano por defecto en la rejilla de 12 columnas. */
  base: { x: number; y: number; w: number; h: number; minW?: number; minH?: number };
  contenido: React.ReactNode;
};

type EstadoGuardado = { version: number; layouts: Layouts; ocultos: string[] };

const COLUMNAS = { lg: 12, md: 8, sm: 4, xs: 2 };
const PUNTOS = { lg: 1200, md: 900, sm: 640, xs: 0 };
const ALTO_FILA = 42;

function layoutsPorDefecto(paneles: DefinicionPanel[]): Layouts {
  const lg: Layout[] = paneles.map((p) => ({
    i: p.id,
    x: p.base.x,
    y: p.base.y,
    w: p.base.w,
    h: p.base.h,
    minW: p.base.minW ?? 2,
    minH: p.base.minH ?? 3,
  }));
  return { lg };
}

export function Tablero({
  claveAlmacen,
  version,
  paneles,
  filtros,
}: {
  claveAlmacen: string;
  version: number;
  paneles: DefinicionPanel[];
  filtros?: React.ReactNode;
}) {
  const clave = `panel-de-vida:${claveAlmacen}`;
  const porDefecto = useMemo(() => layoutsPorDefecto(paneles), [paneles]);

  const [montado, setMontado] = useState(false);
  const [layouts, setLayouts] = useState<Layouts>(porDefecto);
  const [ocultos, setOcultos] = useState<string[]>([]);
  const [bloqueado, setBloqueado] = useState(false);
  const [menuAbierto, setMenuAbierto] = useState(false);
  const menu = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMontado(true);
    try {
      const crudo = localStorage.getItem(clave);
      if (crudo) {
        const guardado = JSON.parse(crudo) as EstadoGuardado;
        if (guardado.version === version && guardado.layouts) {
          setLayouts(guardado.layouts);
          setOcultos(guardado.ocultos ?? []);
        }
      }
      setBloqueado(localStorage.getItem("panel-de-vida:bloqueado") === "1");
    } catch {
      /* almacenamiento no disponible: se usa el layout por defecto */
    }
  }, [clave, version]);

  const guardar = useCallback(
    (nuevos: Layouts, nuevosOcultos: string[]) => {
      try {
        const estado: EstadoGuardado = { version, layouts: nuevos, ocultos: nuevosOcultos };
        localStorage.setItem(clave, JSON.stringify(estado));
      } catch {
        /* sin persistencia */
      }
    },
    [clave, version],
  );

  useEffect(() => {
    if (!menuAbierto) return;
    const fuera = (e: MouseEvent) => {
      if (menu.current && !menu.current.contains(e.target as Node)) setMenuAbierto(false);
    };
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [menuAbierto]);

  const alCambiarLayout = (_actual: Layout[], todos: Layouts) => {
    setLayouts(todos);
    guardar(todos, ocultos);
  };

  const alternarPanel = (id: string) => {
    const siguientes = ocultos.includes(id) ? ocultos.filter((o) => o !== id) : [...ocultos, id];
    setOcultos(siguientes);
    guardar(layouts, siguientes);
  };

  const restablecer = () => {
    setLayouts(porDefecto);
    setOcultos([]);
    try {
      localStorage.removeItem(clave);
    } catch {
      /* sin persistencia */
    }
  };

  const alternarBloqueo = () => {
    const siguiente = !bloqueado;
    setBloqueado(siguiente);
    try {
      localStorage.setItem("panel-de-vida:bloqueado", siguiente ? "1" : "0");
    } catch {
      /* sin persistencia */
    }
  };

  const visibles = paneles.filter((p) => !ocultos.includes(p.id));

  // Un panel nuevo (o ausente del layout guardado) recibe su posicion por defecto.
  const layoutsCompletos: Layouts = useMemo(() => {
    const salida: Layouts = {};
    const claves = new Set([...Object.keys(layouts), "lg"]);
    for (const breakpoint of claves) {
      const previo = layouts[breakpoint] ?? porDefecto.lg;
      const presentes = new Set(previo.map((item) => item.i));
      const faltantes = paneles
        .filter((p) => !presentes.has(p.id))
        .map((p) => ({
          i: p.id,
          x: p.base.x,
          y: p.base.y,
          w: p.base.w,
          h: p.base.h,
          minW: p.base.minW ?? 2,
          minH: p.base.minH ?? 3,
        }));
      salida[breakpoint] = [...previo, ...faltantes];
    }
    return salida;
  }, [layouts, paneles, porDefecto]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">{filtros}</div>

        <div className="flex items-center gap-2">
          <div className="relative" ref={menu}>
            <button
              type="button"
              className="control flex items-center gap-1.5 px-2.5 text-xs font-medium hover:bg-[var(--superficie-2)]"
              onClick={() => setMenuAbierto((v) => !v)}
              style={{ color: "var(--tinta-2)" }}
            >
              <SlidersHorizontal size={13} />
              Paneles
              <span className="tabular" style={{ color: "var(--tinta-3)" }}>
                {visibles.length}/{paneles.length}
              </span>
            </button>
            {menuAbierto && (
              <div
                className="scroll-fino absolute right-0 z-50 mt-1 max-h-80 w-64 overflow-auto rounded-lg border p-1"
                style={{ background: "var(--superficie)", boxShadow: "0 8px 24px rgba(0,0,0,0.16)" }}
              >
                {paneles.map((p) => {
                  const visible = !ocultos.includes(p.id);
                  return (
                    <button
                      key={p.id}
                      type="button"
                      className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-[var(--superficie-2)]"
                      onClick={() => alternarPanel(p.id)}
                      style={{ color: visible ? "var(--tinta)" : "var(--tinta-3)" }}
                    >
                      {visible ? <Eye size={13} /> : <EyeOff size={13} />}
                      <span className="truncate">{p.titulo}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <button
            type="button"
            className="control flex items-center gap-1.5 px-2.5 text-xs font-medium hover:bg-[var(--superficie-2)]"
            onClick={alternarBloqueo}
            title={bloqueado ? "Desbloquear para mover paneles" : "Bloquear posiciones"}
            style={{ color: "var(--tinta-2)" }}
          >
            {bloqueado ? <Lock size={13} /> : <LockOpen size={13} />}
            {bloqueado ? "Bloqueado" : "Editable"}
          </button>

          <button
            type="button"
            className="control flex items-center gap-1.5 px-2.5 text-xs font-medium hover:bg-[var(--superficie-2)]"
            onClick={restablecer}
            title="Volver a la disposicion original"
            style={{ color: "var(--tinta-2)" }}
          >
            <RotateCcw size={13} />
            Restablecer
          </button>
        </div>
      </div>

      {montado ? (
        <Rejilla
          className={bloqueado ? "tablero-bloqueado" : undefined}
          layouts={layoutsCompletos}
          breakpoints={PUNTOS}
          cols={COLUMNAS}
          rowHeight={ALTO_FILA}
          margin={[14, 14]}
          containerPadding={[0, 0]}
          isDraggable={!bloqueado}
          isResizable={!bloqueado}
          draggableHandle=".asa-arrastre"
          onLayoutChange={alCambiarLayout}
          measureBeforeMount={false}
          useCSSTransforms
        >
          {visibles.map((p) => (
            <div key={p.id}>
              <PanelTarjeta titulo={p.titulo} ayuda={p.ayuda} bloqueado={bloqueado}>
                {p.contenido}
              </PanelTarjeta>
            </div>
          ))}
        </Rejilla>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {visibles.slice(0, 4).map((p) => (
            <div key={p.id} className="tarjeta h-48 animate-pulse" />
          ))}
        </div>
      )}
    </div>
  );
}

function PanelTarjeta({
  titulo,
  ayuda,
  bloqueado,
  children,
}: {
  titulo: string;
  ayuda?: string;
  bloqueado: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="tarjeta flex h-full flex-col overflow-hidden">
      <header
        className={`flex shrink-0 items-center gap-1.5 border-b px-3 py-2 ${bloqueado ? "" : "asa-arrastre"}`}
      >
        {!bloqueado && <GripVertical size={13} style={{ color: "var(--tinta-3)" }} />}
        <h3 className="truncate text-[13px] font-semibold" style={{ color: "var(--tinta)" }}>
          {titulo}
        </h3>
        {ayuda && (
          <span className="ml-auto truncate text-[11px]" style={{ color: "var(--tinta-3)" }}>
            {ayuda}
          </span>
        )}
      </header>
      <div className="min-h-0 flex-1 p-3">{children}</div>
    </section>
  );
}
