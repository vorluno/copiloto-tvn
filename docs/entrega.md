# Entrega · jueves 8 de octubre de 2026 (J-14)

Congelamos código a las **20:00**. De 20:00 a 23:00 solo se documenta y se ensaya. A las **23:00** se
entrega **por correo a hackiathon@viamatica.com**, con una hora de margen sobre el cierre (23:59, GMT−5,
la misma hora de Panamá). Base: "Checklist de entrega" del plan maestro.

> **8 oct · sin Notion (ADR-047).** La organización avisó que no entrega el espacio de Notion y que no es
> obligatorio. Las 8 páginas quedan en [`docs/notion/`](notion/README.md), en el repo público. Todos los
> enlaces que se envían tienen que abrir sin cuenta: repo, documentación y video.

## Orden del día

La caché del modelo depende de los datos: si los datos cambian después de la corrida con Gemini, hay
que volver a correrla. Por eso el orden importa.

| Hora | Qué | Quién | Listo cuando |
| --- | --- | --- | --- |
| 12:00 | PR de datos finales: GDELT completo, `fecha_deteccion` (ADR-032), sin `titulo` nulo | Levi → José mergea | `make test` y `make verify` en verde |
| 12:00 | 60 etiquetas humanas (C-05) y benchmark de 40 consultas (C-06) | Cristian | archivos con datos en `main` |
| 14:00 | Corrida con Gemini: `make demo-cache` y PR `feat/J-12-cache-demo` ([guía](demo/corrida-llm.md)) | Levi → José mergea | `OFFLINE=1 make demo-cache` dice "Caché completa" |
| 14:00 | Métricas: macro-F1 IA vs baseline (B-12) y `make eval` | Levi y José | `outputs/reports/` con numerador y denominador |
| 18:00 | T01–T10 ejecutadas y registradas en `pruebas.csv`; 5+ casos revisados en la app (una persona, en el repo real) y `python tools/casos_md.py` | Cristian | matriz completa; `casos.md` con persona revisora en 5+ casos, uno abstenido |
| 18:00 | QA de la interfaz en el navegador con las fichas de Gemini: `tools/qa_app.js` (escenarios `real` y `stub`, en una copia del repo) | Cristian | todo PASS |
| 18:00 | Validez de sustento: una persona llena `valida` (sí/no) y `revisor` en `outputs/reports/sustento_revision.csv` (ya está en el repo; 89 afirmaciones, 158 citas) y corre `python tools/sustento.py` (≥ 30 afirmaciones; meta ≥ 90 %) | Cristian | CSV y `outputs/reports/sustento.md` en el repo; resultado en `pruebas.csv` y el pitch |
| 19:00 | Grabación de la demo con wifi apagado (C-18) | Cristian | video con enlace público (YouTube no listado o Drive "cualquiera con el enlace"), sin secretos en pantalla |
| 20:00 | **Congelamiento**: último merge, verificación final y tag `v1.0` | José | tag publicado |
| 20:00–23:00 | Documentación (8 páginas en `docs/notion/`) completa, 2 ensayos cronometrados del pitch | Todos | pitch de 10 min desde `presentacion.md` |
| 23:00 | Correo de entrega (abajo) a hackiathon@viamatica.com | José | correo enviado; los enlaces abren desde una ventana privada |

## Verificación final del repo (José, 20:00)

En una carpeta nueva, como lo haría el jurado:

```bash
git clone https://github.com/vorluno/copiloto-tvn.git entrega && cd entrega
make setup
make test                    # todo en verde; ninguna clave en archivos versionados
make verify                  # SHA-256 de los datos = data/manifest.json
OFFLINE=1 make demo-cache    # "Caché completa para la demo sin internet."
OFFLINE=1 make demo          # con wifi apagado: bandeja, ficha, borrador, consulta y revisión
git log --all -p | grep -E "sk-or-v1-[A-Za-z0-9]{16,}" | grep -vE "abcdefghijklmnop|0{16}" || echo "historial sin claves"
                             # las dos excluidas son claves falsas de las pruebas (test_guard, test_t07)
```

Después, en el repo de trabajo:

```bash
git checkout main && git pull
git tag -a v1.0 -m "Copiloto TVN · entrega hackIAthon 2026"
git push origin v1.0
```

Actualizar en el README la línea de **Estado** con los números finales (noticias, eventos, métricas).

## Correo de entrega (José, 23:00)

Para: hackiathon@viamatica.com · Asunto: `hackIAthon 2026 · Reto TVN Media · Copiloto TVN`

Antes de enviarlo, abrir **cada enlace desde una ventana privada** (sin sesión de GitHub ni de Google):

- [ ] Repositorio público: https://github.com/vorluno/copiloto-tvn (tag `v1.0`)
- [ ] Documentación, las 8 páginas: https://github.com/vorluno/copiloto-tvn/tree/v1.0/docs/notion
- [ ] Cómo probarlo en 5 minutos: sección "Para el jurado" del README
- [ ] Video de la demo sin internet (enlace público)
- [ ] Equipo: José, Levi y Cristian, con su rol

Pitch Day: la organización avisa el lunes 12 qué 9 equipos pasan; es el viernes 16 en ADEN University.

## Condiciones de admisión (si falta una, no nos evalúan)

| Condición | Dueño | Dónde |
| --- | --- | --- |
| Las 8 páginas en el repo público, abiertas desde una ventana privada (ADR-047) | José (1, 4, 5) y Cristian (resto) | `docs/notion/` |
| Plan con 8+ tareas y 3+ decisiones registradas durante el evento | Cristian | `docs/notion/tareas.csv`, `decisiones.csv` |
| Catálogo completo de fuentes | Levi | `docs/notion/catalogo.csv` |
| 5+ fichas trazables, una con evidencia insuficiente | Cristian revisa; `tools/casos_md.py` genera la página | `docs/notion/casos.md` |
| Matriz T01–T10 con resultados y métricas de la ejecución final | Cristian | `docs/notion/pruebas.csv` + `outputs/reports/` |
| Repo con acceso del jurado: README, instalación, comando, dependencias fijadas, `.env.example`, pruebas | José | este repo (público) |
| Demo que funciona sin internet | José y Levi (caché), Cristian (grabación) | `OFFLINE=1 make demo` |
| Pitch de 10 minutos | Cristian, todos ensayan | `docs/notion/presentacion.md` |
| Cero secretos en código, documentos, video o capturas; cero citas falsas | Todos | `tests/test_no_secrets.py`, guard |

## Las 4 preguntas del jurado

Las respuestas, con dónde mostrarlas en vivo, están en el README ("Cómo cumple el reto").
Cada uno debe poder contestarlas sin mirar.
