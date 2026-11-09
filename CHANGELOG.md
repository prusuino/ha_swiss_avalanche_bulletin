# Changelog

## 1.6.1 — 2026-11-09

- **Version on the service card.** The integration's version now appears on its service card under Settings → Devices & services, where the entities are listed.

## 1.6.0 — 2026-11-09

- **Quality scale Bronze.** The integration keeps its coordinators in the config entry's runtime data, the README gained removal instructions and a quality-scale section, and the manifest declares the **bronze** tier. A test suite (bulletin region lookup, worst danger rating, station distances, IMIS measurement merge, config flow for bulletin and IMIS with duplicate, unreachable service, taken station and reconfigure) runs on every push. No change to entities or configuration.

## 1.5.0 — 2026-11-08

- **New: repair notices.** A notice under **Settings → Repairs** when the SLF service has not answered for three refreshes in a row, when the SLF knows no warning region for a bulletin location (with a pointer to *Reconfigure*), and when an IMIS station could not be fetched for six hours. Each clears itself when the data is back. In all four languages.
- **New: triggers and conditions in the automation editor** (Home Assistant 2026.10 / 2026.11 or newer). Triggers: *Avalanche danger level reached* (from a minimum level, fires once when the level is reached) and *Avalanche danger level changed*; conditions: *Avalanche danger level is at least* and *Avalanche danger level is below*. They target the danger-level sensors of your bulletin locations, in all four languages; on older versions the entries are simply not offered.
- **New: a blueprint, *notify on danger level*.** One-click import from the README: picks the danger-level sensors of your locations, a minimum level and your phone, and sends region, level, the level's meaning and the bulletin's validity once when the level is reached; an action field takes your own steps with the text as `{{ message }}`.
- **New: reconfigure an entry in place.** The entry's menu under **Settings → Devices & services** now offers *Reconfigure*: a bulletin entry takes a new location or label (the warning region is resolved again), an IMIS entry another set of favourite stations. Entities keep their ids and history, the device name follows the label, and the devices of stations that are no longer selected are removed. A location another entry already uses is refused. The options dialog of a bulletin entry now points to Reconfigure instead of saying there is nothing to set.

## 1.4.1 — 2026-11-06

- **Fixed: the diagnostics download could contain private values.** The entry's unique id went out unredacted: depending on the integration it holds the coordinates of the entry or, for a VKF entry of Swiss Hail Protection, the device serial. The text of the last error could also repeat a request URL. The unique id, the entry title and the entry's name and location fields are now redacted, and only the type of the last error is reported. If you have shared a diagnostics file from the previous version, consider it exposed.

## 1.4.0 — 2026-11-06

- **New: diagnostics download.** The entry menu under **Settings → Devices & services** offers *Download diagnostics*: the entry's configuration, what was last fetched and the current state of its entities, with coordinates, credentials and other personal values redacted and long lists cut. Attach it to an issue report.

## 1.3.1 — 2026-11-05

- **Maintenance release for the Home Assistant Marketplace.** Home Assistant 2026.11 replaces HACS with the built-in Marketplace (Settings → Marketplace); the README now describes installation and updates through it. The release ships the integration as a zip asset, which the Marketplace (and HACS) download in one piece.
- **Changed: the declared minimum Home Assistant version is 2025.4** (was 2024.12). The code itself needs nothing newer than before; this aligns the floor across the author's integrations to the version they are tested against.
- Internal: `DeviceInfo` is imported from the device registry helper and config-flow results are typed as `ConfigFlowResult`, following current Home Assistant conventions. No behaviour changes.
- No functional changes. Existing entities, their ids and your configuration are unchanged.

## 1.3.0 — 2026-08-29

Follow-ups from a review of the integration. Nothing to do after
updating: existing entities keep their entity ids, devices and history.

**Fixed:**

- IMIS sensors of a station that cannot be fetched now become
  `unavailable`, as the README promised all along, instead of staying
  "available" with an unknown value while the other stations keep
  updating.
- A station that is unreachable when Home Assistant starts gets its
  sensors as soon as it answers — no reload needed. Sensors it had in an
  earlier run show up as unavailable in the meantime instead of being
  missing.
- A measured value is only reported as current if it was measured within
  the last 3 hours, judged by the record's timestamp against the clock,
  and the `measure_date` attribute now belongs to the value shown.
  Previously a value up to 24 h old could be shown with the timestamp of
  the newest record.
- An unreachable IMIS station is logged once when it fails and once when
  it is back, instead of a warning every 30 minutes.
- The setup and options dialogs tell an unexpected error apart from
  "cannot connect", and a station that is already a favourite of another
  entry is rejected instead of being added a second time.
- The dashboard strategy no longer produces an "IMIS measuring stations"
  section with nothing but its heading when every station of an entry is
  hidden, and its sections follow `max_columns` (they stayed two columns
  wide with `max_columns: 3` or more).

**Changed:**

- Suggested entity ids of newly created entities end in the last four
  characters of the config entry id, e.g.
  `sensor.slf_avalanche_danger_level_home_ab12` and
  `sensor.slf_imis_slf2_ab12_snow_height`, so two locations with the same
  label or two entries with the same station can never collide. This only
  affects entities created from now on: a suggested id applies when an
  entity is created for the first time, entities that already exist keep
  their ids. The bundled card and the strategy work with both forms.
- The stations of an IMIS entry are fetched at the same time instead of
  one after the other, so setup no longer waits for one request per
  station.
- The bulletin and station coordinators carry the entry's label in their
  log lines, so several entries can be told apart.
- SECURITY.md now says exactly what is sent where: HTTPS only, two SLF
  hosts, the configured coordinates for the warning-region lookup, and the
  station codes and current date that travel in the request URLs.
- Updated the bundled dashboard-strategy core to 1.1.1: `map: false` now
  also removes a map section inside a view, `max_columns` is honoured in
  the view-strategy flavour, and a view's header is kept when the strategy
  fills a single view.

**Upgrading:**

- The card file changed, so raise the `?v=` on the resource URL (e.g.
  `?v=1.3.0`) or do a hard reload if the old copy is still served.
- The minimum Home Assistant version stays at 2024.12.0.

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
