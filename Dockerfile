FROM python:3.11.4-bullseye as builder

LABEL maintainer="NSGI <info@nsgi.nl>"

COPY . /src

# ignore pip warning about running pip as root - since we are in a containerized sandboxed environment anyways...
ENV ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /src

RUN pip install --upgrade setuptools && \
    pip install --upgrade pip && \
    pip install --upgrade build && \
    python -m build

WORKDIR /tifs

RUN curl -o nl_nsgi_nlgeo2018.tif https://cdn.proj.org/nl_nsgi_nlgeo2018.tif && \
    curl -o nl_nsgi_rdcorr2018.tif https://cdn.proj.org/nl_nsgi_rdcorr2018.tif && \
    curl -o nl_nsgi_rdtrans2018.tif https://cdn.proj.org/nl_nsgi_rdtrans2018.tif


FROM python:3.11.4-slim-bullseye as runner

ENV ENV PIP_ROOT_USER_ACTION=ignore

COPY --from=builder /src/dist/coordinate_transformation_api-2*.whl .

RUN pip install coordinate_transformation_api-2*.whl

COPY --from=builder /tifs/* /usr/local/lib/python3.11/site-packages/pyproj/proj_dir/share/proj

EXPOSE 8000
ENTRYPOINT [ "ct-api" ]
