# syntax=docker/dockerfile:1.7
FROM python:3.14-slim-bookworm

ARG DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        cron \
        curl \
        git \
        openssh-server \
        supervisor \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh \
    && mkdir -p /var/run/sshd

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
