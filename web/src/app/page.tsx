"use client";

import { useEffect, useState } from "react";
import { Cabecera, type ClavePestana } from "@/components/cabecera";
import { PestanaPasos } from "@/components/tabs/pasos";
import { PestanaLol } from "@/components/tabs/lol";
import { PestanaRegistro } from "@/components/tabs/registro";
import { PestanaFinanzas } from "@/components/tabs/finanzas";

const CLAVES: ClavePestana[] = ["pasos", "lol", "registro", "finanzas"];

export default function Pagina() {
  const [activa, setActiva] = useState<ClavePestana>("pasos");

  useEffect(() => {
    const desdeHash = window.location.hash.replace("#", "") as ClavePestana;
    if (CLAVES.includes(desdeHash)) {
      setActiva(desdeHash);
      return;
    }
    try {
      const guardada = localStorage.getItem("panel-de-vida:pestana") as ClavePestana | null;
      if (guardada && CLAVES.includes(guardada)) setActiva(guardada);
    } catch {
      /* sin persistencia */
    }
  }, []);

  const cambiar = (clave: ClavePestana) => {
    setActiva(clave);
    try {
      localStorage.setItem("panel-de-vida:pestana", clave);
      window.history.replaceState(null, "", `#${clave}`);
    } catch {
      /* sin persistencia */
    }
  };

  return (
    <div className="min-h-screen">
      <Cabecera activa={activa} onCambiar={cambiar} />
      <main className="mx-auto max-w-[1800px] px-4 py-4 sm:px-6">
        {activa === "pasos" && <PestanaPasos />}
        {activa === "lol" && <PestanaLol />}
        {activa === "registro" && <PestanaRegistro />}
        {activa === "finanzas" && <PestanaFinanzas />}
      </main>
    </div>
  );
}
