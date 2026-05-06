# ---- Stage 1: Build dependencies ----
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry poetry-plugin-export && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./

RUN poetry export --without-hashes -f requirements.txt -o /tmp/reqs.txt && \
    pip install --no-cache-dir \
        -r /tmp/reqs.txt email-validator && \
    pip cache purge && \
    rm -rf /root/.cache /tmp/*

# ---- Stage 2: Final runtime image ----
FROM python:3.12-slim

RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends libreoffice-writer && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
