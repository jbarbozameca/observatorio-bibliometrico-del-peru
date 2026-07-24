# Observatorio Bibliométrico del Perú · Scopus 1996–2026

Dashboard web **estático e interactivo** para explorar la producción científica del Perú
indexada en Scopus. Permite **buscar por investigador o institución**, **seleccionar varios**
y **compararlos** mediante tablas y figuras interactivas (Plotly), tomando como referencia
el promedio nacional.

> Fuente: export de Scopus vía SciVal («Publications in Peru 1996 – >2026», datos al 15 de julio de 2026,
> export del 24 de julio de 2026). 98 674 publicaciones (1996–2026; 2026 parcial) ·
> 33 885 investigadores con ≥ 5 publicaciones · 129 instituciones peruanas (allow-list curada).

---

## ✨ Funcionalidades

- 🔎 **Búsqueda** instantánea por nombre (investigador o institución).
- 🏆 **Top 10 nacional y por institución** con selector de métrica (publicaciones, citas, FWCI, % Top 10 %, % Q1, % OA, % internacional). El top por institución usa solo la producción del investigador con esa afiliación (mín. 5 pubs; se excluyen publicaciones con > 100 autores).
- 📖 **Apartado de interpretación de métricas** (institucionales y de investigador), con valores de referencia nacionales y precauciones de lectura.
- 🏆 **Ranking nacional** ordenable (publicaciones, citas, FWCI, % Top 10 %, % Q1, % colaboración internacional).
- ⚖️ **Comparación de hasta 10 entidades** en simultáneo:
  - Tabla comparativa con código de color frente a la referencia nacional.
  - Publicaciones por año (barras agrupadas).
  - Indicadores de impacto y apertura (% Top 10 %, % Q1, % acceso abierto, % colaboración internacional).
  - FWCI medio (con línea del promedio mundial = 1,0).
  - Volumen vs. citas por publicación (dispersión).
- 📱 Diseño responsive; **100 % en el navegador**, sin servidor ni backend.

## 📂 Estructura

```
dashboard/
├── index.html        # Aplicación (HTML + CSS + JS)
├── data/
│   └── data.js        # Datos agregados (generado por build_data.R)
├── build_data.py      # Script Python que produce data.js desde el CSV de Scopus (reemplaza a build_data.R)
└── README.md
```

## 🚀 Publicar en GitHub Pages

1. Crea un repositorio en GitHub y sube el contenido de la carpeta `dashboard/`
   (puedes subir solo esta carpeta como raíz del repositorio).
   ```bash
   git init
   git add .
   git commit -m "Observatorio bibliométrico Perú"
   git branch -M main
   git remote add origin https://github.com/<usuario>/<repo>.git
   git push -u origin main
   ```
2. En GitHub: **Settings → Pages → Build and deployment → Source: _Deploy from a branch_**,
   rama `main`, carpeta `/ (root)`.
3. En 1–2 minutos estará disponible en `https://<usuario>.github.io/<repo>/`.

> No requiere build ni dependencias: GitHub Pages sirve `index.html` directamente.
> Plotly se carga desde CDN.

## 💻 Ejecutar en local

Por seguridad del navegador, ábrelo con un pequeño servidor (no con doble clic):

```bash
cd dashboard
python3 -m http.server 8777
# abre http://localhost:8777
```

## 🔄 Regenerar los datos

Si actualizas el CSV de Scopus, regenera `data/data.js`:

```bash
# Requiere Python 3 (solo librería estándar). El CSV se referencia como pubs.csv
python3 build_data.py
```

Edita en `build_data.py` los umbrales `MIN_PUBS_AUTHOR` / `MIN_PUBS_INST` / `MIN_PUBS_PAIR`
para incluir más o menos entidades, y la allow-list `PERU` para añadir instituciones.

## 📐 Notas metodológicas

- **FWCI** (Field-Weighted Citation Impact): citas observadas / esperadas según campo, año y
  tipo de documento. 1,0 = promedio mundial.
- **% Top 10 %**: porcentaje de trabajos en el 10 % más citado a escala mundial.
- **Cuartil (Q1)**: derivado del percentil de CiteScore del año de publicación. ⚠️ En el export
  de SciVal el percentil está **invertido** (1 = top 1 %), por lo que Q1 = percentil ≤ 25.
  (Versiones anteriores del observatorio usaban ≥ 75 sobre este mismo campo, lo que contaba el
  cuartil inferior; corregido en la edición del 24-jul-2026.)
- **Colaboración internacional**: publicaciones con autores de ≥ 2 países.
- El conteo por entidad refleja **apariciones en publicaciones con afiliación peruana**; el
  ranking de investigadores usa el **Scopus Author ID** como clave de desambiguación.
- Las métricas de citación de 2024–2026 están sujetas a la ventana de citación y subestiman
  el impacto de las cohortes recientes. **2026 es un año parcial** (corte 15-jul-2026).
- En el **Top 10 por institución**, la pertenencia investigador–institución se estima por
  coaparición en publicaciones, excluyendo las de > 100 autores (hiperautoría); las métricas del
  investigador se calculan solo sobre su producción con esa afiliación (mín. 5 publicaciones).

---

*Generado con Python y Plotly.js. Última actualización: 24 de julio de 2026.*
