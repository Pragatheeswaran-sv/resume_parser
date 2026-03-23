FROM python:3.13-slim

WORKDIR /app

RUN pip install poetry

RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./

RUN poetry install --no-root --no-interaction --no-ansi

RUN pip install --no-cache-dir langchain==1.2.10 faiss-cpu sentence-transformers

# Copy src folder into /app
# COPY src /app
COPY . .


EXPOSE 8000

# Run FastAPI
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]