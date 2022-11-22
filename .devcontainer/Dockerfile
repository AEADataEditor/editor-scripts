# syntax=docker/dockerfile:1.2
ARG SRCVERSION=universal
ARG SRCTAG=2-linux
ARG SRCHUBID=mcr.microsoft.com/devcontainers

FROM ${SRCHUBID}/${SRCVERSION}

# The next parts need to be run as root ========================================== ROOT
USER root

# Install packages needed for aea-scripts
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y \
         curl \
         pandoc \
         wkhtmltopdf \
         openssh-server openssh-client


# install the AEA scripts into /usr/local/sbin
RUN git clone https://github.com/AEADataEditor/editor-scripts.git /usr/local/editor-scripts \
    && ln -s /usr/local/editor-scripts/aea* /usr/local/bin/ \
    && ln -s /usr/local/editor-scripts/stata1* /usr/local/bin \
    && ln -s /usr/local/editor-scripts/system-info* /usr/local/bin 

# Install rclone to get at Box and others

RUN curl https://rclone.org/install.sh | bash


RUN git config --global credential.helper store

