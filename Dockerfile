FROM python:3.11.4-slim-bullseye
LABEL maintainer="NSGI <info@nsgi.nl>"

COPY . /src

RUN apt-get update && \
    apt-get install -y \
        moreutils && \
    pip install --upgrade setuptools && \
    pip install /src

# TODO: investigate how to properly setup Dockerfile for production use

ENTRYPOINT [ "ct-api" ]
