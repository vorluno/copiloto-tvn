# Entrega · jueves 8 de octubre de 2026 (J-14)

Congelamos código a las **20:00**. De 20:00 a 23:00 solo se documenta y se ensaya. A las **23:00** se
entrega, con una hora de margen sobre el cierre (23:59). Base: "Checklist de entrega" del plan maestro.

## Orden del día

La caché del modelo depende de los datos: si los datos cambian después de la corrida con Gemini, hay
que volver a correrla. Por eso el orden importa.

| Hora | Qué | Quién | Listo cuando |
| --- | --- | --- | --- |
| 12:00 | PR de datos finales: GDELT completo, `fecha_deteccion` (ADR-032), sin `titulo` nulo | Levi → José mergea | `make test` y `make verify` en verde |
| 12:00 | 60 etiquetas humanas (C-05) y benchmark de 40 consultas (C-06) | Cristian | archivos con datos en `main` |
| 14:00 | Corrida con Gemini: `make demo-cache` y PR `feat/J-12-cache-demo` ([guía](demo/corrida-llm.md)) | Levi → José mergea | `OFFLINE=1 make demo-cache` dice "Caché completa" |
| 14:00 | Métricas: macro-F1 IA vs baseline (B-12) y `make eval` | Levi y José | `outputs/reports/` con numerador y denominador |
| 18:00 | T01–T10 ejecutadas y registradas; 5+ fichas en Notion, una con evidencia insuficiente | Cristian | matriz completa en Notion |
| 19:00 | Grabación de la demo con wifi apagado (C-18) | Cristian | video en Notion, sin secretos en pantalla |
| 20:00 | **Congelamiento**: último merge, verificación final y tag `v1.0` | José | tag publicado |
| 20:00–23:00 | Notion completo, 2 ensayos cronometrados del pitch | Todos | pitch de 10 min desde Notion |
| 23:00 | Entrega | José | enlaces enviados |

## Verificación final del repo (José, 20:00)

En una carpeta nueva, como lo haría el jurado:

```bash
git clone https://github.com/vorluno/copiloto-tvn.git entrega && cd entrega
make setup
make test                    # todo en verde; ninguna clave en archivos versionados
make verify                  # SHA-256 de los datos = data/manifest.json
OFFLINE=1 make demo-cache    # "Caché completa para la demo sin internet."
OFFLINE=1 make demo          # con wifi apagado: bandeja, ficha, borrador, consulta y revisión
git log --all -p | grep -E "sk-or-v1-[A-Za-z0-9]{16,}" || echo "historial sin claves"
```

Después, en el repo de trabajo:

```bash
git checkout main && git pull
git tag -a v1.0 -m "Copiloto TVN · entrega hackIAthon 2026"
git push origin v1.0
```

Actualizar en el README la línea de **Estado** con los números finales (noticias, eventos, métricas).

## Condiciones de admisión (si falta una, no nos evalúan)

| Condición | Dueño | Dónde |
| --- | --- | --- |
| Notion con las 8 páginas y acceso del jurado verificado desde una ventana privada | Cristian | Notion |
| Plan con 8+ tareas y 3+ decisiones registradas durante el evento | Cristian | `docs/notion/tareas.csv`, `decisiones.csv` → Notion |
| Catálogo completo de fuentes | Levi | `docs/notion/catalogo.csv` → Notion |
| 5+ fichas trazables, una con evidencia insuficiente | Cristian (desde `outputs/fichas.jsonl`) | Notion |
| Matriz T01–T10 con resultados y métricas de la ejecución final | Cristian | Notion |
| Repo con acceso del jurado: README, instalación, comando, dependencias fijadas, `.env.example`, pruebas | José | este repo (público) |
| Demo que funciona sin internet | José y Levi (caché), Cristian (grabación) | `OFFLINE=1 make demo` |
| Pitch de 10 minutos presentado desde Notion | Cristian, todos ensayan | Notion |
| Cero secretos en código, Notion o capturas; cero citas falsas | Todos | `tests/test_no_secrets.py`, guard |

## Las 4 preguntas del jurado

Las respuestas, con dónde mostrarlas en vivo, están en el README ("Cómo cumple el reto").
Cada uno debe poder contestarlas sin mirar.
