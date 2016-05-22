#!/usr/bin/python3
# encoding=utf8
# Buildscript for Arch packages
# Part of the Pellets buildsystem

from jinja2 import Template
from shlex import quote

import json
import logging
import os
import subprocess
import sys

logger = logging.getLogger('pellets-builder')
logger.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler()
stream_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

stream_handler.setFormatter(stream_formatter)
logger.addHandler(stream_handler)


DEFAULTS = {
    "packager": "Pellets <https://github.com/pellets>",
    "target_repository": "https://autoaurbuilder.grunnegers.nl/repository/autoaurbuilder2/",
    "target_repository_name": "autoaurbuilder2",

    "enable_multilib": False,
    "cpus": 1,

    "repositories": [],
    "mirrors": [
        "http://arch.apt-get.eu/$repo/os/$arch",
        "http://mirror.i3d.net/pub/archlinux/$repo/os/$arch",
        "http://mirror.23media.de/archlinux/$repo/os/$arch",
        "http://mirror.archlinux.ikoula.com/archlinux/$repo/os/$arch",
        "http://archlinux.cu.be/$repo/os/$arch",
    ],
    "keys_to_import": [],
    "packages_to_install": [],

    "git_remote": None,
    "git_commit": None,
}

PACMAN_CONF_TEMPLATE = Template("""# This config is generated by pellets-builder.
[options]
HoldPkg     = pacman glibc
Architecture = auto

[core]
Include = /etc/pacman.d/mirrorlist

[extra]
Include = /etc/pacman.d/mirrorlist

[community]
Include = /etc/pacman.d/mirrorlist

{% if enable_multilib %}
[multilib]
Include = /etc/pacman.d/mirrorlist
{% endif %}

[{{ target_repository_name }}]
SigLevel = Optional TrustAll
Server = {{ target_repository }}
""")

MAKEPKG_CONF_TEMPLATE = Template("""# This config is generated by pellets-builder
DLAGENTS=('ftp::/usr/bin/curl -fC - --ftp-pasv --retry 3 --retry-delay 3 -o %o %u'
          'http::/usr/bin/curl -fLC - --retry 3 --retry-delay 3 -o %o %u'
          'https::/usr/bin/curl -fLC - --retry 3 --retry-delay 3 -o %o %u'
          'rsync::/usr/bin/rsync --no-motd -z %u %o'
          'scp::/usr/bin/scp -C %u %o')

VCSCLIENTS=('bzr::bzr'
            'git::git'
            'hg::mercurial'
            'svn::subversion')

CARCH="x86_64"
CHOST="x86_64-unknown-linux-gnu"
CPPFLAGS="-D_FORTIFY_SOURCE=2"
CFLAGS="-march=x86-64 -mtune=generic -O2 -pipe -fstack-protector-strong"
CXXFLAGS="-march=x86-64 -mtune=generic -O2 -pipe -fstack-protector-strong"
LDFLAGS="-Wl,-O1,--sort-common,--as-needed,-z,relro"
MAKEFLAGS="-j{{ cpus }}"
DEBUG_CFLAGS="-g -fvar-tracking-assignments"
DEBUG_CXXFLAGS="-g -fvar-tracking-assignments"
BUILDENV=(!distcc color !ccache check !sign)
OPTIONS=(strip docs !libtool !staticlibs emptydirs zipman purge !upx !debug)
INTEGRITY_CHECK=(md5)
STRIP_BINARIES="--strip-all"
STRIP_SHARED="--strip-unneeded"
STRIP_STATIC="--strip-debug"
MAN_DIRS=({usr{,/local}{,/share},opt/*}/{man,info})
DOC_DIRS=(usr/{,local/}{,share/}{doc,gtk-doc} opt/*/{doc,gtk-doc})
PURGE_TARGETS=(usr/{,share}/info/dir .packlist *.pod)
PKGDEST=/build/package_output/
PACKAGER="{{ packager }}"
#GPGKEY=""
COMPRESSGZ=(gzip -c -f -n)
COMPRESSBZ2=(bzip2 -c -f)
COMPRESSXZ=(xz -c -z - --threads={{ cpus }})
COMPRESSLRZ=(lrzip -q)
COMPRESSLZO=(lzop -q)
COMPRESSZ=(compress -c -f)
PKGEXT='.pkg.tar.xz'
SRCEXT='.src.tar.gz'
""")


MIRRORLIST_TEMPLATE = Template("""# This config is generated by pellets-builder
{% for mirror in mirrors %}
Server = {{ mirror }}
{% endfor %}
""")


class CommandFailure(Exception):
    pass


def execute_command(commands, input=None, cwd=None):
    logger.debug("Executing command: %s", commands)
    process = subprocess.Popen(commands, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    stdout, stderr = process.communicate()
    logger.debug("Process exited with code %d", process.returncode)
    return process.returncode, stdout.decode(), stderr.decode()


class ExecutionWrapper:
    log_basedir = "/build/build_logs"

    def __init__(self, log_name, user='root', allow_failure=True):
        if not os.path.exists(self.log_basedir):
            execute_command('sudo mkdir -p {0}'.format(self.log_basedir))
            execute_command('sudo chown build:build {0}'.format(self.log_basedir))

        if not log_name.endswith('.log'):
            log_name += '.log'

        self.allow_failure = allow_failure
        self.log_name = os.path.join(self.log_basedir, log_name)
        self.user = user

    def __enter__(self):
        self.log_file = open(self.log_name, 'w')
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        if exception_type:
            self.log_file.write("Exception occured!")
            self.log_file.write(str(exception_type))
            self.log_file.write(str(exception_value))
            self.log_file.write(str(traceback))
        self.log_file.flush()
        self.log_file.close()

    def execute_command(self, commands, input=None, cwd=None):
        commands += ' 2>&1 | uniq'
        logger.debug("***********************************************-")
        logger.debug("*")
        logger.debug("*  Executing command: %s", commands)
        logger.debug("*")
        logger.debug("***********************************************-")
        process = subprocess.Popen(commands, shell=True, stdout=subprocess.PIPE,
                                   universal_newlines=True, stdin=subprocess.PIPE, cwd=cwd)
        if input:
            process.stdin.write(input)

        last_line = ""
        for line in process.stdout:
            if type(line) == bytes:
                line = bytes.decode('utf-8')

            if last_line != line:
                logger.info('%s', line.strip('\r').strip('\n'))
                last_line = line

        process.communicate()
        exitcode = process.returncode
        logger.debug("Process exited with code %d", exitcode)
        if not self.allow_failure and exitcode != 0:
            raise CommandFailure("Command failed, aborting...")


def prepare_environment(variables):
    logger.info("Initializing gpg")
    with ExecutionWrapper("gpg_setup") as e:
        e.execute_command('dirmngr < /dev/null')
        for key in variables['keys_to_import']:
            logger.info("Importing gpg key %s", key)
            e.execute_command('gpg --keyserver keys.gnupg.net --recv {0} 2>&1'.format(key))

    logger.info("Generating configfiles")
    with open('/tmp/pacman.conf', 'w') as f:
        f.write(PACMAN_CONF_TEMPLATE.render(**variables))

    with open('/tmp/makepkg.conf', 'w') as f:
        f.write(MAKEPKG_CONF_TEMPLATE.render(**variables))

    with ExecutionWrapper("environment_setup") as e:
        logger.info("Preparing environment")
        e.execute_command('sudo cp /tmp/pacman.conf /etc/pacman.conf')
        e.execute_command('sudo cp /tmp/makepkg.conf /etc/makepkg.conf')
        e.execute_command('sudo mkdir -p /build/package_output')
        e.execute_command('sudo chown build:build /build/package_output')

        logger.info("Updating system")
        e.execute_command('sudo pacman -Syyu --noconfirm --noprogress')

        if variables['packages_to_install']:
            logger.info("Installing dependencies")
            e.execute_command('yes | sudo pacman -S --noprogress --needed ' +
                              ' '.join(variables['packages_to_install']))


def build_package(variables):
    with ExecutionWrapper("makepkg", allow_failure=False) as e:
        logger.info("Cloning PKGBUILD repo")
        e.execute_command('git clone {0} "/home/pellets/package_output"'.format(
            quote(variables['git_remote'])
        ), cwd='/home/pellets/')

        logger.info("Checking out correct git commit")
        e.execute_command('git checkout {0}'.format(
            variables['git_commit']
        ), cwd='/home/pellets/package_output/')

        logger.info("Invoking makepkg")
        e.execute_command('SHELL=/bin/bash makepkg -sfc --noconfirm --needed --noprogress',
                          cwd='/home/pellets/package_output/')


def process_payload(payload):
    variables = {}
    variables.update(DEFAULTS)
    variables.update(payload)
    logger.debug(variables)

    prepare_environment(variables)
    build_package(variables)


def main(args):
    logger.info("Pellets-builder starting...")
    if len(args) > 0:
        decoded_payload = json.loads(args[0])
        process_payload(decoded_payload)
    else:
        logger.warning("No JSON payload on stdin found.")


if __name__ == "__main__":
    result = main(sys.argv[1:])
    if not result:
        sys.exit(0)
    else:
        try:
            sys.exit(int(result))
        except ValueError:
            sys.exit(1)
