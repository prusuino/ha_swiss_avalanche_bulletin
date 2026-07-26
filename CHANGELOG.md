# Changelog

## 1.1.0 — 2026-07-26

IMIS measuring stations — snow depth, temperatures and wind in Home Assistant.

- New setup choice when adding the integration: avalanche bulletin for a
  location, or favourite IMIS measuring stations (independent of each other)
- Any of the ~200 IMIS stations can be selected as favourites from a
  searchable list sorted by distance; favourites are manageable at any time
  via the integration options
- One device per station with sensors for what it actually measures: snow
  depth, new snow last 24 h, air and snow surface temperature, humidity,
  wind speed/gusts/direction — updated every 30 minutes via the official
  SLF measurement API (measurement-api.slf.ch, CC BY 4.0)
- New Lovelace card `custom:slf-imis-station-card` with visual editor,
  bundled and registered automatically
- Automatically created "Avalanches" dashboard with one section per
  bulletin location and station cards for the IMIS favourites (user edits
  are never overwritten; removed again with the last entry)

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
