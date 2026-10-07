# Copiloto TVN · common commands (J-01). Owner: José.
# OFFLINE=1 make demo -> no network: LLM output is served only from outputs/cache/.

VENV   := .venv
PY     := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip
OFFLINE ?= 0

# Never send Streamlit telemetry; with OFFLINE=1 also block Hugging Face downloads.
DEMO_ENV := OFFLINE=$(OFFLINE) STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ifeq ($(OFFLINE),1)
DEMO_ENV += HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
endif

.PHONY: setup stub data news nlp verify demo test eval llm-check fichas

setup: ## Create .venv and install pinned requirements
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@test -f .env || cp .env.example .env
	@echo "Done. Next: make demo"

stub: ## Rebuild the synthetic stubs: news (J-02) and case cards for the UI
	$(PY) data/stub/make_stub.py
	$(PY) data/stub/make_fichas_stub.py

data: ## Download every source, then build and validate noticias.parquet (B-01..B-05); needs internet
	$(PY) -m src.ingest.worldbank
	$(PY) -m src.ingest.usgs
	$(PY) -m src.ingest.tvn_rss
	$(PY) -m src.ingest.gdelt --resume
	$(MAKE) news

news: ## Rebuild noticias.parquet + quality report from the stored raw snapshots (no network)
	$(PY) -m src.ingest.news

nlp: ## Embeddings, topics, provenance, clusters and baseline (B-06..B-09) on noticias.parquet
	$(PY) -m src.nlp.run

verify: ## Recompute every SHA-256 in data/manifest.json and compare (B-17); exit 1 on a mismatch
	$(PY) -m src.manifest --verify

demo: ## Open the Streamlit app on the local snapshot (stub until B delivers)
	@test -f data/stub/noticias_stub.parquet || $(PY) data/stub/make_stub.py
	$(DEMO_ENV) $(PY) -m streamlit run app/streamlit_app.py

test: ## Run T01-T10 and contract tests
	$(PY) -m pytest tests/ -v -rs

eval: ## Run the benchmark and write outputs/reports/ (J-13); OFFLINE=1 replays the cache
	OFFLINE=$(OFFLINE) $(PY) -m src.eval.run_benchmark

llm-check: ## One real LLM call on the stub (needs LLM_API_KEY in .env); result is cached (J-12)
	$(PY) -m src.generate.generate

fichas: ## Build outputs/fichas.jsonl for the top clusters (J-09); OFFLINE=1 uses only the cache
	OFFLINE=$(OFFLINE) $(PY) -m src.fichas --top $(or $(TOP),10)
