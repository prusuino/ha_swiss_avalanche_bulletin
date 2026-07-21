# Swiss Avalanche Bulletin (SLF)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
<a href="https://www.buymeacoffee.com/prusuino"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" height="20"></a>

A Home Assistant custom integration for the official Swiss **avalanche bulletin**, published by the **WSL Institute for Snow and Avalanche Research (SLF)**.

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

Data is refreshed every hour. The bulletin itself is typically published once daily (around 17:00), with interim updates during high-danger situations.

## Language

Entity names, device info, and the danger-level/avalanche-problem text all follow the official multilingual EAWS (European Avalanche Warning Services) terminology and adapt automatically to your Home Assistant language setting — German, English, French, and Italian are supported, with English as the fallback for any other language.

## Installation

### HACS (recommended)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**, add this repository URL with category **Integration**.
2. Search for **"Swiss Avalanche Bulletin"** and install.
3. Restart Home Assistant.

### Manual

1. Copy the `custom_components/slf_avalanche` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Setup

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **"Swiss Avalanche Bulletin (SLF)"**.
3. Latitude/longitude default to your Home Assistant home location — adjust if you want a different location (e.g. a specific mountain area), and optionally give it a label.
4. Done. Add the integration again for additional locations.

## Data source & license

This integration reads live data from the SLF's public API. That data is licensed under **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**, separate from this repository's MIT license — see [NOTICE.md](NOTICE.md) for the required attribution. Every sensor sets Home Assistant's `attribution` attribute accordingly.

## Notes

- Only relevant for locations in or near Switzerland — the SLF's ~150 warning regions cover the country and adjacent border areas.
- This integration is unofficial and not affiliated with, endorsed by, or supported by the SLF. It only reads their published open data.
- If the SLF API is unreachable or its format changes, entities become `unavailable` rather than reporting a stale or incorrect value.
- **This is informational only.** Avalanche danger assessment requires proper training and terrain judgment. Never use this integration as your sole basis for backcountry travel decisions — always consult the official bulletin at [slf.ch](https://www.slf.ch/en/avalanche-bulletin-and-snow-situation/) directly.

## Disclaimer

This integration is provided **as-is, without any warranty**. Data is retrieved from a third-party published source and may be inaccurate, delayed, incomplete, or unavailable. Do not rely on it as your sole source for safety-critical or life-and-death decisions such as backcountry travel or ski touring — always consult the official SLF bulletin and use proper avalanche safety training and equipment. The author(s) accept **no responsibility or liability** for any damage, injury, loss, incorrect readings, or other issues arising from using this integration, whether it stops working, behaves unexpectedly, or never worked correctly for your setup in the first place.

## License

Source code: MIT — see [LICENSE](LICENSE). Avalanche bulletin data: CC BY 4.0 (SLF) — see [NOTICE.md](NOTICE.md).

## Related integrations

More Home Assistant integrations from the same author:

- [Swiss Charging Stations](https://github.com/prusuino/ha_swiss_charging_stations) — real-time availability and prices of public EV charging stations in Switzerland
- [Austrian Charging Stations](https://github.com/prusuino/ha_austrian_charging_stations) — real-time availability of public EV charging stations in Austria
- [Swiss Transport](https://github.com/prusuino/ha_swiss_transport) — live public-transport departure boards and saved connections
- [Swiss Parking](https://github.com/prusuino/ha_swiss_parking) — live free parking spaces in Swiss cities
- [Swiss Electricity Price](https://github.com/prusuino/ha_swiss_electricity_price) — electricity tariffs of any Swiss grid operator (ElCom)
- [eug Electricity Price](https://github.com/prusuino/ha_swiss_eug_electricity_price) — electricity tariffs of eug Elektra Untergäu
- [Swiss Solar Reference Price](https://github.com/prusuino/ha_swiss_solar_reference_price) — the Swiss solar reference market price (SFOE)
- [Swiss Earthquakes](https://github.com/prusuino/ha_swiss_earthquakes) — recent Swiss earthquakes on the built-in map
- [Swiss Public Alerts](https://github.com/prusuino/ha_swiss_public_alerts) — official Swiss public alerts (Alertswiss) with home-location matching
- [Innoxel Master 3](https://github.com/prusuino/ha_innoxel_master3) — local control of the Innoxel Master 3 home-automation system

## Support

If this integration is useful to you, you can support its development:

<a href="https://www.buymeacoffee.com/prusuino"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="41"></a>
