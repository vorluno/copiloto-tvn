# Riesgos de los datos (B-16)

Aporte de Levi (B) a la página **7 · Riesgos y ética** de Notion (C-07, Cristian). Cifras sobre el
corpus final del 07/10/2026 (11,337 noticias: 1,248 de TVN y 10,089 de GDELT, con GDELT completo
para el período 02/10/2025–30/09/2026). Cada riesgo trae su control o, si no hay, lo dice.

## 1. Derechos por fuente

| Fuente | Qué guardamos | Qué **no** hacemos | Condición |
| --- | --- | --- | --- |
| TVN RSS y TVN web | Titular, descripción corta, fecha, URL (JSON-LD del artículo) | No guardamos ni redistribuimos el cuerpo, imágenes ni video; no saltamos paywall | El patrocinio no da derechos de republicación (reto secc. 6). Scraping solo de páginas que robots.txt permite, 1 página/s, User-Agent identificado |
| GDELT DOC 2.0 | Titular, URL, dominio, idioma, `seendate` | No abrimos ni copiamos el artículo del medio enlazado | Uso libre citando a GDELT; la API **no** transfiere derechos de los medios (reto secc. 6) |
| Banco Mundial | Valor por país, indicador y año | No presentamos un dato anual como cifra de hoy | CC BY 4.0 con atribución; revisar excepciones de terceros por indicador |
| USGS | Sismos con id, hora, lugar, magnitud | No lo usamos para inundaciones ni pérdidas | Dominio público |

Control: `fuentes.json` y el catálogo llevan las condiciones por fuente y por medio; el borrador
cita ID + campo y, si solo hay titular, dice "basado únicamente en titular/metadatos" (guard).

## 2. Privacidad y reputación

- **Hay nombres de personas en titulares públicos** (p. ej. detenciones, audiencias): unos 37 titulares con palabras como "detienen", "aprehenden", "imputado". No extraemos personas, no armamos perfiles ni listas, no cruzamos fuentes por persona.
- Las acusaciones se presentan como **declaración atribuida**, no como hecho (regla del reto; J-09).
- No guardamos datos de lectores, cuentas ni nada fuera de los metadatos públicos de la noticia.
- **Riesgo residual:** un titular antiguo sobre una persona puede seguir en el corpus aunque el caso haya cambiado. El sistema no lo sabe; la persona revisora decide.

## 3. Sesgos y cobertura

| Riesgo | Cifra | Efecto | Control |
| --- | --- | --- | --- |
| **Solo titulares en casi todo el corpus** | 89.5 % es `titular/metadatos` (todo GDELT) | El tema y el evento se deciden con pocas palabras; el borrador no puede dar detalles | `alcance_texto` en cada noticia; frase obligatoria en el borrador |
| **GDELT topa en 250 por consulta** | 48 de 64 respuestas guardadas llegaron a 250 | En esos meses entran solo los artículos más recientes del mes (orden `DateDesc`): el inicio de mes queda subrepresentado | Consultas por mes y por tema; los meses saturados quedan registrados. No se corrige del todo |
| **GDELT pesa 9 de cada 10 notas** | 10,089 de 11,337 noticias son de GDELT (de 639 a 1,261 por mes); TVN es una muestra de 100 por mes | El ranking y la corroboración reflejan sobre todo la prensa internacional sobre Panamá, no la agenda de TVN | `origen` en cada noticia; la bandeja y la ficha muestran el medio de cada registro |
| **Pocos medios panameños en GDELT** | 7.8 % de las notas de GDELT vienen de dominios `.pa`; los 10 dominios con más notas suman 16.2 % | La "corroboración" pesa más la prensa internacional que la local | Se cuentan procedencias, no registros; la ficha muestra qué medios son |
| **Idioma** | es 52.9 %, en 26.5 %, zh 6.1 %, el resto en 45 idiomas más (pt, el…) | El modelo es multilingüe pero se probó en español; en otros idiomas tema y agrupación son menos fiables. La muestra de etiquetas solo tiene es/en | B-12 mide solo es/en y lo dice |
| **Muestra de TVN, no censo** | 100 artículos por mes de ~2,300 (orden fijo por hash de la URL) | El volumen de un tema en TVN no es su peso real en la agenda | La muestra es reproducible; no reportamos "TVN publicó X notas de…" |
| **La mayoría queda en "otro"** | 73.5 % del corpus (78.4 % de TVN: deportes, sucesos, internacional) | El ranking trabaja sobre ~27 % del corpus; un tema relevante mal escrito puede caer en "otro" | Umbral 0.45 calibrado en B-12 con etiquetas humanas; el reporte lista los errores |

## 4. Límites técnicos que el jurado puede preguntar

- **Procedencia aproximada:** solo detectamos agencias nombradas (54 notas con agencia en el corpus) y casi copias de título en 48 h. Un medio que reescribe a EFE sin nombrarla cuenta como procedencia propia → la corroboración puede **sobrestimarse**.
- **Agrupación con titulares:** con titulares cortos, la similitud sola juntaba notas que solo compartían "Panamá + economía" (revisión del 07/10). Desde entonces un par debe compartir además 2 raíces de contenido. Aun así, eventos contados de forma muy distinta pueden quedar separados (los 33 tránsitos del Canal siguen en dos clusters, uno en español y otro en inglés). Se mide contra `cluster_humano` (B-12).
- **Recirculadas sin casos reales:** GDELT no indexa ninguna URL de tvn-2.com, así que ninguna noticia real tiene las dos fechas (ADR-032 no aplica a ningún caso hoy) y `recirculada` es `false` en todo el corpus. T03 se prueba con datos sintéticos.
- **`seendate` no es fecha de publicación:** en GDELT la urgencia se calcula con la fecha de detección y la ficha lo dice (`base_urgencia="deteccion"`). Nunca se copia una fecha en la otra.
- **Contexto oficial escaso a propósito:** solo 17 vínculos a indicadores del Banco Mundial (regla estricta: tema + Panamá + lo que mide el indicador). Mejor sin vínculo que con uno forzado.

## 5. Fuentes oficiales: para qué no sirven

- **Banco Mundial:** series anuales hasta 2024; no miden el mes de la noticia ni explican su causa. Una pregunta como "inflación de septiembre de 2026" debe terminar en abstención (T06).
- **USGS:** caja regional (lat 5–12, lon −86 a −76) que **no es** el territorio de Panamá, solo 2024 y solo sismos. Hoy no hay ningún vínculo de sismo con las noticias (2025–2026), a propósito.

## 6. Fuera de alcance (datos)

Decidir si una noticia es verdadera o falsa; medir audiencia o rating; contenido detrás de paywall;
datos personales de clientes o lectores; republicar artículos, imágenes o video.
