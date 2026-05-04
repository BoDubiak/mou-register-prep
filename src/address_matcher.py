from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

from .utils import clean_text, has_apostrophe, is_lviv, normalize_for_match, read_table


STREET_WORDS_PATTERN = re.compile(
    r"\b(вул|вулиця|просп|проспект|пл|площа|пров|провулок|шосе|узвіз|бульв|бульвар|алея|дорога|тракт)\.?\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class AddressMatch:
    address_search: str
    status: str
    score: int | None = None
    matched_label: str = ""


class AddressMatcher:
    def __init__(self, streets_file: Path, manual_overrides_file: Path | None = None, min_score: int = 88) -> None:
        self.min_score = min_score
        self.labels = self._load_labels(streets_file)
        self.normalized_to_label = {normalize_for_match(label): label for label in self.labels}
        self.key_to_label = {street_match_key(label): label for label in self.labels if street_match_key(label)}
        self.normalized_labels = list(self.key_to_label.keys())
        self.manual_overrides = self._load_manual_overrides(manual_overrides_file)

    @staticmethod
    def _load_labels(path: Path) -> list[str]:
        df = read_table(path)
        if "Label" not in df.columns:
            raise ValueError(f"Street reference must contain a Label column: {path}")
        labels = [clean_text(value) for value in df["Label"].tolist()]
        return sorted({label for label in labels if label})

    @staticmethod
    def _load_manual_overrides(path: Path | None) -> dict[str, str]:
        if path is None or not path.exists():
            return {}
        df = read_table(path)
        required = {"source", "address_search"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"manual_overrides.csv is missing columns: {', '.join(sorted(missing))}")

        overrides: dict[str, str] = {}
        for _, row in df.iterrows():
            source = normalize_for_match(row.get("source", ""))
            target = clean_text(row.get("address_search", ""))
            if source and target:
                overrides[source] = target
        return overrides

    def match(self, settlement: object, address_object: object) -> AddressMatch:
        address = clean_text(address_object)
        if not address:
            return AddressMatch("", "empty_address")

        street_candidate = extract_street_candidate(address)
        search_text = street_candidate or address
        normalized = normalize_for_match(search_text)
        match_key = street_match_key(search_text)

        override = self._manual_override(normalized)
        if override:
            return AddressMatch(self._format_label(override, settlement), "manual_override")

        if has_apostrophe(search_text):
            return AddressMatch("", "apostrophe_problem")

        exact = self.normalized_to_label.get(normalized)
        if exact:
            return AddressMatch(self._format_label(exact, settlement), "exact", 100, exact)

        exact_key = self.key_to_label.get(match_key)
        if exact_key:
            return AddressMatch(self._format_label(exact_key, settlement), "exact_key", 100, exact_key)

        match = process.extractOne(
            match_key,
            self.normalized_labels,
            scorer=fuzz.token_set_ratio,
            score_cutoff=self.min_score,
        )
        if not match:
            return AddressMatch("", "not_found")

        matched_normalized, score, _ = match
        matched_label = self.key_to_label[matched_normalized]
        return AddressMatch(self._format_label(matched_label, settlement), "fuzzy", int(score), matched_label)

    def _manual_override(self, normalized_address: str) -> str:
        if normalized_address in self.manual_overrides:
            return self.manual_overrides[normalized_address]

        for source, target in self.manual_overrides.items():
            if source and (source in normalized_address or normalized_address in source):
                return target
        return ""

    @staticmethod
    def _format_label(label: str, settlement: object) -> str:
        if is_lviv(settlement):
            return clean_text(label)
        return strip_settlement_from_label(label)


def extract_street_candidate(address: str) -> str:
    text = clean_text(address)
    if not text:
        return ""

    without_building = re.split(r"\b(буд|будинок|д\.|кв|прим|корпус|літ)\.?\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    candidate = strip_locator_designator(without_building).strip(" ,.;")

    match = STREET_WORDS_PATTERN.search(candidate)
    if match:
        candidate = candidate[match.start() :].strip(" ,.;")
        second_street = STREET_WORDS_PATTERN.search(candidate, match.end() - match.start())
        if second_street:
            candidate = candidate[: second_street.start()]
        candidate = re.split(
            r"\s+(біля|від|до|та\s+прилеглі|та\s+прилеглих|на\s+ділянці|в\s+районі)\b",
            candidate,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        return candidate.strip(" ,.;")
    return candidate


def strip_settlement_from_label(label: str) -> str:
    text = clean_text(label)
    if not text:
        return ""

    pieces = [piece.strip() for piece in re.split(r"[,;]", text) if piece.strip()]
    street_pieces = [piece for piece in pieces if STREET_WORDS_PATTERN.search(piece)]
    if street_pieces:
        return street_pieces[-1]

    text = re.sub(r"^\s*(м\.?|місто|с\.?|село|смт\.?)\s+[^,;]+[,;]?\s*", "", text, flags=re.IGNORECASE)
    return text.strip(" ,.;")


def strip_locator_designator(address: str) -> str:
    text = clean_text(address)
    text = re.sub(r"\s*,?\s*(?:№\s*)?\d+[0-9а-яА-Яa-zA-Z/-]*\s*$", "", text)
    text = re.sub(r"\s*,?\s*(?:№\s*)?\d+[0-9а-яА-Яa-zA-Z/-]*\s*[;,].*$", "", text)
    return text.strip(" ,.;")


def street_match_key(value: str) -> str:
    text = normalize_for_match(strip_locator_designator(value))
    replacements = {
        "вул": " ",
        "вулиця": " ",
        "просп": " ",
        "проспект": " ",
        "пл": " ",
        "площа": " ",
        "пров": " ",
        "провулок": " ",
        "бульв": " ",
        "бульвар": " ",
        "шосе": " ",
        "узвіз": " ",
        "алея": " ",
        "дорога": " ",
        "тракт": " ",
    }
    tokens = []
    for token in text.split():
        replacement = replacements.get(token, token)
        if replacement.strip():
            tokens.extend(replacement.split())
    tokens = [token for token in tokens if len(token) > 2]
    return " ".join(tokens)
