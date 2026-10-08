# 1 · Inicio del reto

**Copiloto TVN** · hackIAthon 2026, reto TVN Media · modalidad **editorial TVN** (ADR-001).

## Equipo

| Persona | Rol | Es dueño de |
| --- | --- | --- |
| José | Líder técnico e integración | Repo, arquitectura, puntaje, búsqueda, generación con LLM, guard, caché offline, fichas |
| Levi | B · Datos e IA | Ingesta, validación, contexto oficial, embeddings, temas, procedencia, clusters, baseline, métricas |
| Cristian | C · Producto, frontend y QA | Interfaz, etiquetas humanas, benchmark, pruebas T01–T10, riesgos, pitch |

## Problema

Una redacción recibe cada día cientos de notas sobre Panamá, de TVN y de medios de todo el mundo, más
datos oficiales sueltos. Decidir qué revisar primero, saber cuántas fuentes **independientes** respaldan
un hecho y escribir un primer borrador sin inventar nada toma tiempo y se hace a mano.

## Usuario

La editora o el editor de turno y la periodista o el periodista de TVN. El copiloto **no publica**:
prepara borradores para revisión humana.

## Qué hace (las 7 etapas del reto)

1. **Carga** noticias públicas (TVN RSS y web, GDELT) y datos oficiales (Banco Mundial, USGS) y reporta su calidad.
2. **Organiza:** tema y evento por noticia; cuenta procedencias independientes, no registros.
3. **Contextualiza** con indicadores y sismos solo cuando la relación está sustentada.
4. **Prioriza** con P = 30R + 25I + 20U + 15N + 10E, determinista y con sus componentes a la vista.
5. **Explica** en una ficha qué se reporta, quién, qué está respaldado y qué falta.
6. **Produce** brief, guion de 45–60 s y copy digital, con una cita por afirmación; se abstiene sin evidencia.
7. **Revisa:** una persona marca el estado, que queda registrado con su nombre y la fecha.

## Alcance

- Noticias del 02/10/2025 al 30/09/2026: **11,337** (1,248 de TVN y 10,089 de GDELT), en **8,421 eventos**.
- Banco Mundial: 6 países × 6 indicadores × 2010–2024. USGS: sismos de 2024.
- De TVN solo metadatos públicos (titular, descripción, fecha, URL), nunca el cuerpo, imágenes ni video.
- Funciona sin internet (`OFFLINE=1`): el modelo se sirve desde la caché.
- Fuera de alcance: la modalidad bancaria (ADR-001) y publicar. Riesgos y controles en la página 7.

## Criterios de éxito y resultado

Cifras de la ejecución final, con numerador y denominador (detalle en la página 6 y en `outputs/reports/`).

| Criterio | Meta | Resultado |
| --- | --- | --- |
| Afirmaciones mostradas con cita válida | 100 % | 89/89 (100 %) |
| Abstención correcta sin evidencia | ≥ 80 % | 7/7 (100 %) |
| Consultas adversariales: sin filtración y con alerta | 100 % | 6/6 (100 %), con la alerta en código (ADR-046) |
| Latencia mediana por consulta | ≤ 15 s | 4.84 s (p95 8.82 s) |
| Demo sin internet | completa | `OFFLINE=1 make demo-cache`: "Caché completa" |
| Validez de sustento (revisión humana) | ≥ 90 % sobre ≥ 30 afirmaciones | ver página 6 |

Límites medidos, dichos como límites: contradicciones mostradas 3/7 y respondibles sin abstención
indebida 15/20 (página 6).

## Enlaces

- Repositorio (público): https://github.com/vorluno/copiloto-tvn · versión de entrega: tag `v1.0`.
- Cómo probarlo en 5 minutos: sección "Para el jurado" del [README](../../README.md).
- Video de la demo sin internet (3 min, grabado con `OFFLINE=1` en el orden del pitch): [`docs/demo/copiloto-tvn-demo-respaldo.mp4`](https://github.com/vorluno/copiloto-tvn/blob/main/docs/demo/copiloto-tvn-demo-respaldo.mp4).
- Las 8 secciones: [índice](README.md).
