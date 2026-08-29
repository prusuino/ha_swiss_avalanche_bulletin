# Changelog

## 1.2.0 — 2026-08-29

The integration no longer creates or deletes dashboards and Lovelace
resources. Writing into another component's storage is not something an
integration should do on its own initiative, and the previous
implementation relied on internal Home Assistant APIs that carry no
stability guarantee — a change upstream could break setup or leave a
dashboard behind that had to be repaired by hand.

**Breaking:**

- The automatically created "Avalanches" dashboard is gone. Existing
  dashboards are left untouched — this release simply stops creating,
  extending and deleting them. If you want to keep the dashboard you
  already have, do nothing; it is now yours to edit freely.
- The bundled card is no longer registered as a Lovelace resource
  automatically. Register it once under **Settings → Dashboards → ⋮ →
  Resources** with the URL `/slf_avalanche/static/slf-imis-card.js` and
  type *JavaScript module*. The README has step-by-step instructions and
  example card configurations.

**Unchanged:**

- The card itself still ships with the integration and is still served
  under `/slf_avalanche/static/`. Once registered, it works exactly as
  before, including the visual editor.
- All sensors, devices, coordinators and the IMIS station handling are
  untouched.

**Other:**

- Minimum Home Assistant version declared as 2024.12.0, matching what the
  options flow actually requires. It was previously declared as 2024.1.0,
  where the options dialog would have failed.
- Added `translations/en.json`. English users previously saw raw
  translation keys in the setup and options dialogs, because `strings.json`
  is not read at runtime for custom integrations.

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
