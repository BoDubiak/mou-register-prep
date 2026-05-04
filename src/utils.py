from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pandas as pd


APOSTROPHES = {"'", "`", "’", "ʼ", "‘", "՚"}


def ensure_dirs(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def latest_file(directory: Path, patterns: Iterable[str]) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(directory.glob(pattern))
    files = [path for path in candidates if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        return pd.read_excel(path, dtype=str, engine="openpyxl")
    if suffix == ".xls":
        return pd.read_excel(path, dtype=str)
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str)
    raise ValueError(f"Unsupported file format: {path}")


def write_excel(df: pd.DataFrame, path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="register")
        worksheet = writer.sheets["register"]
        worksheet.freeze_panes = "A2"
        for column_cells in worksheet.columns:
            max_length = max(len(str(cell.value or "")) for cell in column_cells)
            worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 12), 60)


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return "" if text.lower() in {"nan", "none", "nat"} else text


def normalize_for_match(value: object) -> str:
    text = clean_text(value).lower()
    replacements = {
        "№": "",
        ".": " ",
        ",": " ",
        ";": " ",
        ":": " ",
        "(": " ",
        ")": " ",
        "-": " ",
        "–": " ",
        "—": " ",
        "\"": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    for apostrophe in APOSTROPHES:
        text = text.replace(apostrophe, "")
    return re.sub(r"\s+", " ", text).strip()


def clean_order_number(value: object) -> str:
    text = clean_text(value)
    text = text.replace("№", "")
    text = re.sub(r"^\s*N\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def format_order_number(value: object, include_sign: bool = True) -> str:
    number = clean_order_number(value)
    if not number:
        return ""
    return f"№{number}" if include_sign else number


def format_date(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        parsed = pd.to_datetime(text, errors="coerce", format="%Y-%m-%d %H:%M:%S")
        if pd.isna(parsed):
            parsed = pd.to_datetime(text[:10], errors="coerce", format="%Y-%m-%d")
    else:
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return text
    return parsed.strftime("%Y-%m-%d 00:00:00")


def has_apostrophe(value: object) -> bool:
    text = clean_text(value)
    return any(apostrophe in text for apostrophe in APOSTROPHES)


def combine_nonempty(values: Iterable[object]) -> str:
    parts = [clean_text(value) for value in values]
    return " ".join(part for part in parts if part)


def is_lviv(value: object) -> bool:
    text = normalize_for_match(value)
    return text in {"львів", "м львів", "місто львів"}
