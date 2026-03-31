---
name: harvest-filings
description: Extract time series data, metrics, tables, and financial statements from 10-K, 20-F, and equivalent filings across multiple periods. Output as CSV for spreadsheet analysis. Use when the user needs to collect or compare financial data from annual reports.
argument-hint: "[--dir path/to/filings]"
---

# Harvest Filings

Extract and consolidate data from filing PDFs into a single CSV for spreadsheet analysis.

## Dependencies

This skill requires two CLI tools for PDF text extraction and search:

| Tool | Purpose | Linux | macOS | Windows |
|------|---------|-------|-------|---------|
| `pdftotext` | Extract text from PDF pages | `sudo apt install poppler-utils` | `brew install poppler` | `conda install -c conda-forge poppler` or WSL |
| `pdfgrep` | Search for keywords inside PDFs | `sudo apt install pdfgrep` | `brew install pdfgrep` | WSL only (no native build) |
| `pdfplumber` | Structured table extraction from PDFs | `pip install pdfplumber` | `pip install pdfplumber` | `pip install pdfplumber` |

**Windows fallback**: If `pdfgrep` is not available, use `pdftotext <file> - | grep -n -i "keyword"` as a substitute.

Before proceeding, verify tools are available by running `which pdfgrep pdftotext` and `python -c "import pdfplumber"`. If any are missing, inform the user and provide the install command for their platform.

## Helper Scripts

This skill includes two Python scripts in [scripts/](scripts/) to handle the mechanical parts of table extraction and merging:

### extract_table.py

Extracts tables from specific PDF pages into clean CSV using `pdfplumber`. Much more reliable than `pdftotext` for tabular data.

```bash
# Extract the first table from page 45
python ${CLAUDE_SKILL_DIR}/scripts/extract_table.py filing.pdf 45

# Extract from a page range (table spans pages 45-46), save to file
python ${CLAUDE_SKILL_DIR}/scripts/extract_table.py filing.pdf 45 46 -o income_stmt_2024.csv

# Extract all tables found on those pages
python ${CLAUDE_SKILL_DIR}/scripts/extract_table.py filing.pdf 45 46 --table-index all
```

### merge_tables.py

Merges multiple per-filing CSVs into one consolidated table. Rows are matched by label. Last file wins on conflicts (latest filing takes precedence).

```bash
# Merge 3 filing extracts (ordered oldest to newest)
python ${CLAUDE_SKILL_DIR}/scripts/merge_tables.py stmt_2022.csv stmt_2023.csv stmt_2024.csv -o consolidated.csv
```

## Invocation

The user invokes the skill and then provides a **reference snippet** — a copy-pasted excerpt from one filing that shows the data they want. This can be a table, a paragraph, a few lines — anything.

```
/harvest-filings
> [user pastes a snippet from one filing as the reference example]

/harvest-filings --dir ./filings/TSM
> [user pastes snippet]
```

- **Default directory**: current working directory. Override with `--dir <path>`.
- **Reference snippet**: The pasted content is the template. If the user does not provide a snippet, ask them to paste one.

## Step-by-Step Process

### 1. Discover and order PDFs

- Glob for `*.pdf` in the target directory.
- Sort filings chronologically by filename (rely on the user's good naming).
- List the discovered filings and confirm with the user before proceeding.

### 2. Analyze the reference snippet

Examine the user's pasted snippet to determine:

- **Is it tabular data or a text/metric disclosure?** This determines which extraction path to follow.
- **What are the key labels/line items?** E.g., "Revenue", "Net income", "Installed capacity (GW)", etc.
- Derive search keywords from the snippet — section titles, line item names, distinctive phrases — that can be used to locate the equivalent section in other filings. Choose keywords that are **likely to be unique** in the document.

Then follow the appropriate path below.

---

## Path A: Tabular Data (financial statements, tables)

Use this path when the reference snippet is a structured table (income statement, balance sheet, cash flow statement, segment data, etc.).

### A1. Locate tables across all PDFs

Batch grep all PDFs to find the page where the target table lives:

```bash
for f in *.pdf; do echo "=== $f ==="; pdfgrep -n -i "section title keyword" "$f"; done
```

For **large tables that span multiple pages**, use boundary keywords to determine a page range:

```bash
# Start of table (e.g., section title)
for f in *.pdf; do echo "=== $f ==="; pdfgrep -n -i "CONSOLIDATED STATEMENTS OF OPERATIONS" "$f"; done

# End of table (e.g., last line item, or start of next section)
for f in *.pdf; do echo "=== $f ==="; pdfgrep -n -i "Earnings per share" "$f"; done
```

For **small tables that fit on one page**, a single keyword grep is enough — just find the page number.

If a keyword is not found in a filing, try alternative keywords (labels may vary across years). If still not found, note it as a gap.

### A2. Extract tables

For each filing, run the extraction script using the page (or page range) found in A1:

```bash
# Single page table
python ${CLAUDE_SKILL_DIR}/scripts/extract_table.py filing.pdf <page> -o <filing_extract>.csv

# Multi-page table
python ${CLAUDE_SKILL_DIR}/scripts/extract_table.py filing.pdf <start_page> <end_page> -o <filing_extract>.csv
```

Review the extracted CSV to verify it captured the right table. If the wrong table was picked, use `--table-index` to select a different one, or `--table-index all` to see all tables on those pages.

### A3. Merge tables across filings

Once you have one CSV per filing, merge them using the merge script. **Order files oldest to newest** so that the latest filing wins on conflicts:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/merge_tables.py extract_2020.csv extract_2021.csv extract_2022.csv extract_2023.csv extract_2024.csv -o consolidated.csv
```

The merge script handles:
- **Data conflicts** (e.g., 2025 filing restates 2024 numbers): last file wins — it reflects restatements and reclassifications.
- **Row mismatches** (e.g., "Cost of revenue" vs "Cost of goods sold"): both rows are kept as-is. The user will reconcile later.

**Structural changes** (e.g., a company pivots its business and the statements look fundamentally different) must be handled manually: keep the latest filing's numbers and stop going further back in time. Note in the output where the structural break occurs.

---

## Path B: Text / Metric Disclosures

Use this path when the reference snippet is from prose — numbers disclosed in paragraphs, not in a formal table (e.g., capacity, yield, production volumes, customer counts).

### B1. Locate disclosures across all PDFs

Batch grep all PDFs to find the page(s) where the metric is mentioned:

```bash
for f in *.pdf; do echo "=== $f ==="; pdfgrep -n -i "keyword" "$f"; done
```

A single keyword is usually enough since text disclosures are typically short and on one page.

### B2. Extract page text

For each filing, extract the full text of the page where the disclosure lives:

```bash
pdftotext -f <page> -l <page> filing.pdf -
```

Read the extracted text and find the metric value and its associated period. Extract verbatim.

### B3. Build the CSV manually

Since text disclosures are not structured tables, build the CSV directly:

```
Metric, <Period 1>, <Period 2>, <Period 3>, ...
Installed capacity (GW), 50, 55, 60, ...
Utilization rate, 85%, 90%, 88%, ...
```

- Some metrics may only appear in certain years — leave blanks for years where the disclosure is missing.
- If the same metric is found in multiple filings for overlapping periods, keep the latest filing's value.

---

## Output

- Write the final CSV to the target directory with a descriptive name (e.g., `AAPL_income_statement.csv`, `TSM_capacity_metrics.csv`).
- Show a summary to the user: number of filings processed, periods covered, any gaps or structural breaks encountered.
- If there are any ambiguities or issues (e.g., a metric found in text but with unclear period association), flag them for the user to review.
- **Clean up intermediate files.** Delete all per-filing extract CSVs (e.g., `extract_2022.csv`, `extract_2023.csv`) created during the process. Only the final merged CSV should remain.

## Important Rules

- **Extract verbatim.** Copy numbers, labels, and text exactly as they appear in the filing. Do not round, reformat, recompute, or "fix" anything. Your job is data extraction, not analysis.
- **Do not interpret or validate the data.** If a number looks wrong, unusual, or inconsistent — extract it anyway. The user will validate later.
- **Never fabricate data.** If a number is not found, leave it blank.
- **Latest filing wins.** When the same period appears in multiple filings with different numbers, use the most recent filing's version.
- **Preserve original labels.** Do not rename line items. Keep them as reported — the user will normalize later.
- **Flag structural breaks.** If filing structures change significantly across periods, note where and stop extending backwards.
- **Respect gaps.** Some disclosures appear in some years but not others (e.g., capacity mentioned in 2023 but not 2022). Leave blanks — do not fill forward or estimate.
- **No custom scripts.** Do not write or execute custom Python/Bash scripts. Only use the provided tools: `pdfgrep`, `pdftotext`, `extract_table.py`, and `merge_tables.py`. If something cannot be achieved with these tools, flag it for the user rather than writing ad-hoc code.
