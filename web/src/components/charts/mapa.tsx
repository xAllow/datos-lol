"use client";

import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";
import { SinDatos } from "./base";

export type RutaMapa = { puntos: [number, number][]; color: string };

function AutoEncuadre({ bounds }: { bounds: LatLngBoundsExpression }) {
  const mapa = useMap();
  useEffect(() => {
    mapa.fitBounds(bounds, { padding: [16, 16] });
  }, [mapa, bounds]);
  return null;
}

/**
 * Mapa real (OpenStreetMap) para una o varias rutas superpuestas.
 * interactivo=false desactiva arrastre/zoom para usarlo como miniatura sin que
 * secuestre el scroll de la pagina; la atribucion se mantiene siempre visible.
 */
export function MapaRuta({
  rutas,
  interactivo = true,
}: {
  rutas: RutaMapa[];
  interactivo?: boolean;
}) {
  const conPuntos = useMemo(() => rutas.filter((r) => r.puntos.length > 1), [rutas]);

  const bounds = useMemo<LatLngBoundsExpression | null>(() => {
    const todos = conPuntos.flatMap((r) => r.puntos);
    if (!todos.length) return null;
    const lats = todos.map((p) => p[0]);
    const lons = todos.map((p) => p[1]);
    return [
      [Math.min(...lats), Math.min(...lons)],
      [Math.max(...lats), Math.max(...lons)],
    ];
  }, [conPuntos]);

  if (!bounds) return <SinDatos mensaje="Sin traza GPS" />;

  return (
    <MapContainer
      bounds={bounds}
      style={{ height: "100%", width: "100%", borderRadius: 8 }}
      zoomControl={interactivo}
      dragging={interactivo}
      scrollWheelZoom={false}
      doubleClickZoom={interactivo}
      boxZoom={interactivo}
      keyboard={interactivo}
      touchZoom={interactivo}
      attributionControl={true}
    >
      <AutoEncuadre bounds={bounds} />
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />
      {conPuntos.map((r, i) => (
        <Polyline key={`linea-${i}`} positions={r.puntos} pathOptions={{ color: r.color, weight: 3 }} />
      ))}
      {conPuntos.map((r, i) => (
        <CircleMarker
          key={`inicio-${i}`}
          center={r.puntos[0]}
          radius={4}
          pathOptions={{ color: "#fff", fillColor: r.color, fillOpacity: 1, weight: 2 }}
        />
      ))}
    </MapContainer>
  );
}
