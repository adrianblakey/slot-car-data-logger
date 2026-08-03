#!/bin/bash
# Copyright @ 2026 Adrian Blakey. All rights reserved
# build.sh — Slot Car Logger (Pico W) firmware builder
# Usage: ./build.sh [frozen|mpy]
#
# Run from the repository root (where Dockerfile and manifest.py live).

set -e
export DOCKER_BUILDKIT=1

RED='\033[0;31m'; GREEN='\033[0;32m'
YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

print_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

IMAGE_NAME="scl-pico-w-builder"
COMPILE_MODE="${1:-frozen}"
BOARD="RPI_PICO_W"   # RP2040 Pico W — NOT RPI_PICO2_W

show_usage() {
cat << EOF
Slot Car Logger (Pico W) — MicroPython Firmware Builder
=========================================================
Usage: $0 [MODE]

Modes:
  frozen   App code frozen into firmware (default). Single self-contained .uf2.
  mpy      Base firmware.uf2 + separate .mpy bytecode files copied after flash.

Examples:
  $0             # frozen mode
  $0 frozen
  $0 mpy
EOF
}

if [[ "$1" == "-h" || "$1" == "--help" ]]; then show_usage; exit 0; fi
if [[ "$COMPILE_MODE" != "frozen" && "$COMPILE_MODE" != "mpy" ]]; then
    print_error "Unknown mode: '$COMPILE_MODE'"; echo; show_usage; exit 1
fi

# ── Pre-flight ────────────────────────────────────────────────────────────────
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Start Docker Desktop and try again."
    exit 1
fi
if [ ! -f "Dockerfile" ]; then
    print_error "Dockerfile not found. Run from the repository root."
    exit 1
fi
if ! ls pico/*.py 1>/dev/null 2>&1 && ! ls pico/src/*.py 1>/dev/null 2>&1; then
    print_warning "No Python files found in pico/ or pico/src/."
    read -p "Continue? (y/n) " -n 1 -r; echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 1
fi

print_info "Board: $BOARD"
print_info "Mode:  $COMPILE_MODE"
echo ""

# ── Docker image ──────────────────────────────────────────────────────────────
if [[ "$(docker images -q $IMAGE_NAME 2>/dev/null)" == "" ]]; then
    print_info "Building Docker image '$IMAGE_NAME'..."
    docker build -t "$IMAGE_NAME" .
    print_success "Image built."
    echo ""
else
    print_info "Using existing image: $IMAGE_NAME"
    read -p "Rebuild image? (y/n) " -n 1 -r; echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker build --no-cache -t "$IMAGE_NAME" .
        print_success "Image rebuilt."
        echo ""
    fi
fi

# ── Prepare output and staging directories ────────────────────────────────────
mkdir -p output
STAGING_DIR="$(mktemp -d /tmp/mpy-build-XXXXXX)"
trap "rm -rf $STAGING_DIR" EXIT

# ── Prepare manifest and source files ────────────────────────────────────────
if [ "$COMPILE_MODE" = "frozen" ]; then

    if [ ! -f "manifest.py" ]; then
        print_error "manifest.py not found in repo root."
        print_error "This file lists which Python files to freeze into firmware."
        exit 1
    fi

    # The container mounts the repo at /app. Replace $(APP_DIR) accordingly.
    RESOLVED_MANIFEST="$STAGING_DIR/manifest.py"
    sed 's|\$(APP_DIR)|/app/pico|g' manifest.py > "$RESOLVED_MANIFEST"
    print_info "Manifest resolved (APP_DIR=/app/pico)"

    print_info "Starting frozen build..."
    echo ""

    docker run --rm \
        -e MPY_BOARD="$BOARD" \
        -e FIRMWARE_DEST="/app/output" \
        -e FROZEN_MANIFEST="/app/staging/manifest.py" \
        -v "$(pwd)":/app \
        -v "$STAGING_DIR":/app/staging \
        "$IMAGE_NAME"

else
    # ── MPY mode ──────────────────────────────────────────────────────────────
    print_info "Building base firmware (no frozen modules)..."
    echo ""

    docker run --rm \
        -e MPY_BOARD="$BOARD" \
        -e FIRMWARE_DEST="/app/output" \
        -v "$(pwd)":/app \
        "$IMAGE_NAME"

    print_info "Compiling .py files to .mpy bytecode..."

    docker run --rm \
        --entrypoint="" \
        -v "$(pwd)":/app \
        -v "$STAGING_DIR":/mpy_out \
        "$IMAGE_NAME" \
        sh -c '
            MPYCROSS=$(find / -name "mpy-cross" -type f 2>/dev/null | head -1)
            if [ -z "$MPYCROSS" ]; then echo "ERROR: mpy-cross not found"; exit 1; fi
            echo "mpy-cross: $MPYCROSS"
            for f in /app/pico/*.py /app/pico/src/*.py; do
                [ -f "$f" ] || continue
                base=$(basename "${f%.py}")
                echo "  $base.py -> $base.mpy"
                "$MPYCROSS" "$f" -o "/mpy_out/$base.mpy" 2>&1 || \
                    echo "  WARNING: failed to compile $base.py (skipping)"
            done
        '

    cp "$STAGING_DIR"/*.mpy output/ 2>/dev/null || true
    MPY_COUNT=$(ls output/*.mpy 2>/dev/null | wc -l)
    print_info "Compiled $MPY_COUNT .mpy files to output/"

    cat > output/INSTALL.txt << 'INSTALL'
INSTALLATION — mpy mode
=======================
1. Flash: hold BOOTSEL, connect USB, copy firmware.uf2 to the drive.
2. After reboot, copy bytecode:
   mpremote connect auto fs cp *.mpy :
INSTALL
fi

# ── Results ───────────────────────────────────────────────────────────────────
echo ""
if [ -f "output/firmware.uf2" ]; then
    print_success "Build complete!"
    echo ""
    print_info "Output files:"
    ls -lh output/
    echo ""
    if [ "$COMPILE_MODE" = "frozen" ]; then
        echo -e "${GREEN}Next steps:${NC}"
        echo "  1. Hold BOOTSEL on the Pico W, connect USB, release BOOTSEL."
        echo "  2. Copy output/firmware.uf2 to the USB drive."
        echo "  3. Device reboots and runs your application automatically."
    else
        echo -e "${GREEN}Next steps:${NC}"
        echo "  1. Flash output/firmware.uf2 via BOOTSEL."
        echo "  2. cd output && mpremote connect auto fs cp *.mpy :"
    fi
else
    print_error "firmware.uf2 not found — build failed."
    exit 1
fi
