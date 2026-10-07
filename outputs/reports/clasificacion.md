# Clasificación y agrupación contra etiquetas humanas (B-12)

Generado por `python -m src.eval.classification`. Etiquetas: `data/etiquetas_humanas.csv` (Cristian Valdes).

## Muestra y método

- Etiquetadas válidas: **60**; descartadas por etiqueta vacía o fuera de la lista: 0.
- Muestra: 60 noticias en español o inglés elegidas por código (semilla 20261007): 40 al azar + 20 vecinas (la más parecida dentro de ±72 h), para que haya pares del mismo evento. Etiquetado por una persona que no construyó el modelo, solo con titular y descripción.
- **Temas:** el umbral se calibra con una mitad fija (30 noticias) y todo se reporta con la otra (30). Umbral elegido: **0.45** (en uso en `classify.THRESHOLD`: 0.45).
- **Eventos:** precisión y recall por pares sobre las 60 etiquetadas; distancia de cluster 0.30 + 2 raíces de contenido en común, regla fijada con 9 grupos revisados a mano por José antes de leer estas etiquetas (no se ajusta aquí).
- Muestra chica: una noticia cambia el F1 de un tema varios puntos. Los resultados son indicativos.

## Temas: IA vs baseline (mitad de reporte)

| Sistema | Macro-F1 | Temas medidos | n |
| --- | --- | --- | --- |
| IA (embeddings, umbral 0.45) | 0.37 | 6 | 30 |
| Baseline (palabras clave) | 0.29 | 7 | 30 |

Por tema (VP / FP / FN y F1):

| Tema | IA | Baseline | Gana |
| --- | --- | --- | --- |
| economía | 3/5/2 · 0.46 | 3/1/2 · 0.67 | baseline |
| logística/Canal | 1/0/0 · 1.00 | 1/1/0 · 0.67 | IA |
| turismo | 0/0/0 · — | 0/2/0 · 0.00 | empate |
| servicios públicos | 0/0/3 · 0.00 | 0/1/3 · 0.00 | empate |
| eventos naturales | 0/1/0 · 0.00 | 0/2/0 · 0.00 | empate |
| regulación | 0/1/0 · 0.00 | 0/1/0 · 0.00 | empate |
| otro | 15/4/6 · 0.75 | 14/4/7 · 0.72 | IA |

Calibración del umbral (mitad de calibración):

| Umbral | Macro-F1 |
| --- | --- |
| 0.30 | 0.14 |
| 0.35 | 0.16 |
| 0.40 | 0.19 |
| 0.45 ← | 0.23 |
| 0.50 | 0.19 |
| 0.55 | 0.12 |
| 0.60 | 0.12 |
| 0.65 | 0.12 |
| 0.70 | 0.14 |

## Eventos: precisión y recall por pares (todas las etiquetadas)

| Sistema | Precisión | Recall |
| --- | --- | --- |
| IA (embeddings, distancia 0.30 + 2 palabras, 72 h) | 3/3 (100%) | 3/3 (100%) |
| Baseline (TF-IDF ≥ 0.9, 72 h) | 1/1 (100%) | 1/3 (33%) |

**4 etiquetas de evento se corrigieron después de comparar con el sistema** (columna `nota`, #62): no son ciegas. Con la entrega ciega (cada una como evento propio) la IA da precisión 1/3 (33%) y recall 1/1 (100%). Se reportan las dos: con 3 pares, ninguna es concluyente.

Sensibilidad a la distancia (exploratoria: se mira con las mismas etiquetas):

| Distancia | Precisión | Recall |
| --- | --- | --- |
| 0.20 | 2/2 (100%) | 2/3 (67%) |
| 0.25 | 3/3 (100%) | 3/3 (100%) |
| 0.30 | 3/3 (100%) | 3/3 (100%) |
| 0.35 | 3/3 (100%) | 3/3 (100%) |
| 0.40 | 3/4 (75%) | 3/3 (100%) |

## Errores de tema (mitad de reporte)

| id_noticia | Titular | Humano | IA | Baseline |
| --- | --- | --- | --- | --- |
| N-0e21154757 | Clásico Mundial de Béisbol 2026: Hijos de Manny Ramírez y José Contreras lideran a Brasil | otro | otro | logística/Canal ✗ |
| N-6b265d83ab | WISS LATAM reúne a mujeres líderes y empresarias para impulsar la innovación y el liderazg | economía | otro ✗ | otro ✗ |
| N-07368175e7 | Meta y YouTube, declaradas responsables en juicio por adicción a redes sociales en EEUU | economía | otro ✗ | otro ✗ |
| N-0476dc200f | Clima en Panamá: Aguaceros moderados a fuertes afectarán gran parte del país | otro | eventos naturales ✗ | eventos naturales ✗ |
| N-030b9d1d3e | Más de 26 mil colombianos en Panamá estuvieron habilitados para votar en sus elecciones pr | otro | economía ✗ | otro |
| N-02b8973d50 | Juegos Centroamericanos y del Caribe / Panamá aplastó a Colombia en el sóftbol masculino | otro | economía ✗ | otro |
| N-023e7a442f | Asamblea aprobó proyecto que establece penas de hasta 10 años de prisión por cerrar acceso | otro | regulación ✗ | regulación ✗ |
| N-7b171e42cf | Diecinueve aerolíneas operan en los terminales temporales de Maiquetía | otro | otro | turismo ✗ |
| N-00c1239378 | Virus sincitial respiratorio: Bocas del Toro registra 238 casos y dos defunciones en bebés | otro | otro | servicios públicos ✗ |
| N-215b8409b1 | Caraballo habría usado el JSP para  persecución política , según abogada | servicios públicos | otro ✗ | otro ✗ |
| N-f3eaa46242 | Greenland Is Not for Sale : Trump Donroe Doctrine and US Imperialism | servicios públicos | otro ✗ | otro ✗ |
| N-0f43860181 | Serie del Caribe Kids/ Elpidio Pinto: coach manifiesta que Panamá ha trabajado bastante en | otro | economía ✗ | otro |
| N-4a8c86692b | Panamá abre centro que fusiona historia y naturaleza tras invertir 7 , 7 millones de dólar | otro | economía ✗ | otro |
| N-1caba9b3ca | Diecinueve aerolíneas operan en terminales temporales del mayor aeropuerto de Venezuela | otro | otro | turismo ✗ |
| N-082272ef58 | Regalías de concentrado de cobre se destinarán a obras prioritarias en comunidades vecinas | servicios públicos | economía ✗ | economía ✗ |
| N-888ce95fa5 | Venezuela main airport partially resumes commercial flights after deadly earthquakes | otro | otro | eventos naturales ✗ |

## Pares mal agrupados por la IA

- ninguno
