# Reporte de calidad de datos

Generado: 2026-10-07T20:06:42Z (UTC) · B-05 · `src/validate.py`

Las filas con errores se separan y la carga sigue. Los nulos permitidos se conservan como nulos (nunca 0).

## Noticias (`noticias.parquet`)

- Filas leídas: 11356
- Filas válidas: 11337
- Repetidas entre fuentes (se conserva TVN): 3
- Filas separadas: 19

### Problemas por tipo

| problema | filas |
| --- | --- |
| campo obligatorio vacío | 19 |

### Detalle

| id_noticia | campo | problema | valor |
| --- | --- | --- | --- |
| N-4e366c91ca | titulo | campo obligatorio vacío |  |
| N-eb43368085 | titulo | campo obligatorio vacío |  |
| N-af40e1cb7a | titulo | campo obligatorio vacío |  |
| N-994bbdfa61 | titulo | campo obligatorio vacío |  |
| N-9618e9133b | titulo | campo obligatorio vacío |  |
| N-c8092e031e | titulo | campo obligatorio vacío |  |
| N-cf647b437e | titulo | campo obligatorio vacío |  |
| N-6988df30b2 | titulo | campo obligatorio vacío |  |
| N-50d1241c0f | titulo | campo obligatorio vacío |  |
| N-baf06dc885 | titulo | campo obligatorio vacío |  |
| N-9bc1b543bc | titulo | campo obligatorio vacío |  |
| N-7497bb2c7b | titulo | campo obligatorio vacío |  |
| N-b2821cdf6c | titulo | campo obligatorio vacío |  |
| N-83b4cbfa8e | titulo | campo obligatorio vacío |  |
| N-4eaafde597 | titulo | campo obligatorio vacío |  |
| N-6127d9a32c | titulo | campo obligatorio vacío |  |
| N-e4f44c4beb | titulo | campo obligatorio vacío |  |
| N-ceca459731 | titulo | campo obligatorio vacío |  |
| N-7fcc79cb7f | titulo | campo obligatorio vacío |  |

### Nulos por columna (filas válidas)

| columna | nulos |
| --- | --- |
| id_noticia | 0 |
| titulo | 0 |
| descripcion | 10148 |
| url | 0 |
| medio | 0 |
| dominio | 0 |
| idioma | 0 |
| fecha_publicacion | 10089 |
| fecha_deteccion | 1248 |
| fecha_extraccion | 0 |
| origen | 0 |
| alcance_texto | 0 |
| procedencia_id | 11337 |
| tema | 11337 |
| tema_confianza | 11337 |
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
