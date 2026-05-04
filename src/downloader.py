from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests


CKAN_API_BASE = "https://opendata.city-adm.lviv.ua/api/3/action/resource_show"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://opendata.city-adm.lviv.ua/",
}


class DownloadError(RuntimeError):
    pass


def download_ckan_resource(resource_page_url: str, destination_dir: Path, filename_prefix: str) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    resource_id = extract_resource_id(resource_page_url)
    metadata = fetch_resource_metadata(resource_id)
    download_url = metadata.get("url")
    if not download_url:
        raise DownloadError(f"Resource {resource_id} has no download URL")

    response = requests.get(download_url, headers=DEFAULT_HEADERS, timeout=120)
    response.raise_for_status()

    filename = build_filename(filename_prefix, metadata, response)
    destination = destination_dir / filename
    destination.write_bytes(response.content)
    return destination


def extract_resource_id(resource_page_url: str) -> str:
    parsed = urlparse(resource_page_url)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise DownloadError(f"Cannot extract resource id from URL: {resource_page_url}")
    return parts[-1]


def fetch_resource_metadata(resource_id: str) -> dict[str, object]:
    response = requests.get(CKAN_API_BASE, params={"id": resource_id}, headers=DEFAULT_HEADERS, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise DownloadError(f"CKAN API did not return success for resource {resource_id}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise DownloadError(f"CKAN API returned invalid result for resource {resource_id}")
    return result


def build_filename(prefix: str, metadata: dict[str, object], response: requests.Response) -> str:
    extension = extension_from_content_disposition(response.headers.get("content-disposition", ""))
    if not extension:
        extension = extension_from_url(str(metadata.get("url", "")))
    if not extension:
        extension = extension_from_format(str(metadata.get("format", "")))
    if not extension:
        extension = ".xlsx"
    return f"{prefix}_latest{extension.lower()}"


def extension_from_content_disposition(header: str) -> str:
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', header, flags=re.IGNORECASE)
    if not match:
        return ""
    filename = unquote(match.group(1).strip())
    return Path(filename).suffix


def extension_from_url(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix
    if suffix.lower() in {".xlsx", ".xls", ".csv", ".xlsm"}:
        return suffix
    return ""


def extension_from_format(resource_format: str) -> str:
    normalized = resource_format.strip().lower()
    if normalized in {"xlsx", "xls", "csv", "xlsm"}:
        return f".{normalized}"
    return ""
