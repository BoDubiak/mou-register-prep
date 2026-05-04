# reference

Сюди скрипт завантажує довідник вулиць opendata як `street_dictionary_latest.*`.

Для ручних замін створіть локальний файл:

```powershell
Copy-Item reference\manual_overrides.example.csv reference\manual_overrides.csv
```

`manual_overrides.csv` і завантажені довідники не зберігаються в git.
