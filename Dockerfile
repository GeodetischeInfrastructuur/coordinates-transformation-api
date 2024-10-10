ARG PYTHON_VERSION=3.12

FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS builder

ARG PYTHON_VERSION
ARG NSGI_PROJ_DB_VERSION="1.2.1"

LABEL maintainer="NSGI <info@nsgi.nl>"


RUN apt-get update && \
    apt-get install -y jq \
    curl \
    git && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*


WORKDIR /src_app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python${PYTHON_VERSION} \
    UV_PROJECT_ENVIRONMENT=/app


# split install of dependencies and application in two
# for improved caching
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-editable

COPY . /src_app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable

WORKDIR /app/lib/python${PYTHON_VERSION}/site-packages/pyproj/proj_dir/share/proj/

RUN curl -sL -o nl_nsgi_nlgeo2018.tif https://cdn.proj.org/nl_nsgi_nlgeo2018.tif && \
    curl -sL -o nl_nsgi_rdcorr2018.tif https://cdn.proj.org/nl_nsgi_rdcorr2018.tif && \
    curl -sL -o nl_nsgi_rdtrans2018.tif https://cdn.proj.org/nl_nsgi_rdtrans2018.tif && \
    curl -sL -H "Accept: application/octet-stream" $(curl -s "https://api.github.com/repos/GeodetischeInfrastructuur/transformations/releases/tags/${NSGI_PROJ_DB_VERSION}" | jq -r '.assets[] | select(.name=="bq_nsgi_bongeo2004.tif").url') -o bq_nsgi_bongeo2004.tif && \
    curl -sL -H "Accept: application/octet-stream" $(curl -s "https://api.github.com/repos/GeodetischeInfrastructuur/transformations/releases/tags/${NSGI_PROJ_DB_VERSION}" | jq -r '.assets[] | select(.name=="nllat2018.gtx").url') -o nllat2018.gtx && \
    curl -sL -H "Accept: application/octet-stream" $(curl -s "https://api.github.com/repos/GeodetischeInfrastructuur/transformations/releases/tags/${NSGI_PROJ_DB_VERSION}" | jq -r '.assets[] | select(.name=="proj.time.dependent.transformations.db").url') -o proj.db



FROM python:${PYTHON_VERSION}-slim-bookworm AS runner
ARG PYTHON_VERSION

RUN groupadd -r app && \
    useradd -r -d /app -g app -N app

# copy build venv folder (/app) from build stage


# COPY --from=builder /assets/*.tif /app/.venv/lib/python${PYTHON_VERSION}/site-packages/pyproj/proj_dir/share/proj/
# COPY --from=builder /assets/*.gtx /app/.venv/lib/python${PYTHON_VERSION}/site-packages/pyproj/proj_dir/share/proj/
# COPY --from=builder /assets/proj.db /app/.venv/lib/python${PYTHON_VERSION}/site-packages/pyproj/proj_dir/share/proj/proj.db


COPY --from=builder --chown=app:app --chmod=555 /app /app

# Place executables in the environment at the front of the path
ENV PATH="/app/bin:$PATH"
ENV PROJ_DIR="/app/lib/python${PYTHON_VERSION}/site-packages/pyproj/proj_dir/share/proj"
USER app
WORKDIR /app

# PORT for serving out API
EXPOSE 8000
# PORT for exposing health endpoints
EXPOSE 8001

ENTRYPOINT [ "ct-api" ]

