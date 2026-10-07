# Latencia, tokens y costo (J-13)

Generado: 2026-10-07T22:04:14Z (UTC) · modelo `google/gemini-2.5-flash`

Tiempo de punta a punta por consulta (búsqueda + LLM + guard). Meta del reto: mediana ≤ 15 s.

| Medida | Valor |
| --- | --- |
| Consultas | 40 |
| Llamadas reales al LLM | 39 |
| Por origen | {'llm': 39, 'cache': 1} |
| Mediana (todas) | 4.844 s |
| p95 (todas) | 8.823 s |
| Mediana (con LLM) | 4.904 s |
| p95 (con LLM) | 9.433 s |
| Tokens de entrada | 45255 |
| Tokens de salida | 28080 |
| Costo total (USD) | 0.084 |
| Costo por consulta con LLM (USD) | 0.002 |
