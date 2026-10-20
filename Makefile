.PHONY: test demo signal score bootstrap dashboard clean

bootstrap:
	bash bootstrap.sh

test:
	python3 -m unittest discover -s tests -v
	python3 -m compileall -q nakedk pa_fetch.py

demo:
	python3 -m nakedk fetch BTCUSDT ETHUSDT

signal:
	python3 -m nakedk signal BTCUSDT ETHUSDT

score:
	python3 -m nakedk score signals.jsonl

clean:
	rm -rf __pycache__ nakedk/__pycache__ tests/__pycache__

dashboard:
	PYTHONPATH=. PORT=8080 python3 dashboard/server.py
