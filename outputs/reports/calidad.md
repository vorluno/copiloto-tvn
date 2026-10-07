# Reporte de calidad de datos

Generado: 2026-10-06T22:57:44Z (UTC) · B-05 · `src/validate.py`

Las filas con errores se separan y la carga sigue. Los nulos permitidos se conservan como nulos (nunca 0).

## Noticias (`noticias.parquet`)

- Filas leídas: 2462
- Filas válidas: 2462
- Repetidas entre fuentes (se conserva TVN): 3
- Filas separadas: 0

### Nulos por columna (filas válidas)

| columna | nulos |
| --- | --- |
| id_noticia | 0 |
| titulo | 2 |
| descripcion | 1273 |
| url | 0 |
| medio | 0 |
| dominio | 0 |
| idioma | 0 |
| fecha_publicacion | 1214 |
| fecha_deteccion | 1248 |
| fecha_extraccion | 0 |
| origen | 0 |
| alcance_texto | 0 |
| procedencia_id | 2462 |
| tema | 2462 |
| tema_confianza | 2462 |
| cluster_id | 0 |
| sintetico | 0 |

## Banco Mundial (`indicadores.csv`)

- Filas: 540

| columna | nulos |
| --- | --- |
| pais_iso3 | 0 |
| indicador_id | 0 |
| anio | 0 |
| valor | 0 |
| unidad | 0 |
| fuente_url | 0 |
| fecha_extraccion | 0 |
| licencia | 0 |

## USGS (`eventos.geojson`)

- Filas: 82

| columna | nulos |
| --- | --- |
| id | 0 |
| magnitude | 0 |
| time | 0 |
| updated | 0 |
| longitude | 0 |
| latitude | 0 |
| depth | 0 |
| place | 0 |
| status | 0 |
| url | 0 |
