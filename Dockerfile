# Autonomous research daemon + dashboard API (Linux/VPS/Docker).
# Researches the Parquet lake offline -- no MetaTrader5 needed in the container.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY deploy/requirements-daemon.txt /app/deploy/requirements-daemon.txt
RUN pip install -r deploy/requirements-daemon.txt

COPY . /app

# Non-root for safety.
RUN useradd -m quant && chown -R quant:quant /app
USER quant

# Default: the never-stop supervisor. Override `command:` in compose for the API.
CMD ["python", "scripts/run_supervisor.py", "--workers", "3", \
     "--db", "data/sor_research.sqlite", "--lake", "data/lake"]
