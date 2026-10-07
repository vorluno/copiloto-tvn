# 7 · Riesgos y ética

Página 7 de Notion (C-07, Cristian). Integra el aporte de datos de Levi
([`riesgos-datos.md`](riesgos-datos.md), B-16): las cifras de sesgo y cobertura están allí.
Cada riesgo lleva su control o dice que no lo tiene.

**Principio:** el copiloto redacta **borradores para revisión humana**. No publica, no decide si
algo es verdad y no reemplaza a la persona editora. Aprobar como borrador no es publicar.

## 1. Privacidad

| Riesgo | Control |
| --- | --- |
| Nombres de personas en titulares públicos (detenciones, audiencias: unos 54) | No extraemos personas, no armamos perfiles ni listas, no cruzamos fuentes por persona. Las acusaciones se muestran como **declaración atribuida**, no como hecho (ADR de J-09). |
| Un titular viejo sobre alguien cuyo caso cambió | **Sin control automático.** La fecha original queda visible (recirculadas, T03) y la persona revisora decide. |
| Datos de lectores o usuarios | No se guardan. La app no tiene cuentas y la telemetría de Streamlit está apagada (`make demo`). |
| Nombres de quien revisa en `outputs/revisiones.jsonl` | Solo personas del equipo, con su acuerdo; el log se sube al repo como evidencia de la revisión humana. |
| Claves del LLM | Solo en `.env` (fuera de git). Una prueba (`test_no_secrets`) falla si aparece una clave en el repo. Nunca en código, PRs, Notion ni capturas. |

## 2. Derechos por fuente

| Fuente | Qué usamos | Qué no hacemos |
| --- | --- | --- |
| TVN (RSS y web) | Titular, descripción, fecha y URL (metadatos públicos) | No guardamos ni redistribuimos el cuerpo, las imágenes ni el video. Scraping solo donde robots.txt lo permite, 1 página/s. |
| GDELT | Titular, URL, dominio, idioma y fecha de detección | No abrimos ni copiamos el artículo del medio enlazado; la API no transfiere sus derechos. |
| Banco Mundial | Valor por país, indicador y año (CC BY 4.0, con atribución) | No lo presentamos como cifra de hoy (T04). |
| USGS | Sismos de 2024 en una caja regional (dominio público) | No lo usamos para daños, inundaciones ni pérdidas. |

Detalle por medio en `data/processed/fuentes.json` y en el Catálogo de datos (página 3).

## 3. Sesgos y límites (resumen; cifras en `riesgos-datos.md`)

- **Mitad del corpus es solo titular** (todo GDELT): el borrador lo dice ("Basado únicamente en titular/metadatos") y no agrega detalles.
- **Cobertura desigual:** GDELT topa en 250 por consulta y tiene pocos medios panameños; TVN es una muestra de 100 artículos por mes, no un censo. No reportamos volúmenes como peso real de la agenda.
- **81 % del corpus queda en "otro"**: el ranking trabaja sobre una parte. El umbral se calibra con etiquetas humanas (B-12).
- **Idiomas:** probado en español e inglés; la bandeja filtra esos dos por defecto (ADR-043).
- **Procedencia aproximada:** un medio que reescribe a EFE sin nombrarla cuenta como fuente propia, así que la corroboración puede **sobrestimarse**.
- **Búsqueda léxica:** encuentra la evidencia esperada en 87 % del benchmark (#48); una pregunta con palabras distintas a las del titular puede quedarse sin evidencia y abstenerse.

## 4. Inyección al agente (T07)

| Control | Dónde |
| --- | --- |
| El texto de las fuentes va dentro de `<fuente>`, escapado; las reglas solo en el mensaje de sistema | `src/generate/` (ADR-014, J-11) |
| El guard detecta instrucciones en la evidencia, bloquea cualquier salida que filtre la clave o el prompt y genera una **alerta** | `src/generate/guard.py`, T07 (9 pruebas) |
| La app muestra la alerta y nunca usa esa fuente como hecho | Ficha y Borrador (C-13, C-14) |
| 6 consultas adversariales en el benchmark | `benchmark/benchmark_dev.jsonl` (C-06) |

**Límite:** el benchmark prueba el ataque dentro de la **pregunta**. El ataque dentro de una
**fuente** solo se prueba en T07, con datos sintéticos aislados, porque meter una noticia falsa en
el corpus rompería la regla 12.

## 5. Invención de datos

- **Cada afirmación lleva cita** (ID + campo + pasaje). El guard descarta lo que no esté en la evidencia, y la app marca ✅ solo si el pasaje aparece en la fuente.
- **Cifras:** una cifra sin respaldo en la cita se descarta (T06, J-10).
- **Abstención** cuando la evidencia no alcanza, sin cifra "aproximada".
- **Contradicciones:** se muestran ambas versiones con "verificación pendiente" (T05).
- **Tipos de afirmación:** hecho, declaración, inferencia o hipótesis, diferenciados en pantalla.
- **El LLM no calcula el puntaje.** P es determinista (`scoring_v1`), y una prioridad alta no habilita publicar (T08).
- **Datos sintéticos** siempre con `sintetico=true` y nunca junto a los reales (regla 12, #28).

## 6. Control humano

Cinco estados de revisión, cada uno con la persona revisora obligatoria y una nota (C-15). El log
solo agrega líneas y nunca se reescribe. Nada sale de la app sin que una persona lo apruebe, y
aprobar es "aprobado **como borrador**".

## 7. Incidentes del evento (registrados, no ocultos)

| Fecha | Qué pasó | Corrección |
| --- | --- | --- |
| 6 oct | Dos titulares nulos de GDELT hacían caer la búsqueda | `9e1a731` (#41) |
| 7 oct | La pantalla de Revisión podía guardar una decisión en **otra ficha** | `a033359` (#44), con prueba |
| 7 oct | Fichas y caché de **relleno** ("palabra palabra…") entraron a `main` como si fueran de Gemini | Detectado en C-08 (#52); pendiente de revertir y regenerar con Gemini |

## 8. Fuera de alcance

Decidir si una noticia es verdadera o falsa; medir audiencia o rating; publicar automáticamente;
contenido detrás de paywall; datos personales de lectores o clientes; republicar artículos,
imágenes o video; la modalidad bancaria (próximo paso).
