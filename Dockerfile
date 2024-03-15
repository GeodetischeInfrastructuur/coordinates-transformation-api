FROM python:3.11.8-bullseye as builder

ARG NSGI_PROJ_DB_VERSION="1.2.0"

LABEL maintainer="NSGI <info@nsgi.nl>"

COPY . /src

# ignore pip warning about running pip as root - since we are in a containerized sandboxed environment anyways...
ENV ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /src

RUN apt-get update && apt-get install jq curl -y

RUN rm -f dist/*

RUN pip install --upgrade setuptools && \
    pip install --upgrade pip && \
    pip install --upgrade build && \
    python -m build

WORKDIR /assets

RUN curl -sL -o nl_nsgi_nlgeo2018.tif https://cdn.proj.org/nl_nsgi_nlgeo2018.tif && \
    curl -sL -o nl_nsgi_rdcorr2018.tif https://cdn.proj.org/nl_nsgi_rdcorr2018.tif && \
    curl -sL -o nl_nsgi_rdtrans2018.tif https://cdn.proj.org/nl_nsgi_rdtrans2018.tif && \
    curl -sL -H "Accept: application/octet-stream" $(curl -s "https://api.github.com/repos/GeodetischeInfrastructuur/transformations/releases/tags/${NSGI_PROJ_DB_VERSION}" | jq -r '.assets[] | select(.name=="bq_nsgi_bongeo2004.tif").url') -o bq_nsgi_bongeo2004.tif && \
    curl -sL -H "Accept: application/octet-stream" $(curl -s "https://api.github.com/repos/GeodetischeInfrastructuur/transformations/releases/tags/${NSGI_PROJ_DB_VERSION}" | jq -r '.assets[] | select(.name=="nllat2018.gtx").url') -o nllat2018.gtx && \
    curl -sL -H "Accept: application/octet-stream" $(curl -s "https://api.github.com/repos/GeodetischeInfrastructuur/transformations/releases/tags/${NSGI_PROJ_DB_VERSION}" | jq -r '.assets[] | select(.name=="proj.time.dependent.transformations.db").url') -o proj.db

RUN ls -lah /src/dist/ >&2

FROM python:3.11.8-slim-bullseye as runner

ENV ENV PIP_ROOT_USER_ACTION=ignore

COPY --from=builder /src/dist/coordinate_transformation_api-2*.whl .

RUN pip install coordinate_transformation_api-2*.whl

COPY --from=builder /assets/*.tif /usr/local/lib/python3.11/site-packages/pyproj/proj_dir/share/proj/
COPY --from=builder /assets/*.gtx /usr/local/lib/python3.11/site-packages/pyproj/proj_dir/share/proj/
COPY --from=builder /assets/proj.db /usr/local/lib/python3.11/site-packages/pyproj/proj_dir/share/proj/proj.db

# PORT for serving out API
EXPOSE 8000
# PORT for exposing health endpoints
EXPOSE 8001

ENTRYPOINT [ "ct-api" ]


