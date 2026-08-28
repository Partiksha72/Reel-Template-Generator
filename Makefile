.PHONY: setup api web e2e clean

setup:
	cd backend && python3 -m venv .venv
	cd backend && .venv/bin/pip install -r requirements.txt
	cd backend && .venv/bin/python scripts/generate_music.py
	cd backend && .venv/bin/python scripts/generate_watermark.py
	cd frontend && npm install

api:
	cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

web:
	cd frontend && npm run dev

e2e:
	cd backend && .venv/bin/python scripts/dev_e2e_check.py

clean:
	rm -rf data tmp_test backend/work
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
