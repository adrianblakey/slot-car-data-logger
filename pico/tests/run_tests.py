#!/usr/bin/env python3
# Copyright @ 2026 Adrian Blakey. All rights reserved
# run_tests.py — host-side test runner (CPython + mocks, no device needed)
#
# Run from the repository root:
#   python3 pico/tests/run_tests.py
# or:
#   make host-test

import sys
import os
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))   # pico/tests/
PICO_DIR  = os.path.dirname(TESTS_DIR)                    # pico/
SRC_DIR   = os.path.join(PICO_DIR, "src")                 # pico/src/

for path in (SRC_DIR, TESTS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

names = sorted(
    os.path.splitext(f)[0]
    for f in os.listdir(TESTS_DIR)
    if f.startswith("test_") and f.endswith(".py")
)
suite = unittest.defaultTestLoader.loadTestsFromNames(names)

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

sys.exit(0 if result.wasSuccessful() else 1)
