FROM python:3.11.4-bullseye as builder

ARG NSGI_PROJ_DB_VERSION="1.0.0"

LABEL maintainer="NSGI <info@nsgi.nl>"

COPY . /src

# ignore pip warning about running pip as root - since we are in a containerized sandboxed environment anyways...
ENV ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /src

RUN apt update && apt install jq curl -y

RUN pip install --upgrade setuptools && \
    pip install --upgrade pip && \
    pip install --upgrade build && \
    python -m build

WORKDIR /assets

RUN curl -o nl_nsgi_nlgeo2018.tif https://cdn.proj.org/nl_nsgi_nlgeo2018.tif && \
    curl -o nl_nsgi_rdcorr2018.tif https://cdn.proj.org/nl_nsgi_rdcorr2018.tif && \
    curl -o nl_nsgi_rdtrans2018.tif https://cdn.proj.org/nl_nsgi_rdtrans2018.tif

RUN curl -sL -H "Accept: application/octet-stream" $(curl -s "https://api.github.com/repos/GeodetischeInfrastructuur/transformations/releases/tags/${NSGI_PROJ_DB_VERSION}" | jq -r '.assets[] | select(.name=="proj.db").url') -o proj.db


FROM python:3.11.4-slim-bullseye as runner

ENV ENV PIP_ROOT_USER_ACTION=ignore

COPY --from=builder /src/dist/coordinate_transformation_api-2*.whl .

RUN pip install coordinate_transformation_api-2*.whl

COPY --from=builder /assets/*.tif /usr/local/lib/python3.11/site-packages/pyproj/proj_dir/share/proj
COPY --from=builder /assets/proj.db /usr/local/lib/python3.11/site-packages/pyproj/proj_dir/share/proj/proj.db

EXPOSE 8000
ENTRYPOINT [ "ct-api" ]
