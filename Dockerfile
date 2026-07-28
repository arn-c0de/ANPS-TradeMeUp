FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-docker.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-docker.txt

COPY . .

RUN chmod +x /app/scripts/docker/entrypoint.sh

# Run as an unprivileged user. logs/ and models/ are bind-mounted from the host,
# so APP_UID must match the owner of those directories or writes will fail.
# Override with: docker compose build --build-arg APP_UID=$(id -u)
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid "${APP_GID}" trademeup \
    && useradd --create-home --uid "${APP_UID}" --gid "${APP_GID}" trademeup \
    && mkdir -p /app/logs /app/models \
    && chown -R trademeup:trademeup /app
USER trademeup

EXPOSE 8000 8050

CMD ["/app/scripts/docker/entrypoint.sh", "api"]
