FROM maikelwever/docker-archlinux
MAINTAINER Maikel Wever <maikelwever@gmail.com>

# Adding mirrorlist with Dutch servers for when I build locally
# Doesn't matter much on Docker Hub
ADD mirrorlist /etc/pacman.d/mirrorlist

RUN pacman -Syyu --needed --noconfirm base-devel sudo python-jinja git haveged procps-ng
RUN bash -c "echo 'y\ny\n' | pacman -Scc"

VOLUME /build

# Set up user & sudo
ADD sudoers /etc/sudoers
RUN useradd -d /home/pellets/ -m -G wheel build
RUN chmod 0400 /etc/sudoers

# Set up build output dir
RUN mkdir -p /home/pellets/
RUN mkdir -p /build/
RUN chown -R build:build /build
RUN chown -R build:build /home/pellets

# Copy over buildscript
ADD buildscript.py /opt/buildscript.py
WORKDIR /home/pellets/
USER build
ENTRYPOINT LC_ALL='en_US.utf8' /usr/bin/python3 /opt/buildscript.py
