# Registro para Notion (mientras llega el espacio)

La organización entregará el espacio Notion Business; mientras tanto el registro se lleva aquí,
fechado en git, y se importa tal cual (Notion → Importar → CSV crea una base de datos).

| Archivo | Base de Notion | Página |
| --- | --- | --- |
| `tareas.csv` | Tareas (ID, Tarea, Dueño, Estado, Día, Fecha de cierre, Commit) | 2 · Plan y decisiones |
| `decisiones.csv` | Decisiones (ID, Fecha, Decisión, Alternativas, Por qué, Quién) | 2 · Plan y decisiones |
| `catalogo.csv` | Catálogo de datos (Fuente, URL, Fecha de extracción, Cobertura, Campos, Licencia / condiciones, Transformaciones, SHA-256, Archivo, Filas). Lo genera `python -m src.catalog` desde los datos y el manifest (Levi, B-15): no editar a mano | 3 · Catálogo de datos |
| `pruebas.csv` | Matriz T01–T10 (ID, Prueba, Entrada preparada, Resultado esperado, Arregla, Observado, Evidencia, Corrección). Cristian la actualiza en cada corrida (C-08); una prueba que falla no se borra: se anota la corrección y su commit | 6 · Pruebas y métricas |
| `riesgos-y-etica.md` | — (texto) | 7 · Riesgos y ética: la página completa (C-07), que integra el aporte de Levi |
| `riesgos-datos.md` | — (texto) | 7 · Riesgos y ética: aporte de datos de Levi (B-16), con las cifras de sesgo y cobertura |

Reglas: una decisión nueva es una fila nueva con su fecha; si cambia una, no se borra: se marca
"Reemplazada por ADR-0XX". Cada tarea cerrada lleva su commit. Dueño: Cristian (C-02).
Estados de Tareas: Por hacer, En curso, Bloqueada, Hecha.
