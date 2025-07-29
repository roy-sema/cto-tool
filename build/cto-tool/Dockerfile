FROM ubuntu:24.04 AS builder

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

COPY ./build/cto-tool/builder_deb_requirements.txt /app/build/cto-tool/builder_deb_requirements.txt
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
    apt-get -yqq update && \
    xargs -a ./build/cto-tool/builder_deb_requirements.txt -L1 apt-get -yqq --no-install-recommends install && \
    apt-get -yqq clean

RUN curl -o /tmp/docker.tgz https://download.docker.com/linux/static/stable/x86_64/docker-28.3.2.tgz \
    && tar -xzvf /tmp/docker.tgz -C /tmp \
    && cp /tmp/docker/* /usr/local/bin \
    && rm -rf /tmp/docker.tgz /tmp/docker

RUN mkdir -p ~/.docker/cli-plugins \
    && curl -SL https://github.com/docker/compose/releases/download/v2.38.2/docker-compose-linux-x86_64 -o ~/.docker/cli-plugins/docker-compose \
    && chmod +x ~/.docker/cli-plugins/docker-compose

COPY ./deployments ./deployments
COPY ./build ./build

FROM node:20-bookworm-slim AS vue-frontend

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

COPY ./build/cto-tool/vue-frontend_deb_requirements.txt /app/build/cto-tool/vue-frontend_deb_requirements.txt
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
    apt-get -yqq update && \
    xargs -a ./build/cto-tool/vue-frontend_deb_requirements.txt -L1 apt-get -yqq --no-install-recommends install && \
    apt-get -yqq clean

COPY \
    ./vue-frontend/package.json \
    ./vue-frontend/package-lock.json \
    ./vue-frontend/tsconfig.json \
    ./vue-frontend/tsconfig.app.json \
    ./vue-frontend/tsconfig.node.json \
    ./vue-frontend/tsconfig.vitest.json \
    /app/
RUN --mount=target=/root/.npm,type=cache,sharing=locked \
    npm ci

COPY ./vue-frontend .
RUN npm run build

CMD [ "npm","run", "dev", "--", "--host", "0.0.0.0" ]
EXPOSE 5173

FROM python:3.13.5-slim-bookworm AS cto-tool

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=100
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_CACHE_DIR=/opt/.cache
ENV UV_NO_SYNC=1
ENV UV_LOCKED=1
ENV PATH="/app/.venv/bin:$PATH"
ENV DEBIAN_FRONTEND=noninteractive

COPY ./build/cto-tool/cto-tool_deb_requirements.txt /app/build/cto-tool/cto-tool_deb_requirements.txt
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
    apt-get -yqq update && \
    xargs -a ./build/cto-tool/cto-tool_deb_requirements.txt -L1 apt-get -yqq --no-install-recommends install && \
    apt-get -yqq clean

RUN pip install -q uv

COPY uv.lock pyproject.toml ./
RUN --mount=target=/opt/.cache,type=cache,sharing=locked \
    uv sync --locked --all-groups

COPY . .
RUN chmod +x /app/build/cto-tool/entrypoint.sh /app/build/cto-tool/run.sh

COPY --from=vue-frontend /mvp/static/vue /app/mvp/static/vue

ENTRYPOINT [ "/app/build/cto-tool/entrypoint.sh" ]
CMD [ "/app/build/cto-tool/run.sh" ]
EXPOSE 8000
