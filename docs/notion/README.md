# Documentación del proyecto · las 8 páginas

La organización pidió el 8 oct un espacio del equipo en Notion (ADR-048, que reemplaza a ADR-047 en lo que toca
a Notion). Está en el workspace del hackIAthon, con tres páginas:
[documentación técnica](https://app.notion.com/p/3f36d0f0b114817ba1a2cf059af5b356),
[documentación funcional](https://app.notion.com/p/3f36d0f0b11481feb68dc27af313d3f9) y
[presentación del Pitch Day](https://app.notion.com/p/3f36d0f0b114812d93a9d2b3f2163f56), más un
[registro del evento](https://app.notion.com/p/3f46d0f0b11481cd880bda2b5bef07d2) con el plan, las decisiones, el catálogo,
los casos, las pruebas y la bitácora de PRs, importados el 08/10/2026 desde este repositorio. Sus imágenes están en
[`img/`](img/) y sus piezas interactivas en [`embeds/`](embeds/). Las 8 páginas del reto siguen aquí, en el
repositorio público, como fuente: GitHub las muestra sin cuenta y cada cambio queda fechado en git.

| # | Página | Archivos |
| --- | --- | --- |
| 1 | Inicio del reto | [`inicio.md`](inicio.md) |
| 2 | Plan y decisiones | [`tareas.csv`](tareas.csv) · [`decisiones.csv`](decisiones.csv) |
| 3 | Catálogo de datos | [`catalogo.csv`](catalogo.csv) |
| 4 | Diseño de solución | [`diseno.md`](diseno.md) |
| 5 | Casos y evidencias | [`casos.md`](casos.md) (generada con `python tools/casos_md.py`) |
| 6 | Pruebas y métricas | [`pruebas.csv`](pruebas.csv) · [`precision-at-5.md`](precision-at-5.md) · [`valor-operativo.md`](valor-operativo.md) · [`../../outputs/reports/`](../../outputs/reports/) |
| 7 | Riesgos y ética | [`riesgos-y-etica.md`](riesgos-y-etica.md) · [`riesgos-datos.md`](riesgos-datos.md) |
| 8 | Presentación al jurado | [`presentacion.md`](presentacion.md) |

## Detalle de cada archivo

| Archivo | Contenido | Página |
| --- | --- | --- |
| `inicio.md` | — (texto) | 1 · Inicio del reto: equipo, problema, usuario, alcance, criterios de éxito y enlaces (José) |
| `diseno.md` | — (texto) | 4 · Diseño de solución: arquitectura, datos, puntaje, modelos, prompts y límites (José) |
| `casos.md` | Casos generados desde `outputs/fichas.jsonl` + `outputs/revisiones.jsonl`: no editar a mano | 5 · Casos y evidencias |
| `tareas.csv` | Tareas (ID, Tarea, Dueño, Estado, Día, Fecha de cierre, Commit) | 2 · Plan y decisiones |
| `decisiones.csv` | Decisiones (ID, Fecha, Decisión, Alternativas, Por qué, Quién) | 2 · Plan y decisiones |
| `catalogo.csv` | Catálogo de datos (Fuente, URL, Fecha de extracción, Cobertura, Campos, Licencia / condiciones, Transformaciones, SHA-256, Archivo, Filas). Lo genera `python -m src.catalog` desde los datos y el manifest (Levi, B-15): no editar a mano | 3 · Catálogo de datos |
| `pruebas.csv` | Matriz T01–T10 (ID, Prueba, Entrada preparada, Resultado esperado, Arregla, Observado, Evidencia, Corrección). Cristian la actualiza en cada corrida (C-08); una prueba que falla no se borra: se anota la corrección y su commit | 6 · Pruebas y métricas |
| `precision-at-5.md` | — (texto) | 6 · Pruebas y métricas: Precision@5 exploratoria (C-09), debajo de la matriz |
| `valor-operativo.md` | — (texto) | 6 · Pruebas y métricas: valor operativo como hipótesis de valor (C-17) |
| `riesgos-y-etica.md` | — (texto) | 7 · Riesgos y ética: la página completa (C-07), que integra el aporte de Levi |
| `riesgos-datos.md` | — (texto) | 7 · Riesgos y ética: aporte de datos de Levi (B-16), con las cifras de sesgo y cobertura |
| `presentacion.md` | — (texto) | 8 · Presentación al jurado: guion del pitch de 10 min con dueños y tiempos (C-11) |

Reglas: una decisión nueva es una fila nueva con su fecha; si cambia una, no se borra: se marca
"Reemplazada por ADR-0XX". Cada tarea cerrada lleva su commit. Dueño: Cristian (C-02).
Estados de Tareas: Por hacer, En curso, Bloqueada, Hecha.
