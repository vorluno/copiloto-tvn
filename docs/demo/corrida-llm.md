# Corrida con Gemini para la demo (J-12, ADR-033)

La hace **Levi** en su máquina, con internet y la clave de OpenRouter. Deja en el repo la caché
que usa la demo sin internet. Tarda unos minutos y cuesta centavos: solo se paga lo que todavía
no está en la caché.

## Antes de empezar

1. **Datos finales primero.** La caché se guarda por hash de la entrada, y la entrada incluye la
   evidencia de cada evento. Si después cambian los datos (GDELT completo, `make nlp` de nuevo, otros
   `cluster_id`), las fichas nuevas ya no están en caché y hay que volver a correr. Orden: mergear el PR
   de datos y luego esta corrida.
2. `git pull` en `main` y `make setup` (o `.venv/bin/pip install -r requirements.txt`).
3. En `.env`, que no se sube:
   - `LLM_API_KEY=` con la clave **rotada**. Nunca en el chat, en un commit ni en una captura.
   - `LLM_PRICE_INPUT_PER_M=0.30` y `LLM_PRICE_OUTPUT_PER_M=2.50`. Confirmar los valores en
     https://openrouter.ai/google/gemini-2.5-flash y corregirlos si cambiaron.
   - `OFFLINE=0`.

## Corrida

```bash
make llm-check            # 1 llamada real: debe decir source=llm y guard ok=True
make demo-cache           # fichas del top 10 + consultas de docs/demo/consultas_demo.txt
OFFLINE=1 make demo-cache # sin red: debe terminar en "Caché completa para la demo sin internet."
OFFLINE=1 make demo       # recorrer la app sin internet: bandeja, fichas, borradores y las consultas
make eval                 # solo cuando benchmark/benchmark_dev.jsonl tenga casos (C-06)
make test                 # T09 real deja de estar en skip; ninguna clave en la caché
```

- `make demo-cache` sale con código 1 y dice qué falló:
  - `error`: falta la clave, la clave es inválida o no hay red.
  - `offline_miss` (en la comprobación sin red): falta en caché; vuelve a correr `make demo-cache` con red.
- `TOP=15 make demo-cache` genera más fichas. Si Cristian cambia una consulta del pitch, hay que volver a correr.
- En la demo, las consultas se escriben **exactamente** como están en `consultas_demo.txt`.
  Otra redacción es otra consulta y, sin internet, la app dirá que no está en caché.

## Qué se sube (PR `feat/J-12-cache-demo`)

```bash
git add outputs/cache/*.json outputs/fichas.jsonl outputs/reports/corrida_llm.md
git add outputs/reports/benchmark.md outputs/reports/latencia.md   # si corriste make eval
git diff --cached | grep -iE "sk-or|api_key" || echo "sin claves"  # tiene que decir "sin claves"
```

Pega en el PR el resumen de `outputs/reports/corrida_llm.md`: origen de cada llamada, afirmaciones que
pasaron el guard, latencia mediana y p95, tokens y costo. Esos números van a las páginas de Notion y al pitch.
