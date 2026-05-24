# Stage 1: Build environment
FROM python:3.14-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip pipenv

# Create the virtual environment directly inside the project directory (/app/.venv)
ENV PIPENV_VENV_IN_PROJECT=1

COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy

# Stage 2: Runtime environment
FROM python:3.14-slim

ARG APP_VERSION=unknown

# Apply metadata labels to the image for easier management and tracking
LABEL version="${APP_VERSION}" \
    description="Telegram bot for monitoring"

# Set runtime environment variables:
# 1. Prevent Python from writing .pyc files
# 2. Unbuffer output for immediate log streaming
# 3. Add virtual environment to PATH
# 4. Make the version available to the application at runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    APP_VERSION="${APP_VERSION}"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv

COPY . .

CMD ["sh", "-c", "alembic -c alembic/alembic.ini upgrade head && python -m src.main"]
