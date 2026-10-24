# Context is deploy/fly/build, staged by deploy/stage_fly.py (server code + game library + summaries).
FROM python:3.12-slim
WORKDIR /app
COPY . /app
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "-X", "utf8", "server/app.py", "--public", "--host", "0.0.0.0", "--port", "8080"]
