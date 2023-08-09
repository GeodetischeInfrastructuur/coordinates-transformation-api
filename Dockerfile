FROM python:3.11.4-slim-bullseye
LABEL maintainer="NSGI <info@nsgi.nl>"

COPY . /src

RUN apt-get update && \
    apt-get install -y \
        moreutils \
        curl && \
    pip install --upgrade setuptools && \
    pip install /src

# TODO: investigate how to properly setup Dockerfile for production use

RUN cd /usr/local/lib/python3.11/site-packages/pyproj/proj_dir/share/proj && \
    curl -o nl_nsgi_nlgeo2018.tif https://cdn.proj.org/nl_nsgi_nlgeo2018.tif && \
    curl -o nl_nsgi_rdcorr2018.tif https://cdn.proj.org/nl_nsgi_rdcorr2018.tif && \
    curl -o nl_nsgi_rdtrans2018.tif https://cdn.proj.org/nl_nsgi_rdtrans2018.tif

ENTRYPOINT [ "ct-api" ]
