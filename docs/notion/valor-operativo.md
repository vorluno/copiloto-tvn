# Valor operativo · hipótesis de valor (C-17)

Para la página **6 · Pruebas y métricas** de Notion y el bloque 5 del pitch.

## Conclusión

**No hay una medición válida del ahorro de tiempo.** El valor operativo se presenta como
**hipótesis de valor**: las pruebas exploratorias muestran que el copiloto encuentra más
corroboración que la búsqueda a mano, pero ninguna tarea se completó dentro del cronómetro, así
que no reportamos un "X % más rápido".

## Método previsto

- **Evaluador:** una persona (Cristian, del equipo), el 7 oct 2026, con `main` en la app y los mismos datos en las dos condiciones.
- **Tres tareas de editor**, cada una hecha dos veces:
  - **a mano:** el corpus de noticias (2,214 en español e inglés) y los 540 datos del Banco Mundial en Excel, con filtros y búsqueda;
  - **con la app:** Bandeja, Ficha, Borrador y Datos y calidad.
- **Orden alternado** entre tareas (a mano primero, app primero, a mano primero), para repartir la ventaja de ya conocer la respuesta.

| Tarea | Pide |
| --- | --- |
| A | 3 temas sobre Panamá para revisar primero, cada uno con 1 noticia y n.º de medios |
| B | Aumento de tránsitos diarios del Canal: n.º de noticias, n.º de medios y qué falta verificar |
| C | Desempleo de Panamá más reciente del Banco Mundial (valor, año y unidad) + 1 noticia de empleo |

## Registro (tal como quedó)

| Orden | Tarea | Condición | Segundos | ¿Completa según la tarea? | Qué faltó |
| --- | --- | --- | --- | --- | --- |
| 1 | A | A mano | 43 | No | n.º de medios por tema (agregado después, fuera del cronómetro) |
| 2 | A | Con la app | 15 | No | n.º de medios por tema (agregado después, fuera del cronómetro) |
| 3 | B | Con la app | 12 | No | qué falta verificar |
| 4 | B | A mano | 26 | No | qué falta verificar |
| 5 | C | A mano | 40 | No | el dato del Banco Mundial (valor, año, unidad) |
| 6 | C | Con la app | 15 | No | valor, unidad y la noticia (solo el ID con el año) |

El promedio crudo es 36 s a mano frente a 14 s con la app. **No se usa como resultado:** compara
tareas incompletas, y en las filas 1 y 2 la respuesta se completó después de detener el
cronómetro.

## Lo que sí se observó

1. **Más corroboración con la app (tarea B).** La app encontró **7 noticias de 7 medios** sobre
   el aumento de tránsitos del Canal; a mano se encontraron **3 de 3**. Probablemente se perdieron
   las notas en inglés ("transits"), que la app agrupa en el mismo evento.
2. **Falla de la app encontrada por la prueba (tarea C).** La evidencia del Banco Mundial en la
   consulta muestra el ID (país, indicador y año) y el valor, pero **no la unidad**. La regla 9 del
   reto pide país, año y unidad. Queda como corrección pendiente de la app.
3. **El cronómetro solo vale con un criterio de "terminado" explícito.** Sin una lista de lo que
   debe tener la respuesta, el evaluador cortó antes de terminar en las 6 pruebas.

## Límites

- Un solo evaluador, del equipo, que conocía la app y el corpus.
- n = 3 tareas por condición; ninguna completa.
- Las respuestas de las filas 1, 2 y 6 se editaron después de cerrar el cronómetro.

## Cómo medirlo bien (próximo paso)

Repetir con 2 o 3 editores de TVN, tareas nuevas en cada condición, una lista de verificación por
tarea que defina cuándo está completa, y el cronómetro activo hasta marcar la última casilla.
Reportar la mediana de tiempo y la tasa de tareas completas en cada condición.
