# make help
PY := .venv/bin/python

.PHONY: help dev api setup load ingest test selftest pipelines schema compose-config drafts patch review review-apply e2e prewarm-plan warm tour chat-eval chat-eval-gemini
help:            ## list targets
	@grep -E '^[a-z-]+:.*## ' Makefile | sed 's/:.*## /\t/'
dev:             ## venv + DB + RAG + API :8000 + web :5173 (scripts/dev.sh)
	scripts/dev.sh
api:             ## API only, no reload of data
	scripts/dev.sh --no-web --no-load
setup:           ## create .venv (Python 3.12 or 3.11) and install requirements
	test -x $(PY) || $$(command -v python3.12 || command -v python3.11 || command -v python3) -m venv .venv
	$(PY) -m pip install -q -r requirements.txt
load:            ## load ontology, research and public data into DATABASE_URL
	$(PY) -m db.load
ingest:          ## embed the RAG corpus
	$(PY) -m rag.ingest
warm:            ## prebuild the season preview cache (data/cache) and load/download the RAG embedder
	$(PY) -m sim.warm
	$(PY) -m rag.embed --warm
test:            ## all tests (API/DB/RAG/LLM + sim + workbook), mock LLM, temp SQLite
	$(PY) -m pytest tests sim/tests research/tests -q
selftest:        ## loader selftest (temp DB, loaded twice)
	$(PY) -m db.load --selftest
pipelines:       ## refresh public data (needs SEOUL_API_KEY)
	$(PY) -m pipelines.run_all
schema:          ## regenerate db/schema.sql from db/models.py
	$(PY) -m db.schema_sql
compose-config:  ## validate docker-compose.yml without starting anything
	docker compose config -q && echo ok
tour:            ## welcome tour data: web/public/data/tour.json + engines/_shared/ui/tour.json (sim + ontology)
	$(PY) -m sim.tour
drafts:          ## AI guesstimate drafts (mock) for every confidence-L criterion -> research/review/ai_drafts.csv
	$(PY) -m agents.guesstimate --all-low-confidence
patch:           ## reviewed + accept=Y drafts -> research/review/accepted_patch.yaml
	$(PY) -m agents.guesstimate --apply-reviewed
review:          ## dry run of the Google review sheet (Team 1 고깃집 검토표): what would change, refused rows
	$(PY) research/sync_review_sheet.py
review-apply:    ## apply reviewed sheet rows: accepted_patch.yaml + build_workbook --apply-patch, stamp 반영됨
	$(PY) research/sync_review_sheet.py --apply --stamp
e2e:             ## headless: start API + web, play one month + owner chat via Playwright, stop everything
	scripts/e2e.sh
chat-eval:       ## owner-chat accuracy eval on the mock backend (offline; answers + retrieval hit@k with the e5 index)
	$(PY) -m tests.chat_eval.run
chat-eval-gemini: ## opt-in: the same eval on the Gemini free tier (one call per question, spaced)
	scripts/chat_eval_gemini.sh
prewarm-plan:    ## owner-chat pre-warm plan (dry run; never sends)
	$(PY) -m agents.prewarm --dry-run
