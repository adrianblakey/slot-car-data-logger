#!/bin/bash
# Copyright @ 2026 Adrian Blakey. All rights reserved
# build-android.sh — Slot Car Logger BLE client, Android build (Docker)
# Usage: ./build-android.sh [debug|release]
#
# Run from app/ (where Dockerfile and pubspec.yaml live).

set -e
export DOCKER_BUILDKIT=1

RED='\033[0;31m'; GREEN='\033[0;32m'
YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

print_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

IMAGE_NAME="scl-flutter-android-builder"
BUILD_MODE="${1:-debug}"

show_usage() {
cat << EOF
Slot Car Logger BLE Client — Android Build (Docker)
=====================================================
Usage: $0 [MODE]

Modes:
  debug     Debug APK, faster build, larger binary (default).
  release   Release APK. Signed with the default debug keystore (see
            android/app/build.gradle.kts's signingConfig comment) —
            fine for sideloading onto your own phone, not for a store
            listing.

Examples:
  $0             # debug
  $0 debug
  $0 release

Output: build-out/app-<mode>.apk
EOF
}

if [[ "$1" == "-h" || "$1" == "--help" ]]; then show_usage; exit 0; fi
if [[ "$BUILD_MODE" != "debug" && "$BUILD_MODE" != "release" ]]; then
    print_error "Unknown mode: '$BUILD_MODE'"; echo; show_usage; exit 1
fi

# ── Pre-flight ────────────────────────────────────────────────────────────────
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Start Docker and try again."
    exit 1
fi
if [ ! -f "Dockerfile" ] || [ ! -f "pubspec.yaml" ]; then
    print_error "Dockerfile/pubspec.yaml not found. Run this from app/ (the Flutter project root)."
    exit 1
fi

print_info "Mode: $BUILD_MODE"
echo ""

# ── Docker image ──────────────────────────────────────────────────────────────
if [[ "$(docker images -q $IMAGE_NAME 2>/dev/null)" == "" ]]; then
    print_info "Building Docker image '$IMAGE_NAME' (first run pulls the Flutter+Android SDK base image — several GB)..."
    docker build -t "$IMAGE_NAME" .
    print_success "Image built."
    echo ""
else
    print_info "Using existing image: $IMAGE_NAME"
    # Skip the prompt when there's no terminal attached (CI, backgrounded
    # runs) — `read` hits EOF immediately there, and under `set -e` that
    # non-zero exit silently kills the whole script before the build ever
    # runs. Default to reusing the existing image in that case.
    if [[ -t 0 ]]; then
        read -p "Rebuild image? (y/n) " -n 1 -r; echo
    else
        REPLY="n"
    fi
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker build --no-cache -t "$IMAGE_NAME" .
        print_success "Image rebuilt."
        echo ""
    fi
fi

# ── Prepare output directory ───────────────────────────────────────────────────
mkdir -p build-out
# The container runs Flutter/Gradle as root, so a file it writes into this
# bind-mounted dir comes out root-owned on the host. World-writable (no
# sticky bit) still lets you delete/overwrite it on the next run without
# sudo — same reasoning as the Pico firmware build.sh's `chmod a+rwx output`.
chmod a+rwx build-out

# ── Build ───────────────────────────────────────────────────────────────────────
print_info "Running flutter pub get, analyze, test, and build apk --$BUILD_MODE..."
echo ""

docker run --rm \
    -v "$(pwd)":/app \
    -v "$(pwd)/build-out":/build-out \
    "$IMAGE_NAME" \
    bash -c "
        set -e
        flutter pub get
        flutter analyze
        flutter test
        flutter build apk --$BUILD_MODE
        cp build/app/outputs/flutter-apk/app-$BUILD_MODE.apk /build-out/
    "

# ── Results ───────────────────────────────────────────────────────────────────────
echo ""
if [ -f "build-out/app-$BUILD_MODE.apk" ]; then
    print_success "Build complete!"
    echo ""
    print_info "Output:"
    ls -lh "build-out/app-$BUILD_MODE.apk"
    echo ""
    echo -e "${GREEN}Next steps:${NC}"
    echo "  adb install build-out/app-$BUILD_MODE.apk"
else
    print_error "app-$BUILD_MODE.apk not found — build failed."
    exit 1
fi
