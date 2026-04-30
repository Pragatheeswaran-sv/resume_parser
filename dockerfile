# ---- Stage 1: Build dependencies ----
FROM python:3.13-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry

RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./

# Install CPU-only PyTorch first to avoid pulling ~8GB of CUDA/NVIDIA libraries
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN poetry install --no-root --no-interaction --no-ansi \
    && pip cache purge \
    && rm -rf /root/.cache /tmp/*

RUN pip install --no-cache-dir email-validator

# ---- Stage 2: Final runtime image ----
FROM python:3.13-slim

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends libreoffice-writer \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
