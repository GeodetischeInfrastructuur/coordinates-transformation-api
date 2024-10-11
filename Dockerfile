ARG PYTHON_VERSION=3.12

FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS builder

ARG PYTHON_VERSION
ARG NSGI_PROJ_DB_VERSION="2.0.0"

LABEL maintainer="NSGI <info@nsgi.nl>"

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    jq=1.6-2.1 \
    curl=7.88.1-10+deb12u7 \
    git=1:2.39.5-0+deb12u1 && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python${PYTHON_VERSION} \
    UV_PROJECT_ENVIRONMENT=/app

WORKDIR /src_app
# split install of dependencies and application in two
# for improved caching
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-editable

COPY . /src_app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable

WORKDIR /app/lib/python${PYTHON_VERSION}/site-packages/pyproj/proj_dir/share/proj/

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# install grid and modified proj.db with NSGI CRS definitions
RUN curl -sL -o nl_nsgi_nlgeo2018.tif https://cdn.proj.org/nl_nsgi_nlgeo2018.tif && \
    curl -sL -o nl_nsgi_rdcorr2018.tif https://cdn.proj.org/nl_nsgi_rdcorr2018.tif && \
    curl -sL -o nl_nsgi_rdtrans2018.tif https://cdn.proj.org/nl_nsgi_rdtrans2018.tif && \
    release_url="https://api.github.com/repos/GeodetischeInfrastructuur/transformations/releases/tags/${NSGI_PROJ_DB_VERSION}" && \
    curl -sL -H "Accept: application/octet-stream" \
    "$(curl -s "$release_url" | jq -r '.assets[] | select(.name=="bq_nsgi_bongeo2004.tif").url')" -o bq_nsgi_bongeo2004.tif && \
    curl -sL -H "Accept: application/octet-stream" \
    "$(curl -s "$release_url" | jq -r '.assets[] | select(.name=="nllat2018.gtx").url')" -o nllat2018.gtx && \
    curl -sL -H "Accept: application/octet-stream" \
    "$(curl -s "$release_url" | jq -r '.assets[] | select(.name=="proj.time.dependent.transformations.db").url')" -o proj.db

FROM python:${PYTHON_VERSION}-slim-bookworm AS runner
ARG PYTHON_VERSION
RUN groupadd -r app && \
    useradd -r -d /app -g app -N app
COPY --from=builder --chown=app:app --chmod=555 /app /app

# Place executables in the environment at the front of the path
ENV PATH="/app/bin:$PATH"
ENV PROJ_DATA="/app/lib/python${PYTHON_VERSION}/site-packages/pyproj/proj_dir/share/proj"

USER app
WORKDIR /app

# PORT for serving out API
EXPOSE 8000
# PORT for exposing health endpoints
EXPOSE 8001

ENTRYPOINT [ "ct-api" ]
