"""Enforce line coverage independently of coverage.py's combined branch score."""
import json
from pathlib import Path


def check(path='coverage.json'):
    totals = json.loads(Path(path).read_text())['totals']
    statements = totals['num_statements']
    percent = 100 * totals['covered_lines'] / statements if statements else 0
    print(f'Line coverage: {percent:.2f}% (required: 80%)')
    return percent >= 80


if __name__ == '__main__':
    raise SystemExit(0 if check() else 1)
