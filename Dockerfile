FROM python:3.12-slim

WORKDIR /app
COPY . .

# No third-party dependencies: the image only contains the standard library.
RUN python3 -m compileall -q nakedk pa_fetch.py

ENTRYPOINT ["python3", "-m", "nakedk"]
CMD ["fetch", "BTCUSDT", "ETHUSDT"]
