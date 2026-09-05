# Panel de vida

Panel personal de pasos, League of Legends, registro diario y finanzas. Sustituye al
dashboard de Streamlit de la carpeta `pasos/` por una aplicación Next.js que se puede
desplegar en Vercel o Netlify.

Qué cambia respecto a Streamlit:

- **Paneles móviles**: cada tarjeta se arrastra por su cabecera y se redimensiona por la
  esquina inferior derecha. La disposición se guarda en el navegador por pestaña.
- **Más filtros**: rango de fechas con atajos, meses, días de la semana, franja horaria,
  rol, campeón, cola, lado, resultado, categoría de gasto, búsqueda por concepto e
  importes o duraciones mínimas.
- **Tema claro y oscuro** con conmutador de tres estados (claro, oscuro, sistema).
- **Estilo minimalista**: una sola familia tipográfica, líneas finas y paleta validada
  para daltonismo en ambos modos.

## Puesta en marcha

```bash
cd web
npm install
cp .env.example .env.local   # rellena las variables
npm run dev
```

La aplicación queda en `http://localhost:3000`.

### Modo demo

Sin credenciales, `http://localhost:3000/?demo=1` genera datos sintéticos para las cuatro
pestañas. Sirve para revisar el diseño o para una vista previa del despliegue. También se
activa de forma global con `DEMO_DATOS=1`.

## Variables de entorno

| Variable | Para qué sirve |
| --- | --- |
| `MONGODB_URI` | Conexión a MongoDB. Necesaria para pasos y League of Legends. |
| `DB_NAME` | Base de datos. Por defecto `lol`. |
| `COLLECTION_NAME` | Colección de pasos. Por defecto `pasos`. |
| `LOL_COLLECTION_NAME` | Colección de partidas. Por defecto `partidas`. |
| `LOL_PUUID` | Opcional. Si falta, se deduce de los propios documentos. |
| `LOL_RIOT_ID` | Nombre de invocador de respaldo. Por defecto `xAllow`. |
| `GOOGLE_SHEET_CSV_URL` | Hoja publicada como CSV con el registro diario. |
| `BANK_CSV_URL` | Hoja publicada como CSV con los movimientos bancarios. |
| `DEMO_DATOS` | `1` para servir siempre datos de ejemplo. |

Son las mismas variables que ya usaba el panel de Python, así que un `.env` existente vale
tal cual.

## Despliegue

### Vercel (recomendado)

1. Importa el repositorio y pon `web` como *Root Directory*.
2. Framework: Next.js. No hace falta tocar los comandos de build.
3. Añade las variables de entorno anteriores en *Settings → Environment Variables*.

### Netlify

1. *Base directory*: `web`. *Build command*: `npm run build`. *Publish directory*: `.next`.
2. El archivo `netlify.toml` ya declara `@netlify/plugin-nextjs`, que Netlify instala solo.
3. Añade las mismas variables de entorno.

Las rutas de datos son funciones de servidor, así que la conexión a MongoDB nunca llega al
navegador. Un despliegue estático puro no funcionaría.

## Cómo está organizado

```
src/app/api/*       Rutas de datos: leen MongoDB y las hojas CSV y devuelven filas compactas
src/components/     Tablero arrastrable, controles de filtro, gráficas y pestañas
src/lib/            Paleta, formatos, fechas, parseo CSV, categorías de gasto, caché
```

Cada ruta cachea su resultado cinco minutos en memoria del proceso. El filtrado ocurre en
el navegador, de modo que mover un control no dispara ninguna petición.

### Añadir un panel

En el archivo de la pestaña, añade una entrada al array `paneles` con `id`, `titulo`,
`base` (posición y tamaño en una rejilla de doce columnas) y `contenido`. Sube el número
de `version` que recibe `Tablero` para que las disposiciones guardadas se regeneren.

### Categorías de gasto

Las reglas están en `src/lib/categorias.ts`, en una única lista de palabras clave.
