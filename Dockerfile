FROM python:3.12-slim

WORKDIR /app
ENV PORT=8080
COPY . .

# No third-party dependencies: the image only contains the standard library.
RUN python3 -m compileall -q nakedk pa_fetch.py

# /api/health 由 dashboard/server.py 提供；镜像默认 CMD 是 CLI，不监听端口，
# 故需由编排层把 CMD 覆盖为 dashboard 服务后该检查才会成功（见 deploy/INVENTORY.md）。
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/api/health', timeout=3)" || exit 1

ENTRYPOINT ["python3", "-m", "nakedk"]
CMD ["fetch", "BTCUSDT", "ETHUSDT"]
