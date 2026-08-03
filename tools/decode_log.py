#!/usr/bin/env python3
# Copyright @ 2026 Adrian Blakey. All rights reserved
# tools/decode_log.py — decode a compact binary session log (see
# pico/src/log_record.py) to CSV, or load it as a pandas DataFrame.
#
# The device stores 8 bytes/record instead of CSV text (see the "Flash
# budget" section of the README for why) — this is the host-side tool that
# turns that back into something readable/analysable.
#
# Usage:
#   python3 tools/decode_log.py session_20260101_120000.bin
#   python3 tools/decode_log.py session_20260101_120000.bin -o session.csv
#   python3 tools/decode_log.py session_20260101_120000.bin --pandas

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pico', 'src'))
import log_record as lr


def iter_records(path):
    """Yields ('header', dict) once, then ('record', dict) per row."""
    with open(path, 'rb') as f:
        header = lr.read_header(f)
        yield ('header', header)
        while True:
            buf = f.read(lr.RECORD_SIZE)
            if len(buf) < lr.RECORD_SIZE:
                break
            yield ('record', lr.unpack_record(buf))


def to_csv(path, out):
    writer = csv.writer(out)
    t_ms = 0
    for kind, item in iter_records(path):
        if kind == 'header':
            for k, v in item['profile'].items():
                out.write('# {}={}\n'.format(k, v))
            out.write('# start_epoch={}\n'.format(item['start_epoch']))
            out.write('# sample_rate_hz={}\n'.format(item['sample_rate_hz']))
            writer.writerow(['t_ms', 'current_A', 'track_V', 'supply_V', 'marker'])
            continue
        t_ms += item['dt_ms']
        writer.writerow([
            t_ms,
            '' if item['marker'] else '{:.2f}'.format(item['current_A']),
            '{:.2f}'.format(item['track_V']),
            '{:.2f}'.format(item['supply_V']),
            1 if item['marker'] else 0,
        ])


def to_dataframe(path):
    """Return (pandas.DataFrame, header dict). Requires pandas."""
    import pandas as pd
    rows = []
    header = None
    t_ms = 0
    for kind, item in iter_records(path):
        if kind == 'header':
            header = item
            continue
        t_ms += item['dt_ms']
        rows.append({
            't_ms': t_ms,
            'current_A': None if item['marker'] else item['current_A'],
            'track_V': item['track_V'],
            'supply_V': item['supply_V'],
            'marker': item['marker'],
        })
    return pd.DataFrame(rows), header


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('path', help='binary session file (.bin)')
    ap.add_argument('-o', '--output', help='output CSV path (default: stdout)')
    ap.add_argument('--pandas', action='store_true',
                     help='load with pandas and print a summary instead of CSV')
    args = ap.parse_args()

    if args.pandas:
        df, header = to_dataframe(args.path)
        print('Session header:', header)
        print(df.describe())
        return

    if args.output:
        with open(args.output, 'w', newline='') as out:
            to_csv(args.path, out)
    else:
        to_csv(args.path, sys.stdout)


if __name__ == '__main__':
    main()
