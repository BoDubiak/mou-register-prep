# MOU register monthly Excel preparation

Проєкт готує щомісячний Excel-файл реєстру МУО з актуального відкритого реєстру Львівської міської ради, старого файлу бота та довідника вулиць.

## Структура

```text
src/
input/
output/
reports/
reference/
requirements.txt
README.md
```

## Джерела даних

Скрипт за замовчуванням сам завантажує:

- актуальний реєстр МУО:
  `https://opendata.city-adm.lviv.ua/dataset/reyestr-mistobudivnykh-umov-ta-obmezhen/resource/485a8ee7-8cf4-48d3-b500-4cf5ee138911`
- довідник вулиць:
  `https://opendata.city-adm.lviv.ua/dataset/street-dictionary/resource/aace2a36-767e-427d-96fb-9a1ad88d51b5`

Завантажені файли зберігаються як:

- `input/registermuo_latest.*`
- `reference/street_dictionary_latest.*`

Старий файл з бота потрібно покласти вручну:

- `input/RE_*.xlsx`

Ручні заміни для перейменованих або проблемних вулиць:

- `reference/manual_overrides.csv`

## Встановлення

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Запуск

Типовий запуск із завантаженням останнього реєстру та довідника:

```powershell
python -m src.main
```

Офлайн-запуск з локальними файлами:

```powershell
python -m src.main --skip-download
```

За замовчуванням результат повторює формат зразка `RE_02042026_MUO.xlsx`: у колонці `number` лишається знак `№`, а `address_search` записується як рядок-список, наприклад `['вулиця Пирогівка']` або `[]`.

Якщо потрібен номер без знаку `№`:

```powershell
python -m src.main --number-without-sign
```

Явне передавання файлів:

```powershell
python -m src.main `
  --old-file input\RE_2026_04.xlsx `
  --current-file input\registermuo_latest.xlsx `
  --streets-file reference\street_dictionary_latest.xlsx `
  --manual-overrides reference\manual_overrides.csv
```

## Результати

- `output/muo_register_prepared_YYYYMMDD_HHMMSS.xlsx` - підготовлений реєстр
- `reports/unmatched_addresses_YYYYMMDD_HHMMSS.xlsx` - адреси, для яких не знайдено `address_search`

## Зіставлення колонок

| Вихідна колонка | Джерело |
| --- | --- |
| `date` | `orderIssued` |
| `number` | `orderNumber`, у форматі зразка зі знаком `№`; для номера без знаку використайте `--number-without-sign` |
| `customer` | `applicantName` |
| `type` | `type` |
| `name_object` | `name` |
| `settlement` | `addressPostName` |
| `address_object` | `addressThoroughfare + addressLocatorDesignator + addressLocatorComment` |
| `address_search` | старий бот-файл, довідник `Label`, або `manual_overrides.csv` |
| `changes` | `changesDescription` |
| `cancelling` | `cancellationDescription` |

## Правила address_search

- Спочатку переноситься наявне `address_search` зі старого бот-файлу, якщо запис збігається за датою, номером, замовником, назвою об'єкта та адресою.
- Якщо запису в старому файлі немає, адреса шукається в довіднику вулиць по колонці `Label`.
- Якщо населений пункт не Львів, у `address_search` записується лише вулиця без населеного пункту.
- Якщо вулиця не знайдена в довіднику, скрипт перевіряє `reference/manual_overrides.csv`.
- Якщо є апостроф у проблемному незнайденому кейсі, `address_search` лишається порожнім у логіці обробки і записується як `[]` у фінальному Excel.
- Усі порожні або `[]` значення `address_search` потрапляють в unmatched report.

## manual_overrides.csv

Файл підтримує такі колонки:

- `source` - проблемна назва або фрагмент адреси з актуального реєстру
- `address_search` - правильне значення для `address_search`
- `comment` - необов'язковий коментар
