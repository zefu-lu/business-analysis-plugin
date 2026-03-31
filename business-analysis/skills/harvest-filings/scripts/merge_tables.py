#!/usr/bin/env python3
"""Merge multiple CSV tables (one per filing period) into a single consolidated CSV.

Rows are matched by label (first column). Columns are periods, ordered chronologically
by the order the input files are provided (oldest first).

When the same metric+period appears in multiple files, the LAST file's value wins
(latest filing takes precedence).

Usage:
    python merge_tables.py <csv1> <csv2> [csv3 ...] -o merged.csv
    python merge_tables.py filing_2022.csv filing_2023.csv filing_2024.csv -o consolidated.csv

Arguments:
    csv files       Input CSV files, ordered oldest to newest.

Options:
    -o, --output    Output CSV path. Default: stdout.

Notes:
    - Row labels are matched exactly. If labels differ across filings
      (e.g., "Cost of revenue" vs "Cost of goods sold"), both rows are kept.
    - Blank cells are preserved as empty strings.
    - The first row of each CSV is treated as the header (period columns).
"""

import argparse
import csv
import sys
from collections import OrderedDict


def read_csv(path):
    """Read a CSV file and return (headers, rows) where rows is a list of (label, {period: value})."""
    with open(path, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return [], []

    headers = [h.strip() for h in rows[0]]
    # headers[0] is the metric label column, headers[1:] are period columns
    period_columns = headers[1:]

    data = []
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue  # skip blank rows
        label = row[0].strip()
        values = {}
        for i, period in enumerate(period_columns):
            cell_idx = i + 1
            if cell_idx < len(row):
                values[period] = row[cell_idx].strip()
            else:
                values[period] = ""
        data.append((label, values))

    return period_columns, data


def merge(csv_paths):
    """Merge multiple CSVs into one consolidated table.

    Files should be ordered oldest to newest — last file wins on conflicts.
    """
    all_periods = OrderedDict()  # preserves insertion order
    # label -> {period: value}
    merged_rows = OrderedDict()

    for path in csv_paths:
        periods, data = read_csv(path)

        for period in periods:
            if period not in all_periods:
                all_periods[period] = True

        for label, values in data:
            if label not in merged_rows:
                merged_rows[label] = {}
            for period, value in values.items():
                if value:  # only overwrite if there's actually a value
                    merged_rows[label][period] = value

    period_list = list(all_periods.keys())
    return period_list, merged_rows


def write_merged(period_list, merged_rows, output):
    """Write the merged table to CSV."""
    writer = csv.writer(output)

    # Header row
    writer.writerow(["Metric"] + period_list)

    # Data rows
    for label, values in merged_rows.items():
        row = [label]
        for period in period_list:
            row.append(values.get(period, ""))
        writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description="Merge multiple filing CSV tables into one consolidated table."
    )
    parser.add_argument(
        "csv_files",
        nargs="+",
        help="Input CSV files, ordered oldest to newest",
    )
    parser.add_argument("-o", "--output", help="Output CSV file (default: stdout)")

    args = parser.parse_args()

    if len(args.csv_files) < 2:
        print("Error: need at least 2 CSV files to merge.", file=sys.stderr)
        sys.exit(1)

    period_list, merged_rows = merge(args.csv_files)

    if args.output:
        with open(args.output, "w", newline="") as f:
            write_merged(period_list, merged_rows, f)
        print(
            f"Merged {len(args.csv_files)} files: "
            f"{len(merged_rows)} rows x {len(period_list)} periods -> {args.output}",
            file=sys.stderr,
        )
    else:
        write_merged(period_list, merged_rows, sys.stdout)


if __name__ == "__main__":
    main()
