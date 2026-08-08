# syntax=docker/dockerfile:1
#
# Slot Car Logger BLE client (Flutter) — Android build
#
# Uses cirruslabs/docker-images-flutter, which bundles the Flutter SDK,
# a full Android SDK/NDK/build-tools, and pre-accepted SDK licenses in one
# self-contained, container-owned install.
# See: https://github.com/cirruslabs/docker-images-flutter
#
# Why this exists: building this app against the host's shared Android SDK
# at /opt/android-sdk (root-owned) needed three separate `sudo chown`
# passes (SDK root, ndk/, build-tools/+platforms/) to get `flutter build
# apk` working at all, plus a permission_handler_android version pin to
# dodge a compileSdk-37 naming mismatch (see README.md's "Flutter mobile
# app" section, and this project's pubspec.yaml dependency_overrides).
# None of that host-SDK wrangling is needed here — the image's SDK is
# already fully set up and owned by the container.
#
# `stable` tracks Flutter's stable channel, same channel the host install
# used when this app was last verified (Flutter 3.44.x at the time of
# writing). No exact patch-version tag is published for every host
# release, so this floats rather than pins — Flutter patch releases are
# backward compatible in practice, and build-android.sh's flutter analyze
# + flutter test steps catch anything that isn't.
FROM ghcr.io/cirruslabs/flutter:stable

WORKDIR /app
