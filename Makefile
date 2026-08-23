# intel-hub — ローカル開発タスク
# Windows で make が無い場合は README の PowerShell 手順を参照。

PY ?= python

.PHONY: setup test collect collect-fast collect-normal collect-slow score dev deploy db-init

setup:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest

collect:
	$(PY) -m scripts.run_collectors --tier all --sink sqlite

collect-fast:
	$(PY) -m scripts.run_collectors --tier fast

collect-normal:
	$(PY) -m scripts.run_collectors --tier normal

collect-slow:
	$(PY) -m scripts.run_collectors --tier slow

score:
	$(PY) -m scripts.rescore

dev:
	cd worker && npx wrangler dev

deploy:
	cd worker && npx wrangler deploy

db-init:
	cd worker && npx wrangler d1 execute intel-hub --remote --file=../db/schema.sql
