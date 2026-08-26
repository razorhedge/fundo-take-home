.PHONY: setup wait-db pipeline pipeline-full check check-fail check-fix measure clean reset-db

PYTHON ?= python3
export PYTHONPATH := src

setup:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pipeline init

wait-db:
	@echo "Waiting for Postgres..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do \
		$(PYTHON) -c "import psycopg; psycopg.connect('postgresql://fundo:fundo@localhost:5432/ops').close()" 2>/dev/null && exit 0; \
		sleep 1; \
	done; \
	echo "Postgres not ready"; exit 1

pipeline: wait-db
	$(PYTHON) -m pipeline pipeline

pipeline-full: wait-db
	$(PYTHON) -m pipeline pipeline --full

check: wait-db
	$(PYTHON) -m pipeline check

check-fail: wait-db
	$(PYTHON) -m pipeline break
	-$(PYTHON) -m pipeline check; \
	exit 0

check-fix: wait-db
	$(PYTHON) -m pipeline restore
	$(PYTHON) -m pipeline check

measure: wait-db
	$(PYTHON) -m pipeline measure

clean:
	rm -f data/warehouse.duckdb data/warehouse.duckdb.wal data/measurement.json

reset-db:
	docker compose down -v
	docker compose up -d
	$(MAKE) wait-db
