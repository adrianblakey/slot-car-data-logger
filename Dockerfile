# syntax=docker/dockerfile:1
#
# Slot Car Logger (Pico W) — MicroPython UF2 build
#
# Uses mattrmansfieldtx/micropython-builder:latest-rp2
# See: https://hub.docker.com/r/mattrmansfieldtx/micropython-builder
#
# The base image's entrypoint handles the full build using these env vars:
#   MPY_BOARD        — board to build for (required) — RPI_PICO_W here,
#                       NOT RPI_PICO2_W (this is the RP2040 Pico W reference,
#                       not the RP2350 Pico 2 W)
#   FIRMWARE_DEST    — output directory inside the container
#   FROZEN_MANIFEST  — path to a manifest.py for frozen modules (optional)
#
# We use the image as-is without overriding the entrypoint.
# All configuration is passed via -e flags in build.sh.

FROM mattrmansfieldtx/micropython-builder:latest-rp2
