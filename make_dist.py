#!/usr/bin/env python3
# Copyright @ 2026 Adrian Blakey. All rights reserved
# make_dist.py — build the device distribution from dist_manifest.py.
#
# Run on the host from the repo root:
#   python3 make_dist.py     build ./dist staging tree
#
# Then:  make deploy    (mpremote copies ./dist to the device)
#
# Simpler than the Pico 2 W reference's make_dist.py: this one only builds
# ./dist. The reference's --check/--emit-lib modes cross-reference a full
# import-graph reachability scanner (find_unused.py) that was not ported for
# this smaller project — dist_manifest.py is kept in sync with pico/src/ and
# pico/lib/ by hand instead.

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dist_manifest as M

DIST = "dist"


def build():
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    total = 0
    n = 0
    missing = []
    for repo, dev in M.all_files():
        if not os.path.isfile(repo):
            missing.append(repo)
            continue
        dst = os.path.join(DIST, dev)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(repo, dst)
        total += os.path.getsize(repo)
        n += 1
    for repo_dir, dev_dir in M.TREES:
        if not os.path.isdir(repo_dir):
            missing.append(repo_dir + "/")
            continue
        for base, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                srcp = os.path.join(base, f)
                rel = os.path.relpath(srcp, repo_dir)
                dst = os.path.join(DIST, dev_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(srcp, dst)
                total += os.path.getsize(srcp)
                n += 1
    print("dist/: {} files, {:.0f} KB".format(n, total / 1024))
    if missing:
        print("\nMANIFEST ERRORS — listed but not found in the repo:")
        for p in missing:
            print("  ", p)
        sys.exit(1)


if __name__ == "__main__":
    build()
