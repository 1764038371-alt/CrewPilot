FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/app ./app
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/start.sh ./start.sh

RUN chmod +x ./start.sh

CMD ["./start.sh"]
