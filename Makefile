# Thin wrapper for Mac/Linux users. The real runner is tasks.py (works on Windows too).
PYTHON ?= python3

.PHONY: setup data train api app test lint backup

setup data train api app test lint backup:
	$(PYTHON) tasks.py $@
