# Registro para Notion (mientras llega el espacio)

La organización entregará el espacio Notion Business; mientras tanto el registro se lleva aquí,
fechado en git, y se importa tal cual (Notion → Importar → CSV crea una base de datos).

| Archivo | Base de Notion | Página |
| --- | --- | --- |
| `tareas.csv` | Tareas (ID, Tarea, Dueño, Estado, Día, Fecha de cierre, Commit) | 2 · Plan y decisiones |
| `decisiones.csv` | Decisiones (ID, Fecha, Decisión, Alternativas, Por qué, Quién) | 2 · Plan y decisiones |

Reglas: una decisión nueva es una fila nueva con su fecha; si cambia una, no se borra: se marca
"Reemplazada por ADR-0XX". Cada tarea cerrada lleva su commit. Dueño: Cristian (C-02).
Estados de Tareas: Por hacer, En curso, Bloqueada, Hecha.
