from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from .address_matcher import AddressMatcher
from .config import (
    ADDRESS_PART_COLUMNS,
    CURRENT_FILE_PATTERNS,
    CURRENT_REGISTER_RESOURCE_URL,
    INPUT_DIR,
    MANUAL_OVERRIDES_FILE,
    OLD_FILE_PATTERN,
    OLD_MATCH_KEY_COLUMNS,
    OUTPUT_COLUMNS,
    OUTPUT_DIR,
    REFERENCE_DIR,
    REPORTS_DIR,
    SOURCE_TO_OUTPUT_COLUMNS,
    STREET_DICTIONARY_RESOURCE_URL,
)
from .downloader import download_ckan_resource
from .utils import (
    clean_order_number,
    clean_text,
    combine_nonempty,
    ensure_dirs,
    format_date,
    format_order_number,
    latest_file,
    normalize_for_match,
    read_table,
    write_excel,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare monthly MOU register Excel file.")
    parser.add_argument("--old-file", type=Path, default=None, help="Old bot file, usually input/RE_*.xlsx")
    parser.add_argument("--current-file", type=Path, default=None, help="Current registermuo*.xls(x) or CSV file")
    parser.add_argument("--streets-file", type=Path, default=None, help="Street reference file with Label column")
    parser.add_argument("--manual-overrides", type=Path, default=MANUAL_OVERRIDES_FILE, help="Manual overrides CSV")
    parser.add_argument("--output-file", type=Path, default=None, help="Prepared output Excel path")
    parser.add_argument("--report-file", type=Path, default=None, help="Unmatched report Excel path")
    parser.add_argument("--min-score", type=int, default=88, help="Minimum rapidfuzz score for street matching")
    parser.add_argument("--skip-download", action="store_true", help="Use only local input/reference files")
    parser.add_argument("--number-without-sign", action="store_true", help="Write number without the № sign")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs([INPUT_DIR, OUTPUT_DIR, REPORTS_DIR, REFERENCE_DIR])

    old_file = args.old_file or latest_file(INPUT_DIR, [OLD_FILE_PATTERN])
    current_file = args.current_file
    streets_file = args.streets_file

    if not args.skip_download:
        if current_file is None:
            current_file = try_download_latest(CURRENT_REGISTER_RESOURCE_URL, INPUT_DIR, "registermuo")
        if streets_file is None:
            streets_file = try_download_latest(STREET_DICTIONARY_RESOURCE_URL, REFERENCE_DIR, "street_dictionary")

    current_file = current_file or latest_file(INPUT_DIR, CURRENT_FILE_PATTERNS)
    streets_file = streets_file or find_streets_file()

    if old_file is None:
        raise FileNotFoundError(f"Old bot file not found by pattern {INPUT_DIR / OLD_FILE_PATTERN}")
    if current_file is None:
        raise FileNotFoundError(f"Current file not found by patterns: {', '.join(CURRENT_FILE_PATTERNS)}")
    if streets_file is None:
        raise FileNotFoundError("Street reference file with a Label column was not found in reference/")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = args.output_file or OUTPUT_DIR / f"muo_register_prepared_{timestamp}.xlsx"
    report_file = args.report_file or REPORTS_DIR / f"unmatched_addresses_{timestamp}.xlsx"

    current_df = read_table(current_file)
    old_df = read_table(old_file)

    prepared_df = transform_current_register(current_df)
    transfer_existing_address_search(prepared_df, old_df)

    matcher = AddressMatcher(streets_file, args.manual_overrides, min_score=args.min_score)
    unmatched_rows = fill_address_search(prepared_df, matcher)
    format_sample_output(prepared_df, include_number_sign=not args.number_without_sign)

    write_excel(prepared_df[OUTPUT_COLUMNS], output_file)
    write_excel(pd.DataFrame(unmatched_rows), report_file)

    print(f"Prepared file: {output_file}")
    print(f"Unmatched report: {report_file}")
    print(f"Rows: {len(prepared_df)}")
    print(f"Unmatched: {len(unmatched_rows)}")


def try_download_latest(resource_url: str, destination_dir: Path, filename_prefix: str) -> Path | None:
    try:
        path = download_ckan_resource(resource_url, destination_dir, filename_prefix)
        print(f"Downloaded latest {filename_prefix}: {path}")
        return path
    except Exception as exc:
        print(f"Could not download latest {filename_prefix}: {exc}")
        return None


def find_streets_file() -> Path | None:
    preferred_patterns = [
        "*street*.xlsx",
        "*street*.xls",
        "*vuly*.xlsx",
        "*vuly*.xls",
        "*.xlsx",
        "*.xls",
        "*.csv",
    ]
    for pattern in preferred_patterns:
        for path in sorted(REFERENCE_DIR.glob(pattern)):
            if path.name == MANUAL_OVERRIDES_FILE.name:
                continue
            try:
                columns = list(read_table(path).columns)
            except Exception:
                continue
            if "Label" in columns:
                return path
    return None


def transform_current_register(df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in SOURCE_TO_OUTPUT_COLUMNS if column not in df.columns]
    missing_address_parts = [column for column in ADDRESS_PART_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Current register is missing required columns: {', '.join(missing)}")
    if missing_address_parts:
        raise ValueError(f"Current register is missing address columns: {', '.join(missing_address_parts)}")

    result = pd.DataFrame()
    for source, target in SOURCE_TO_OUTPUT_COLUMNS.items():
        result[target] = df[source].map(clean_text)

    result["date"] = df["orderIssued"].map(format_date)
    result["number"] = df["orderNumber"].map(format_order_number)
    result["address_object"] = df[ADDRESS_PART_COLUMNS].apply(lambda row: combine_nonempty(row.tolist()), axis=1)
    result["address_search"] = ""

    for column in OUTPUT_COLUMNS:
        if column not in result.columns:
            result[column] = ""

    return result[OUTPUT_COLUMNS].copy()


def transfer_existing_address_search(prepared_df: pd.DataFrame, old_df: pd.DataFrame) -> None:
    if "address_search" not in old_df.columns:
        return

    normalized_old = normalize_old_bot_df(old_df)
    existing_map: dict[str, str] = {}

    for _, row in normalized_old.iterrows():
        address_search = clean_text(row.get("address_search", ""))
        if is_empty_address_search(address_search):
            continue
        key = build_match_key(row)
        if key and key not in existing_map:
            existing_map[key] = address_search

    for index, row in prepared_df.iterrows():
        key = build_match_key(row)
        existing = existing_map.get(key)
        if existing:
            prepared_df.at[index, "address_search"] = existing


def normalize_old_bot_df(old_df: pd.DataFrame) -> pd.DataFrame:
    df = old_df.copy()

    rename_candidates = {
        "orderIssued": "date",
        "orderNumber": "number",
        "applicantName": "customer",
        "name": "name_object",
        "addressPostName": "settlement",
        "changesDescription": "changes",
        "cancellationDescription": "cancelling",
    }
    df = df.rename(columns={source: target for source, target in rename_candidates.items() if source in df.columns})

    for column in OUTPUT_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df["date"] = df["date"].map(format_date)
    df["number"] = df["number"].map(clean_order_number)
    for column in OUTPUT_COLUMNS:
        df[column] = df[column].map(clean_text)
    return df[OUTPUT_COLUMNS].copy()


def build_match_key(row: pd.Series) -> str:
    values = []
    for column in OLD_MATCH_KEY_COLUMNS:
        value = row.get(column, "")
        values.append(normalize_for_match(value))
    key = "|".join(values)
    return key if key.strip("|") else ""


def fill_address_search(prepared_df: pd.DataFrame, matcher: AddressMatcher) -> list[dict[str, object]]:
    unmatched_rows: list[dict[str, object]] = []

    for index, row in prepared_df.iterrows():
        if not is_empty_address_search(row.get("address_search", "")):
            continue

        match = matcher.match(row.get("settlement", ""), row.get("address_object", ""))
        prepared_df.at[index, "address_search"] = match.address_search

        if not match.address_search:
            unmatched_rows.append(
                {
                    "row_number": index + 2,
                    "date": row.get("date", ""),
                    "number": row.get("number", ""),
                    "customer": row.get("customer", ""),
                    "settlement": row.get("settlement", ""),
                    "address_object": row.get("address_object", ""),
                    "reason": match.status,
                    "score": match.score,
                    "matched_label": match.matched_label,
                }
            )

    return unmatched_rows


def format_sample_output(prepared_df: pd.DataFrame, include_number_sign: bool = True) -> None:
    prepared_df["date"] = prepared_df["date"].map(format_date)
    prepared_df["number"] = prepared_df["number"].map(lambda value: format_order_number(value, include_number_sign))
    prepared_df["address_search"] = prepared_df["address_search"].map(format_address_search_cell)


def is_empty_address_search(value: object) -> bool:
    text = clean_text(value)
    return text in {"", "[]", "['']", '[""]'}


def format_address_search_cell(value: object) -> str:
    text = clean_text(value)
    if is_empty_address_search(text):
        return "[]"
    if text.startswith("[") and text.endswith("]"):
        return text
    escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"['{escaped}']"


if __name__ == "__main__":
    main()
