from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
REPORTS_DIR = PROJECT_ROOT / "reports"
REFERENCE_DIR = PROJECT_ROOT / "reference"

OLD_FILE_PATTERN = "RE_*.xlsx"
CURRENT_FILE_PATTERNS = ("registermuo*.xlsx", "registermuo*.xls", "registermuo*.csv")
MANUAL_OVERRIDES_FILE = REFERENCE_DIR / "manual_overrides.csv"

CURRENT_REGISTER_RESOURCE_URL = (
    "https://opendata.city-adm.lviv.ua/dataset/"
    "reyestr-mistobudivnykh-umov-ta-obmezhen/resource/"
    "485a8ee7-8cf4-48d3-b500-4cf5ee138911"
)
STREET_DICTIONARY_RESOURCE_URL = (
    "https://opendata.city-adm.lviv.ua/dataset/"
    "street-dictionary/resource/"
    "aace2a36-767e-427d-96fb-9a1ad88d51b5"
)

OUTPUT_COLUMNS = [
    "date",
    "number",
    "customer",
    "type",
    "name_object",
    "settlement",
    "address_object",
    "address_search",
    "changes",
    "cancelling",
]

SOURCE_TO_OUTPUT_COLUMNS = {
    "orderIssued": "date",
    "orderNumber": "number",
    "applicantName": "customer",
    "type": "type",
    "name": "name_object",
    "addressPostName": "settlement",
    "changesDescription": "changes",
    "cancellationDescription": "cancelling",
}

ADDRESS_PART_COLUMNS = [
    "addressThoroughfare",
    "addressLocatorDesignator",
    "addressLocatorComment",
]

OLD_MATCH_KEY_COLUMNS = [
    "date",
    "number",
    "customer",
    "name_object",
    "address_object",
]
