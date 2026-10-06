# Reporte de calidad de datos

Generado: 2026-10-06T20:56:23Z (UTC) · B-05 · `src/validate.py`

Las filas con errores se separan y la carga sigue. Los nulos permitidos se conservan como nulos (nunca 0).

## Noticias (`noticias.parquet`)

El archivo no existe todavía (B-01, B-02).

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
