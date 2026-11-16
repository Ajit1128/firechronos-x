# FireChronos X — treatment of missing `type` values

## Scope

This document describes the **exploratory** MODIS/VIIRS comparison in
`scripts/compare_spatiotemporal.py`. It is not sensor harmonization,
fire identification, or validation of geographic coverage.

## Input semantics and policy

- The NASA FIRMS ingestion pipeline stores the original `type` value in
  `type_raw`. When the source column is missing, the normalized value is an
  empty string, not an inferred vegetation-fire classification.
- **Default:** only observations with `type_raw == "0"` (after trimming
  whitespace) are eligible for proximity candidates.
- Blank, missing, and other values are excluded by default, but are not
  deleted from the normalized dataset.
- **`--all-types`:** bypasses the type filter and also permits observations
  without a classification or with a different thermal-anomaly type. Results
  in that mode must not be interpreted as vegetation-fire-only comparisons.
- A single candidate is an exploratory *proximity association*; it is NOT
  evidence that MODIS and VIIRS observed the same individual fire.

## JSON report fields

`proximity_report.json` records:

| Field | Meaning |
|---|---|
| `type_zero_only` | Whether the default type filter is enabled |
| `type_missing_in_input` | Missing/blank type values in the complete input |
| `type_missing_by_sensor` | Missing/blank values per declared sensor |
| `excluded_missing_type` | Missing/blank values removed by the active filter |
| `excluded_other_type` | Non-`0` nonblank values removed by the active filter |
| `selected_modis`, `selected_viirs` | Rows eligible for comparison after filtering |

These categories count **thermal detections, not unique fires**.
All counts are computed without silently imputing a classification.

## Reproduce and test

From the repository root:

```powershell
python -m pytest -q
python scripts/compare_spatiotemporal.py --input data/processed/detections_normalized.csv --output-dir data/processed/comparison_default --radius-km 1 --minutes 60
python scripts/compare_spatiotemporal.py --input data/processed/detections_normalized.csv --output-dir data/processed/comparison_all_types --radius-km 1 --minutes 60 --all-types
```

`python` must refer to the virtual environment containing the project's
`requirements.txt` dependencies. The observations file is **not included** in
this patch; use the locally processed NASA CSVs and preserve their hashes.

Published sensitivity scenarios describe the previously run input and filter.
Do not overwrite or replace their existing manifest results after changing the
filter, without creating a new run and documenting the parameters.
