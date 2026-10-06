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

.PHONY: setup stub data nlp demo test eval

setup: ## Create .venv and install pinned requirements
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@test -f .env || cp .env.example .env
	@echo "Done. Next: make demo"

stub: ## Rebuild the synthetic stub (J-02)
	$(PY) data/stub/make_stub.py

data: ## Ingestion + validation (B-01..B-05)
	@echo "Pending B-01..B-05: src/ingest/*.py and src/validate.py have no entry point yet."

nlp: ## Embeddings, topics, provenance, clusters and baseline (B-06..B-09, B-11)
	@echo "Pending B-06..B-09: src/nlp/*.py have no entry point yet."

demo: ## Open the Streamlit app on the local snapshot (stub until B delivers)
	@test -f data/stub/noticias_stub.parquet || $(PY) data/stub/make_stub.py
	$(DEMO_ENV) $(PY) -m streamlit run app/streamlit_app.py

test: ## Run T01-T10 and contract tests
	$(PY) -m pytest tests/ -v -rs

eval: ## Run the benchmark and write outputs/reports/ (J-13, B-12)
	@echo "Pending J-13/B-12: src/eval/run_benchmark.py has no entry point yet."
