import type { Metadata, Viewport } from "next";
import "./globals.css";
import "leaflet/dist/leaflet.css";
import { Proveedores } from "@/components/proveedores";

export const metadata: Metadata = {
  title: "Panel de vida",
  description: "Pasos, League of Legends, registro diario y finanzas en un panel configurable.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f9f9f7" },
    { media: "(prefers-color-scheme: dark)", color: "#0d0d0d" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <body>
        <Proveedores>{children}</Proveedores>
      </body>
    </html>
  );
}
