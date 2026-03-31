#!/usr/bin/env python3
"""Extract a table from specific pages of a PDF using pdfplumber.

Usage:
    python extract_table.py <pdf_path> <start_page> [end_page] [-o output.csv] [--table-index N]

Arguments:
    pdf_path        Path to the PDF file.
    start_page      First page to extract from (1-indexed).
    end_page        Last page to extract from (1-indexed, default: same as start_page).

Options:
    -o, --output    Output CSV path. Default: stdout.
    --table-index N Which table on the page(s) to extract (0-indexed, default: 0).
                    Use "all" to extract all tables found, separated by a blank row.

Examples:
    python extract_table.py AAPL_10K_2024.pdf 45
    python extract_table.py AAPL_10K_2024.pdf 45 46 -o income_statement.csv
    python extract_table.py AAPL_10K_2024.pdf 45 46 --table-index all
"""

import argparse
import csv
import sys

try:
    import pdfplumber
except ImportError:
    print("Error: pdfplumber is required. Install with: pip install pdfplumber", file=sys.stderr)
    sys.exit(1)


def extract_tables(pdf_path, start_page, end_page, table_index):
    """Extract table(s) from the given page range."""
    tables = []

    with pdfplumber.open(pdf_path) as pdf:
        if start_page < 1 or end_page > len(pdf.pages):
            print(
                f"Error: page range {start_page}-{end_page} out of bounds "
                f"(PDF has {len(pdf.pages)} pages).",
                file=sys.stderr,
            )
            sys.exit(1)

        # Collect all tables across the page range
        all_tables = []
        for page_num in range(start_page - 1, end_page):
            page = pdf.pages[page_num]
            page_tables = page.extract_tables()
            if page_tables:
                all_tables.extend(page_tables)

        if not all_tables:
            print(
                f"No tables found on pages {start_page}-{end_page}.",
                file=sys.stderr,
            )
            sys.exit(1)

        if table_index == "all":
            for i, table in enumerate(all_tables):
                tables.append(table)
        else:
            idx = int(table_index)
            if idx >= len(all_tables):
                print(
                    f"Error: table index {idx} out of range "
                    f"(found {len(all_tables)} table(s)).",
                    file=sys.stderr,
                )
                sys.exit(1)
            tables.append(all_tables[idx])

    return tables


def clean_cell(cell):
    """Clean a cell value: strip whitespace, normalize None."""
    if cell is None:
        return ""
    return str(cell).strip().replace("\n", " ")


def write_tables(tables, output):
    """Write extracted tables to CSV."""
    writer = csv.writer(output)
    for i, table in enumerate(tables):
        if i > 0:
            writer.writerow([])  # blank row separator between tables
        for row in table:
            writer.writerow([clean_cell(cell) for cell in row])


def main():
    parser = argparse.ArgumentParser(
        description="Extract tables from PDF pages using pdfplumber."
    )
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("start_page", type=int, help="First page (1-indexed)")
    parser.add_argument(
        "end_page",
        type=int,
        nargs="?",
        default=None,
        help="Last page (1-indexed, default: same as start_page)",
    )
    parser.add_argument("-o", "--output", help="Output CSV file (default: stdout)")
    parser.add_argument(
        "--table-index",
        default="0",
        help='Which table to extract: 0-indexed number or "all" (default: 0)',
    )

    args = parser.parse_args()

    if args.end_page is None:
        args.end_page = args.start_page

    tables = extract_tables(
        args.pdf_path, args.start_page, args.end_page, args.table_index
    )

    if args.output:
        with open(args.output, "w", newline="") as f:
            write_tables(tables, f)
        print(f"Wrote {len(tables)} table(s) to {args.output}", file=sys.stderr)
    else:
        write_tables(tables, sys.stdout)


if __name__ == "__main__":
    main()
