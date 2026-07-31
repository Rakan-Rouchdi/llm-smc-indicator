FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend /app/backend
COPY schemas /app/schemas

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir /app/backend

CMD ["sh", "-c", "exec uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port ${PORT:-8000}"]
