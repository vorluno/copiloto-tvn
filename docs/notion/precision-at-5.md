# Precision@5 · evaluación exploratoria (C-09)

Para la página **6 · Pruebas y métricas** de Notion, debajo de la matriz T01–T10.

## Resultado

**Precision@5 = 2/5 (40 %)**: 2 de las 5 prioridades del sistema coinciden con los temas que
elegiría un editor. Es una **evaluación exploratoria**, no una medición con un editor real (ver
límites).

> **Fecha y corte:** medida el 7 oct 2026 con el corpus de entonces (**2,462 noticias, 2,015
> eventos**). El corpus final (11,337 noticias, 8,421 eventos) cambió el top 5: el Canal sube a #2,
> y entran Cobre Panamá (#4) y el aporte del Canal al Estado (#5). Este resultado **no** describe el
> ranking final; la corrida con el corpus final está al final de esta página.

## Corrida 2 · corpus final (7 oct, tarde)

**Precision@5 = 2/5 (40 %).** Mismos temas del editor y mismo método. Top 5 de `main` `86cacce`
(11,337 noticias, 8,421 eventos, `scoring_v1`, filtro es + en):

| # | P | Tema del sistema | Titular | Registros · procedencias | ¿Coincide? |
| --- | --- | --- | --- | --- | --- |
| 1 | 91.0 | economía | ¿Cómo está el empleo en Panamá? Presidente afirma que el desempleo baja y sector privado gana terreno | 1 · 1 | No |
| 2 | 78.3 | logística/Canal | Autoridad del Canal de Panamá aumenta a 33 buques capacidad diaria de tránsito | 7 · 7 | **Sí** (Canal) |
| 3 | 77.4 | logística/Canal | Panama Canal disruption creates new cargo accumulation headache | 1 · 1 | **Sí** (Canal) |
| 4 | 76.1 | economía | Panama panel backs path to Cobre Panama restart | 1 · 1 | No |
| 5 | 76.0 | logística/Canal | Canal de Panamá: esta es la millonaria cifra que aportará al Estado en 2027 | 1 · 1 | No |

**Fila dudosa:** la #5 trata del Canal (su aporte al Estado) y el evaluador la juzgó fuera de su
tema "Canal de Panamá". Se respeta su criterio; con la otra lectura serían 3/5 (60 %).

**Lectura:** el resultado no cambia con el corpus final (2/5). Siguen ausentes deuda pública, El Niño,
CSS y turismo, y 4 de las 5 filas tienen una sola fuente (1 · 1).

## Método

1. **Selección humana independiente.** Cristian (C, producto) eligió, sin abrir la app, los 5 temas
   que revisaría primero como editor de TVN sobre Panamá en el período del corpus
   (02/10/2025–30/09/2026), en orden de prioridad.
2. **Top 5 del sistema**, con la configuración de la demo: `score_clusters` sobre el corpus completo
   (2,015 clusters, reglas `scoring_v1`, urgencia contra la fecha del corpus, ADR-027) y el filtro
   de idioma por defecto, español + inglés (ADR-043). Corrida sobre `main` `81f8ff4` el 7 oct 2026.
3. **Coincidencia decidida por la persona evaluadora**, fila por fila: una fila del top 5 es acierto
   si pertenece a uno de los 5 temas elegidos, según lo que dice el titular y no la etiqueta del
   sistema. Precision@5 = aciertos / 5.

## Datos

**Temas del editor**, en orden: 1. Canal de Panamá · 2. Deuda pública · 3. El Niño · 4. CSS
(Caja de Seguro Social) · 5. Turismo.

| # | P | Tema del sistema | Titular | Registros · procedencias | ¿Coincide? |
| --- | --- | --- | --- | --- | --- |
| 1 | 90.9 | economía | ¿Cómo está el empleo en Panamá? Presidente afirma que el desempleo baja y sector privado gana terreno | 1 · 1 | No |
| 2 | 78.2 | economía | La pobreza no solo será económica (Panamá América) | 2 · 2 | No |
| 3 | 78.2 | logística/Canal | Panama Canal adds daily transit slot, raises Neopanamax draft limit | 7 · 7 | **Sí** (Canal) |
| 4 | 77.2 | logística/Canal | Panama Canal disruption creates new cargo accumulation headache | 1 · 1 | **Sí** (Canal) |
| 5 | 76.1 | logística/Canal | La economía de expatriados: un mercado con potencial para seguir creciendo en Panamá | 3 · 3 | No |

**Cobertura por tema:** de los 5 temas del editor, solo **1 (Canal)** aparece en el top 5. Deuda
pública, El Niño, CSS y Turismo no aparecen; el sistema prioriza empleo y pobreza.

## Lectura

- **Acierta en el Canal:** el evento con más corroboración del corpus (7 registros, 7 procedencias) está en el top 5.
- **Prioriza notas de una sola fuente** (#1 y #4, 1 · 1). Las sube la urgencia y la relación con Panamá, no la corroboración: E pesa solo 10 %.
- **La fila 5 muestra un error de tema:** el sistema la clasificó como `logística/Canal`, pero trata de la economía de los expatriados.
- **Temas del editor que no entran:** sin contexto oficial vinculado (B-14 es estricto a propósito) ni varias procedencias, el impacto (I) y la evidencia (E) quedan bajos.

## Límites

- **Un solo evaluador**, del equipo, no un editor de TVN. No es una medida de validez editorial.
- **El evaluador ya había visto versiones anteriores del ranking** durante el desarrollo, así que la independencia no es total.
- **Temas frente a eventos:** el editor eligió temas y el sistema ordena eventos (clusters). La coincidencia la decide una persona, y otra podría juzgar distinto.
- **n = 5:** un acierto más o menos cambia el resultado en 20 puntos.

**Próximo paso:** repetir con 2 o 3 editores de TVN, a ciegas, sobre el mismo corte de datos.
