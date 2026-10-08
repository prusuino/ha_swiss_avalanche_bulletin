# Swiss Avalanche Bulletin (SLF)

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
<a href="https://www.buymeacoffee.com/prusuino"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" height="20"></a>

A Home Assistant custom integration for the official Swiss **avalanche bulletin**, published by the **WSL Institute for Snow and Avalanche Research (SLF)** — and, independently of it, for the **IMIS measuring stations** of the SLF: snow depth, new snow, temperatures and wind from ~200 automatic high-alpine stations.

## Background

The SLF publishes a nationwide avalanche bulletin covering ~150 warning regions across Switzerland, with a public, unauthenticated API (`aws.slf.ch`). This integration:

1. Resolves your configured latitude/longitude to the SLF warning region ("sector") that covers it, using the SLF's own coordinate lookup endpoint.
2. Fetches the current bulletin and extracts the danger rating and avalanche problems for that specific region.

Outside the winter season (or when your region isn't covered by an active bulletin), the sensors simply report no value rather than a stale or incorrect one.

**Multiple locations:** add the integration again to track a second location (e.g. a mountain cabin in addition to your home) — each instance is independent.

## What it provides

Per configured location:

| Entity | Description |
|---|---|
| `sensor.slf_avalanche_danger_level_<label>` | Current avalanche danger level as a **number (1–5)**, so it can be used directly in automations/thresholds. Attributes: text label (e.g. "Considerable"), whether a bulletin is currently active, validity period, next update time, publication time, the raw danger-rating data (bulletins can split the rating by elevation) |
| `sensor.slf_avalanche_region_<label>` | The SLF warning region name resolved for your coordinates (e.g. "Olten-Gösgen") — lets you confirm the location match is correct |
| `sensor.slf_avalanche_problem_1/2/3_<label>` | Up to 3 currently reported avalanche problems (e.g. wind-drifted snow, persistent weak layers, wet snow). Each includes elevation range, affected aspects (compass directions), and the SLF's full plain-text explanation. Entities report no value on days with fewer than 3 reported problems |

`<label>` is the label you gave the location when adding it — or, if you left it empty, the name of the resolved SLF warning region — slugified, followed by the last four characters of the config entry id so that two locations with the same label never collide: a location labelled "Home" gets something like `sensor.slf_avalanche_danger_level_home_ab12`, an unlabelled one in the Olten-Gösgen region `sensor.slf_avalanche_danger_level_olten_gosgen_ab12`. The integration suggests these object ids itself when an entity is first created, so they do not depend on your Home Assistant language — only the displayed names are localized. Entities created by versions before 1.3.0 keep their ids without the four-character part. Like any entity, they can be renamed in the entity settings afterwards.

Data is refreshed every hour. The bulletin itself is typically published once daily (around 17:00), with interim updates during high-danger situations.

## IMIS measuring stations

The Intercantonal Measurement and Information System (IMIS) consists of about 200 automatic stations in the Swiss Alps and Jura, most between 2000 and 3000 m. When adding the integration, choose **"IMIS measuring stations"** to pick any stations as favourites — the searchable list is sorted by distance from your home location (❄ snow station, 🌬 wind station), and the favourites can be changed at any time via the integration options.

Each station becomes a device with sensors for what it actually measures, updated every 30 minutes via the **official, documented SLF measurement API** ([measurement-api.slf.ch](https://measurement-api.slf.ch/)):

| Sensor | Stations |
|---|---|
| Snow depth (cm) and new snow last 24 h (cm) | snow stations |
| Air temperature, snow surface temperature, humidity | most stations |
| Wind speed, gusts, direction | wind stations and many snow stations |

Their entity ids are built from the station code and the same four-character entry part as the bulletin sensors, `sensor.slf_imis_<code>_<xxxx>_<measurement>` — e.g. `sensor.slf_imis_slf2_ab12_snow_height`; entities created before 1.3.0 keep `sensor.slf_imis_slf2_snow_height` — and are suggested by the integration itself, independent of the Home Assistant language.

A value is only reported as current if it was measured within the last 3 hours; the `measure_date` attribute tells when the shown value was measured. The sensors of a station that cannot be fetched are `unavailable` until it answers again, and a station that is unreachable when Home Assistant starts gets its sensors as soon as it does — no reload needed.

## Bundled card & dashboard

The integration ships a Lovelace card, **SLF IMIS Station** (`custom:slf-imis-station-card`), with a visual editor — snow depth as the hero value, temperatures, wind with direction arrow, measurement age and the required SLF attribution — and, in the same file, a **dashboard strategy** that assembles a complete avalanche dashboard from your config entries at display time.

The card file is served by the integration, but you register it as a Lovelace resource yourself — the integration does not write to your dashboard configuration. It is a one-time step.

### Adding the card as a resource (once)

**Settings → Dashboards → ⋮ (top right) → Resources → + Add resource** — the *Resources* entry is only shown when **Advanced mode** is enabled in your user profile (click your name at the bottom of the sidebar).

| Field | Value |
|---|---|
| URL | `/slf_avalanche/static/slf-imis-card.js?v=1.3.0` |
| Resource type | JavaScript module |

Then reload the page (Ctrl/Cmd+Shift+R). The card appears as **SLF IMIS Station** in the normal card picker, with its visual editor; the same file also contains the [dashboard strategy](#dashboard), so this one resource covers both.

> **After updating the integration:** the card file is served with long-lived cache headers, so your browser may keep the old copy. The `?v=` part of the URL is only there to defeat that cache — if a new feature does not show up after an update, raise it to the new version (or do a hard reload, Ctrl+F5 / Cmd+Shift+R).

### Dashboard

The strategy is a recipe Home Assistant renders in the browser, rather than a dashboard written into your configuration. Nothing is stored, nothing is overwritten, and the result follows your config entries — add a location or a station favourite and it appears on the next page load; remove one and it is gone, with no leftover card.

Requires the card [registered as a resource](#adding-the-card-as-a-resource-once) (the strategy ships in the same file). Then:

1. **Settings → Dashboards → + Add dashboard → New dashboard from scratch**, give it a name.
2. Open it, then **✏️ (edit) → ⋮ → Raw configuration editor**.
3. Replace the entire content with:

```yaml
strategy:
  type: custom:swiss-avalanche-bulletin
views: []
```

4. Save.

You get one **Avalanches** view (two columns) with:

- one full-width section per **bulletin location** — a heading named after the location's device, with the current danger level as a badge, then tiles for the danger level, the warning region and the up to three avalanche problems (outside the season the problems simply read "unknown");
- one full-width section per **IMIS entry** — "IMIS measuring stations" with a station card per favourite, two side by side.

The strategy also appears under **+ Add dashboard** as *Swiss Avalanche Bulletin*, which does the same thing without the raw editor.

Everything the strategy produces is a normal Home Assistant dashboard. If you would rather arrange things yourself, build your own dashboard with the bundled card and the entities above — the strategy is an offer, not a requirement.

### Adjusting the strategy

A strategy dashboard has no card editor — the layout is generated fresh on every load. You still have two ways to shape it without giving that up:

**Options.** Anything you add under `strategy:` is passed to the recipe:

```yaml
strategy:
  type: custom:swiss-avalanche-bulletin
  title: My title
  max_columns: 3
views: []
```

| Option | Effect |
|---|---|
| `title` | dashboard title |
| `max_columns` | column count of the generated view |

**One view inside your own dashboard.** Instead of a separate dashboard, let the strategy fill a single view of one you already have. Open your dashboard's raw configuration editor and add a view:

```yaml
views:
  - title: Home
    # ... your own cards ...
  - title: Avalanches
    strategy:
      type: custom:swiss-avalanche-bulletin
```

That view is regenerated like the full dashboard is, so new config entries still appear by themselves, while every other view stays yours to edit. The same options work here too.

> **Take control** (⋮ menu) turns a strategy dashboard into a static one you can edit card by card — but it is one-way: the dashboard stops following your config entries from then on. Prefer the two approaches above.

### Building it yourself

Add the cards wherever you like. An IMIS station card takes the station part of the station's entity ids: the lower-case station code followed by the four-character entry part, e.g. `slf2_ab12` — or just `slf2` for entries created before 1.3.0. The card's visual editor lists the stations it finds, so you rarely have to type it:

```yaml
type: custom:slf-imis-station-card
station: slf2_ab12
```

For a bulletin location, plain tile cards on the two sensors work well:

```yaml
type: tile
entity: sensor.slf_avalanche_danger_level_home_ab12
color: red
```

```yaml
type: tile
entity: sensor.slf_avalanche_region_home_ab12
```

Replace `home_ab12` with your location label and entry part, and check the exact entity IDs under **Settings → Devices & Services → Entities**.

## Language

Entity names, device info, and the danger-level/avalanche-problem text all follow the official multilingual EAWS (European Avalanche Warning Services) terminology and adapt automatically to your Home Assistant language setting — German, English, French, and Italian are supported, with English as the fallback for any other language. The bundled card and the dashboard strategy follow the language of the Home Assistant frontend the same way.

## Installation

### HACS (recommended)

1. Open **HACS**, search for **"Swiss Avalanche Bulletin"** and download it — or use the button, which opens the integration directly in your HACS:

   [![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=prusuino&repository=ha_swiss_avalanche_bulletin&category=integration)

2. Restart Home Assistant.

Until the integration shows up in the HACS search, the button above adds it as a custom repository.

### Manual

1. Copy the `custom_components/slf_avalanche` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Setup

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **"Swiss Avalanche Bulletin (SLF)"**.
3. Choose what to set up: **avalanche bulletin for a location** or **IMIS measuring stations**.
4. Bulletin: latitude/longitude default to your Home Assistant home location — adjust if you want a different location (e.g. a specific mountain area), and optionally give it a label. Stations: pick any stations from the searchable list.
5. Done. Add the integration again for additional locations or station sets.

## Data source & license

This integration reads live data from the SLF's public bulletin API (`aws.slf.ch`) and the official SLF measurement API (`measurement-api.slf.ch`). That data is licensed under **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**, separate from this repository's MIT license — see [NOTICE.md](NOTICE.md) for the required attribution. Every sensor and the bundled card set the SLF attribution accordingly.

## Notes

- Only relevant for locations in or near Switzerland — the SLF's ~150 warning regions cover the country and adjacent border areas.
- This integration is unofficial and not affiliated with, endorsed by, or supported by the SLF. It only reads their published open data.
- If the SLF API is unreachable or its format changes, entities become `unavailable` rather than reporting a stale or incorrect value. The sensors of a single IMIS station that cannot be fetched become `unavailable` on their own while the other stations keep updating.
- **This is informational only.** Avalanche danger assessment requires proper training and terrain judgment. Never use this integration as your sole basis for backcountry travel decisions — always consult the official bulletin at [slf.ch](https://www.slf.ch/en/avalanche-bulletin-and-snow-situation/) directly.

## Disclaimer

This integration is provided **as-is, without any warranty**. Data is retrieved from a third-party published source and may be inaccurate, delayed, incomplete, or unavailable. Do not rely on it as your sole source for safety-critical or life-and-death decisions such as backcountry travel or ski touring — always consult the official SLF bulletin and use proper avalanche safety training and equipment. The author(s) accept **no responsibility or liability** for any damage, injury, loss, incorrect readings, or other issues arising from using this integration, whether it stops working, behaves unexpectedly, or never worked correctly for your setup in the first place.

## License

Source code: MIT — see [LICENSE](LICENSE). Avalanche bulletin data: CC BY 4.0 (SLF) — see [NOTICE.md](NOTICE.md).

## Related integrations

More Home Assistant integrations from the same author:

- [Swiss Waters](https://github.com/prusuino/ha_swiss_waters) — live water temperature, water level, discharge and flood danger levels of Swiss rivers and lakes
- [Swiss Charging Stations](https://github.com/prusuino/ha_swiss_charging_stations) — real-time availability and prices of public EV charging stations in Switzerland
- [Austrian Charging Stations](https://github.com/prusuino/ha_austrian_charging_stations) — real-time availability of public EV charging stations in Austria
- [Swiss Transport](https://github.com/prusuino/ha_swiss_transport) — live public-transport departure boards and saved connections
- [Swiss Parking](https://github.com/prusuino/ha_swiss_parking) — live free parking spaces in Swiss cities
- [Swiss Electricity Price](https://github.com/prusuino/ha_swiss_electricity_price) — electricity tariffs of any Swiss grid operator (ElCom)
- [Swiss Solar Reference Price](https://github.com/prusuino/ha_swiss_solar_reference_price) — the Swiss solar reference market price (SFOE)
- [Swiss Earthquakes](https://github.com/prusuino/ha_swiss_earthquakes) — recent Swiss earthquakes on the built-in map
- [Swiss Public Alerts](https://github.com/prusuino/ha_swiss_public_alerts) — official Swiss public alerts (Alertswiss) with home-location matching
- [Innoxel Master 3](https://github.com/prusuino/ha_innoxel_master3) — local control of the Innoxel Master 3 home-automation system
- [Swiss Hail Protection](https://github.com/prusuino/ha_swiss_hail_protection) — Swiss hail warnings for your blinds: the official VKF hail-protection signal or the MeteoSwiss hail radar around your location

## Support

If this integration is useful to you, you can support its development:

<a href="https://www.buymeacoffee.com/prusuino"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="41"></a>
