FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV PYTHONPATH="/app:/app/src:/app/api"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DAGSTER_HOME=/app/dagster_home
RUN mkdir -p /app/dagster_home

EXPOSE 3000

# La commande d'origine qui fonctionne très bien sous 3.13
CMD ["dagster", "dev", "-f", "dagster/repository.py", "--host", "0.0.0.0", "--port", "3000"]
