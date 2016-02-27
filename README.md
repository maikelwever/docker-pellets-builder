This Docker container is intended for use with AutoAURBuilder.

It is basically a fork of tazjin/arch-pkgbuild, with a script added which
picks up environment variables set by the buildserver via docker.

Usage:

`docker run --rm -v $(pwd):/build maikelwever/arch-pkgbuild`


What follows is the original README.


This container is intended for building Arch Linux packages in an isolated environment. The container itself has the `base` and `base-devel` package groups installed and runs `makepkg -sfc` from the `/build` directory when launched.

The command is run by a `build` user with UID 1000, it will `chown` the contents of the `/build` directory to it. The reason for this is that `makepkg` can no longer be run as root. Make sure to check and potentially fix file permissions in the build folder after running this container.

To use this container `cd` into a folder containing a `PKGBUILD` and run like this:

`docker run --rm -v $(pwd):/build tazjin/arch-pkgbuild`

This image is available as an automated build from [Docker Hub](https://registry.hub.docker.com/u/tazjin/arch-pkgbuild/)
