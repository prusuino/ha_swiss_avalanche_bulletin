# Changelog

## 1.2.2 — 2026-08-29

- Updated the bundled dashboard-strategy core to 1.1.1: `map: false` now
  also removes a map section inside a view, `max_columns` is honoured in
  the view-strategy flavour, and a view's header is kept when the strategy
  fills a single view. No change to the integration itself. The card file
  changed, so raise the `?v=` on the resource URL (e.g. `?v=1.2.2`) or do
  a hard reload if the old copy is still served.

## 1.2.1 — 2026-08-29

Version 1.2.0 removed the automatically created "Avalanches" dashboard
without offering anything in its place. This release adds the replacement:
a dashboard strategy.

**New:**

- A **dashboard strategy**, `custom:swiss-avalanche-bulletin`. A strategy
  is a recipe Home Assistant renders in the browser at display time: it
  stores nothing, overwrites nothing, and follows your config entries on
  every page load — a new location or station favourite appears by itself,
  a removed one disappears with no leftover card. It builds the layout the
  old dashboard had — one section per bulletin location (danger level with
  a badge, warning region) and one section per IMIS entry with a station
  card per favourite — and adds tiles for the up to three avalanche
  problems to each bulletin section. Create an
  empty dashboard and set `strategy: {type: custom:swiss-avalanche-bulletin}`
  in the raw configuration editor, or pick *Swiss Avalanche Bulletin* in
  the **+ Add dashboard** dialog; the README has the details. The strategy
  also registers as a **view strategy**, so it can fill a single view of a
  dashboard you already have, and honours `title` and `max_columns` under
  `strategy:`.
- The strategy ships inside the existing card file
  `/slf_avalanche/static/slf-imis-card.js`, so the one resource you already
  register for the card covers both — no second resource. The integration
  still only *serves* the file; adding it as a resource remains the
  one-time manual step described in the README.

**Upgrading:**

- The card file changed, and it is served with long-lived cache headers. If
  the strategy is not offered after the update, append or raise a version on
  the resource URL (e.g. `/slf_avalanche/static/slf-imis-card.js?v=1.2.1`)
  or do a hard reload (Ctrl+F5 / Cmd+Shift+R).
- No changes to sensors, devices or the setup flow. The minimum Home
  Assistant version stays at 2024.12.0.

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
