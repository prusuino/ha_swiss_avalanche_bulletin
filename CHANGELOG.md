# Changelog

## 1.0.0 — 2026-07-16

Initial public release.

- `sensor.slf_avalanche_danger_level_<label>` — current avalanche danger level (1–5) for the configured location, resolved via the SLF's coordinate-to-warning-region API
- `sensor.slf_avalanche_region_<label>` — the resolved SLF warning region name
- `sensor.slf_avalanche_problem_1/2/3_<label>` — up to 3 currently reported avalanche problems with elevation, aspects, and full explanatory text
- Danger-level and avalanche-problem text follow the official multilingual EAWS terminology
- Multi-language support (German, English, French, Italian) for entity names, device info, and danger/problem text, based on the Home Assistant language setting
- Config flow defaults to the Home Assistant home location, with manual override; supports multiple locations via multiple config entries
- All entities carry the required CC BY 4.0 attribution for SLF data
- Data refreshed every hour; gracefully reports no value outside the winter season or when the bulletin doesn't cover the configured region
