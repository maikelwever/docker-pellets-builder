FROM logankoester/archlinux
MAINTAINER Maikel Wever <maikelwever@gmail.com>

# Adding mirrorlist with Dutch servers for when I build locally
# Doesn't matter much on Docker Hub
ADD mirrorlist /etc/pacman.d/mirrorlist

RUN pacman -Sy --noconfirm && \
    pacman -S archlinux-keyring --noconfirm

RUN pacman -Syyu --needed --noconfirm base-devel sudo python-jinja git

VOLUME /build
WORKDIR /build

# Set up user & sudo
ADD sudoers /etc/sudoers
RUN useradd -d /build -G wheel build && \
    chmod 0400 /etc/sudoers

# Set up build output dir
RUN mkdir /build/package_output
RUN mkdir /build/build_logs
RUN chown -R build:build /build

# Copy over buildscript
ADD buildscript.py /opt/buildscript.py
USER build
ENTRYPOINT sudo chown build: /build && \
           /usr/bin/python3 /opt/buildscript.py
