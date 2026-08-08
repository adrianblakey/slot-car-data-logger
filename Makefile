# Copyright @ 2026 Adrian Blakey. All rights reserved
# Makefile — helpers for the Slot Car Logger (Pico W)
#
# Run from the REPOSITORY ROOT (where this file lives).
#
# Device port — override if mpremote can't auto-detect:
#   make deploy DEVICE=/dev/tty.usbmodem1101   # macOS
#   make deploy DEVICE=/dev/ttyACM0            # Linux
#   make deploy DEVICE=COM3                    # Windows
#
# Typical workflow after a firmware build:
#   1. Flash output/firmware.uf2 via BOOTSEL (manual drag-and-drop)
#   2. Copy conf/wifi.json.example to conf/wifi.json and fill in real creds
#   3. make deploy           — build ./dist and copy it to the device
#   4. make host-test        — run unit tests on this machine

DEVICE   ?= auto
PICO_DIR := pico
SRC_DIR  := $(PICO_DIR)/src
TEST_DIR := $(PICO_DIR)/tests

.PHONY: dist deploy sync host-test device-test test clean help

help:
	@echo "Slot Car Logger (Pico W) — make targets"
	@echo ""
	@echo "  dist         Build ./dist from dist_manifest.py"
	@echo "  deploy       Build ./dist and copy it to the device"
	@echo "               (creates src/lib/conf/static/data/syslog on a blank fs)"
	@echo "  sync         Copy src/ and tests/ to device (subset of deploy)"
	@echo "  host-test    Run unit tests on this machine (no device needed)"
	@echo "  device-test  Run unit tests on the Pico via mpremote"
	@echo "  test         Run both host-test and device-test"
	@echo "  clean        Remove src/, tests/, lib/, static/, conf/ from the device"
	@echo ""
	@echo "  DEVICE=auto  Override with e.g. DEVICE=/dev/tty.usbmodem1101"

# ── dist: explicit-manifest distribution ────────────────────────────────────
dist:
	python3 make_dist.py

# ── deploy: manifest distribution to the device ─────────────────────────────
# Works from a COMPLETELY BLANK filesystem: top-level directories are
# created first (mpremote cp -r needs the target's parent to exist), and
# data/syslog are created for the first boot's flash session/log writer.
deploy: dist
	@echo "Deploying manifest distribution to Pico..."
	@echo ""
	@echo "  Creating device directories (safe if they already exist)..."
	mpremote connect $(DEVICE) mkdir :src    || true
	mpremote connect $(DEVICE) mkdir :lib    || true
	mpremote connect $(DEVICE) mkdir :conf   || true
	mpremote connect $(DEVICE) mkdir :static || true
	mpremote connect $(DEVICE) mkdir :data   || true
	mpremote connect $(DEVICE) mkdir :syslog || true
	@echo "  Copying root files..."
	mpremote connect $(DEVICE) fs cp dist/main.py :main.py
	mpremote connect $(DEVICE) fs cp dist/boot.py :boot.py
	@echo "  Copying src/ ..."
	mpremote connect $(DEVICE) fs cp -r dist/src    :
	@echo "  Copying lib/ ..."
	mpremote connect $(DEVICE) fs cp -r dist/lib    :
	@echo "  Copying conf/ ..."
	mpremote connect $(DEVICE) fs cp -r dist/conf   :
	@echo "  Copying static/ ..."
	mpremote connect $(DEVICE) fs cp -r dist/static :
	@echo ""
	@echo "Deploy complete. Soft-reboot the device to start the application."
	@echo "  (Press Ctrl-D in the REPL, or: mpremote connect $(DEVICE) reset)"
	@echo ""
	@echo "  If conf/wifi.json wasn't deployed (gitignored), copy"
	@echo "  conf/wifi.json.example -> conf/wifi.json with real credentials"
	@echo "  first, or use mpremote to create it directly on the device."

# ── sync: copy src/ and tests/ to the device ────────────────────────────────
# `cp -r LOCALDIR :src` when :src already exists (true for any device past
# its first deploy) nests into :src/src/* instead of overwriting :src/* —
# confirmed on hardware chasing a "my redeployed code isn't running" bug.
# Match deploy's already-correct pattern: cp -r into the PARENT (:), letting
# the local dir's own basename (src/tests) become the top-level name.
sync:
	@echo "Syncing source and tests to Pico..."
	mpremote connect $(DEVICE) fs cp -r $(SRC_DIR)  :
	mpremote connect $(DEVICE) fs cp -r $(TEST_DIR) :
	@echo "Sync complete."

# ── host-test: run test suite on this machine (no device needed) ───────────
host-test:
	@echo "Running host tests (CPython + mocks)..."
	python3 $(TEST_DIR)/run_tests.py
	@echo "Host tests complete."

# ── device-test: sync then run tests on the Pico via mpremote ──────────────
device-test: sync
	@echo "Running tests on Pico..."
	mpremote connect $(DEVICE) run $(TEST_DIR)/test_log_record.py
	@echo "Device tests complete."

test: host-test device-test

# ── clean: remove app files from the device ─────────────────────────────────
clean:
	@echo "Removing src/, tests/, lib/, static/, conf/ from device..."
	mpremote connect $(DEVICE) fs rm -r :src    || true
	mpremote connect $(DEVICE) fs rm -r :tests  || true
	mpremote connect $(DEVICE) fs rm -r :lib    || true
	mpremote connect $(DEVICE) fs rm -r :static || true
	mpremote connect $(DEVICE) fs rm -r :conf   || true
	@echo "Clean complete."
