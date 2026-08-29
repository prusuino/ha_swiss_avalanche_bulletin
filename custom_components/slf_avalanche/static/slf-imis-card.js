/* SLF IMIS station card — shipped by the Swiss Avalanche Bulletin
 * integration and served under /slf_avalanche/static/. Register it once
 * as a Lovelace resource (JavaScript module); see the README.
 *
 *   slf-imis-station-card   snow, temperature and wind of one IMIS station
 *
 * The card provides a visual editor (getConfigElement) and follows the
 * Home Assistant frontend language (de/en/fr/it).
 *
 * The same file also carries the dashboard strategy
 * (custom:swiss-avalanche-bulletin) at the bottom, so that one resource
 * covers both.
 */

const SLF_IMIS_L10N = {
  de: {
    snow_height: 'Schneehöhe', new_snow: 'Neuschnee 24 h', air: 'Luft',
    surface: 'Schneeoberfläche', humidity: 'Luftfeuchtigkeit', wind: 'Wind',
    gusts: 'Böen', measured: 'Gemessen', station: 'Station', no_data: 'Keine Daten',
    attribution: 'Daten: WSL-Institut für Schnee- und Lawinenforschung SLF',
  },
  en: {
    snow_height: 'Snow depth', new_snow: 'New snow 24 h', air: 'Air',
    surface: 'Snow surface', humidity: 'Humidity', wind: 'Wind',
    gusts: 'Gusts', measured: 'Measured', station: 'Station', no_data: 'No data',
    attribution: 'Data: WSL Institute for Snow and Avalanche Research SLF',
  },
  fr: {
    snow_height: 'Hauteur de neige', new_snow: 'Neige fraîche 24 h', air: 'Air',
    surface: 'Surface de la neige', humidity: 'Humidité', wind: 'Vent',
    gusts: 'Rafales', measured: 'Mesuré', station: 'Station', no_data: 'Pas de données',
    attribution: "Données : Institut pour l'étude de la neige et des avalanches SLF",
  },
  it: {
    snow_height: 'Altezza della neve', new_snow: 'Neve fresca 24 h', air: 'Aria',
    surface: 'Superficie della neve', humidity: 'Umidità', wind: 'Vento',
    gusts: 'Raffiche', measured: 'Misurato', station: 'Stazione', no_data: 'Nessun dato',
    attribution: 'Dati: Istituto per lo studio della neve e delle valanghe SLF',
  },
};

function slfImisLang(hass) {
  const lang = ((hass && hass.language) || 'en').split('-')[0];
  return SLF_IMIS_L10N[lang] || SLF_IMIS_L10N.en;
}

function slfImisEsc(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

/* Station slugs present in the state machine: sensor.slf_imis_<slug>_<key>.
 * The slug is the lower-case station code, followed since 1.3.0 by the
 * last four characters of the config entry id (e.g. slf2_ab12). */
function slfImisStations(hass) {
  const found = new Map();
  if (!hass) return [];
  for (const id of Object.keys(hass.states)) {
    const m = id.match(/^sensor\.slf_imis_(.+)_(snow_height|air_temperature|wind_speed|wind_direction|humidity)$/);
    if (!m) continue;
    if (!found.has(m[1])) {
      const attrs = hass.states[id].attributes || {};
      found.set(m[1], attrs.station_name ? `${attrs.station_name} (${attrs.station_code})` : m[1].toUpperCase());
    }
  }
  return [...found.entries()].map(([value, label]) => ({ value, label }));
}

function slfImisState(hass, station, key) {
  const st = hass.states[`sensor.slf_imis_${station}_${key}`];
  if (!st || st.state === 'unknown' || st.state === 'unavailable') return null;
  const value = Number(st.state);
  return Number.isFinite(value) ? { value, attrs: st.attributes || {} } : null;
}

function slfImisCardinal(deg) {
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  return dirs[Math.round(((deg % 360) + 360) % 360 / 45) % 8];
}

function slfImisAgo(iso, lang) {
  if (!iso) return '';
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return { de: `vor ${minutes} min`, en: `${minutes} min ago`, fr: `il y a ${minutes} min`, it: `${minutes} min fa` }[lang] || `${minutes} min`;
  const hours = Math.round(minutes / 60);
  return { de: `vor ${hours} h`, en: `${hours} h ago`, fr: `il y a ${hours} h`, it: `${hours} h fa` }[lang] || `${hours} h`;
}

class SlfImisStationCard extends HTMLElement {
  static getConfigElement() { return document.createElement('slf-imis-station-card-editor'); }

  static getStubConfig(hass) {
    const stations = slfImisStations(hass);
    return { station: stations.length ? stations[0].value : '' };
  }

  setConfig(config) {
    if (!config.station) throw new Error('station required');
    this._config = config;
    this._built = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) { this._build(); this._built = true; }
    this._render();
  }

  getCardSize() { return 4; }

  _build() {
    const r = this.attachShadow ? (this.shadowRoot || this.attachShadow({ mode: 'open' })) : this;
    r.innerHTML = `
      <style>
        :host { display: block; height: 100%; }
        ha-card { padding: 16px; height: 100%; box-sizing: border-box;
                  display: flex; flex-direction: column; }
        .head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
        .name { font-size: 1.05rem; font-weight: 600; }
        .meta { color: var(--secondary-text-color); font-size: .8rem; white-space: nowrap; }
        #body { flex: 1; }
        .hero { display: flex; align-items: center; gap: 14px; margin: 14px 0 6px; }
        .hero .icon { font-size: 2.2rem; line-height: 1; }
        .hero .value { font-size: 2.4rem; font-weight: 300; line-height: 1; }
        .hero .unit { font-size: 1.1rem; color: var(--secondary-text-color); }
        .hero .label { color: var(--secondary-text-color); font-size: .8rem; margin-top: 2px; }
        .chip { display: inline-block; background: var(--secondary-background-color); border-radius: 12px;
                padding: 2px 10px; font-size: .8rem; margin: 2px 4px 2px 0; }
        .rows { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
        .row { display: flex; justify-content: space-between; align-items: baseline;
               gap: 12px; font-size: .9rem; }
        .row .k { color: var(--secondary-text-color); overflow: hidden;
                  text-overflow: ellipsis; white-space: nowrap; }
        .row .v { white-space: nowrap; }
        .wind-arrow { display: inline-block; }
        .foot { margin-top: 12px; color: var(--secondary-text-color); font-size: .72rem;
                display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
      </style>
      <ha-card>
        <div class="head"><div class="name" id="name"></div><div class="meta" id="meta"></div></div>
        <div id="body"></div>
        <div class="foot"><span id="measured"></span><span id="attr"></span></div>
      </ha-card>`;
    this._el = {
      name: r.getElementById('name'), meta: r.getElementById('meta'),
      body: r.getElementById('body'), measured: r.getElementById('measured'),
      attr: r.getElementById('attr'),
    };
  }

  _render() {
    const hass = this._hass;
    if (!hass) return;
    const L = slfImisLang(hass);
    const lang = ((hass.language || 'en')).split('-')[0];
    const station = this._config.station;

    const hs = slfImisState(hass, station, 'snow_height');
    const hn = slfImisState(hass, station, 'new_snow_1d');
    const ta = slfImisState(hass, station, 'air_temperature');
    const tss = slfImisState(hass, station, 'snow_surface_temperature');
    const rh = slfImisState(hass, station, 'humidity');
    const vw = slfImisState(hass, station, 'wind_speed');
    const vg = slfImisState(hass, station, 'wind_gust');
    const dw = slfImisState(hass, station, 'wind_direction');

    const any = hs || ta || vw;
    const attrs = (any || { attrs: {} }).attrs;
    const title = this._config.title
      || (attrs.station_name ? `${attrs.station_name} (${attrs.station_code})` : station.toUpperCase());
    this._el.name.textContent = title;
    const meta = [];
    if (attrs.elevation != null) meta.push(`${Math.round(attrs.elevation)} m`);
    if (attrs.distance_km != null) meta.push(`${attrs.distance_km} km`);
    this._el.meta.textContent = meta.join(' · ');

    let html = '';
    if (hs) {
      html += `<div class="hero"><div class="icon">❄️</div><div>
        <div><span class="value">${Math.round(hs.value)}</span> <span class="unit">cm</span></div>
        <div class="label">${L.snow_height}</div></div></div>`;
      if (hn && hn.value > 0) html += `<span class="chip">🌨 ${L.new_snow}: ${Math.round(hn.value)} cm</span>`;
    }
    const rows = [];
    if (ta) rows.push([L.air, `${ta.value.toFixed(1)} °C`]);
    if (tss) rows.push([L.surface, `${tss.value.toFixed(1)} °C`]);
    if (rh) rows.push([L.humidity, `${Math.round(rh.value)} %`]);
    if (vw) {
      let windText = `${(vw.value * 3.6).toFixed(0)} km/h`;
      if (vg) windText += ` (${L.gusts} ${(vg.value * 3.6).toFixed(0)})`;
      if (dw) windText += ` <span class="wind-arrow" style="transform: rotate(${Math.round(dw.value) + 180}deg)">↑</span> ${slfImisCardinal(dw.value)}`;
      rows.push([L.wind, windText]);
    }
    if (rows.length) {
      html += `<div class="rows">${rows.map(([k, v]) =>
        `<div class="row"><span class="k">${slfImisEsc(k)}</span><span class="v">${v}</span></div>`).join('')}</div>`;
    }
    if (!html) html = `<div class="rows">${L.no_data}</div>`;
    this._el.body.innerHTML = html;

    this._el.measured.textContent = attrs.measure_date
      ? `${L.measured}: ${slfImisAgo(attrs.measure_date, lang)}` : '';
    this._el.attr.textContent = L.attribution;
  }
}

class SlfImisStationCardEditor extends HTMLElement {
  setConfig(config) { this._config = { ...config }; this._renderForm(); }
  set hass(hass) { this._hass = hass; this._renderForm(); }

  _renderForm() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement('ha-form');
      this._form.computeLabel = (s) => ({
        station: 'IMIS station', title: 'Card title (optional)',
      }[s.name] || s.name);
      this._form.addEventListener('value-changed', (ev) => {
        this._config = { ...this._config, ...ev.detail.value };
        this.dispatchEvent(new CustomEvent('config-changed', {
          detail: { config: this._config }, bubbles: true, composed: true,
        }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = [
      {
        name: 'station',
        required: true,
        selector: { select: { options: slfImisStations(this._hass), mode: 'dropdown' } },
      },
      { name: 'title', selector: { text: {} } },
    ];
  }
}

customElements.define('slf-imis-station-card-editor', SlfImisStationCardEditor);
customElements.define('slf-imis-station-card', SlfImisStationCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'slf-imis-station-card',
  name: 'SLF IMIS Station',
  description: 'Snow depth, temperatures and wind of an SLF IMIS measuring station',
});

/* ===================================================================== */
/* The strategy block below is wrapped in an IIFE: several of these       */
/* integrations ship the same core, and without the wrapper two of them   */
/* installed side by side would declare the same consts in one scope.     */
/* ===================================================================== */
(() => {
/* =====================================================================
 * Dashboard strategy core — shared building blocks
 * =====================================================================
 * A Lovelace dashboard strategy generates a dashboard in the browser at
 * render time. Nothing is written to .storage: the dashboard belongs to
 * the user, the integration only supplies the recipe.
 *
 * ⚠️ This block is duplicated into every integration that ships a
 * strategy. Each integration is its own HACS repository and must not
 * depend on another one being installed, so a shared file is not an
 * option. Keep the copies in sync and bump CORE_VERSION when the shared
 * part changes — it identifies which revision a copy was taken from.
 * ===================================================================== */

const CORE_VERSION = "1.1.1";

/* 1.1.1 - review follow-ups on the `strategy:` options
 *   (a) `map: false` only dropped the view with path "map". Where the map is
 *       a section inside another view (or a card in a panel view) it stayed
 *       visible. The option now also strips map cards out of every view: a
 *       section left with nothing but headings is dropped, and a view that
 *       ends up without any sections or cards is dropped as well.
 *   (b) The view flavour hardcoded max_columns: 2 and discarded the user's
 *       `max_columns`. It now uses the option when valid, else the value of
 *       the first sections view, else 2.
 *   (c) The view flavour copied only sections and cards, losing a view's
 *       `header` and `badges`. Both are carried over from the first view
 *       that has them. */

/* --- Registry access -------------------------------------------------
 * The registries are the only reliable way to find an integration's
 * entities: entity_id patterns are user-editable, unique_id is not.
 * Both calls are cheap and cached by the frontend for the render pass.
 */
async function loadRegistry(hass) {
  const [entities, devices] = await Promise.all([
    hass.callWS({ type: "config/entity_registry/list" }),
    hass.callWS({ type: "config/device_registry/list" }),
  ]);
  return { entities, devices };
}

/** All registry entries belonging to one integration (platform == domain). */
function entriesOfDomain(entities, domain) {
  return entities.filter((e) => e.platform === domain && !e.disabled_by);
}

/** Registry entries of one config entry, keyed by unique_id suffix.
 *  Mirrors the `f"{entry_id}_{suffix}"` convention the integrations use. */
function bySuffix(entities, configEntryId) {
  const out = {};
  const prefix = `${configEntryId}_`;
  for (const e of entities) {
    if (e.config_entry_id !== configEntryId) continue;
    if (typeof e.unique_id === "string" && e.unique_id.startsWith(prefix)) {
      out[e.unique_id.slice(prefix.length)] = e.entity_id;
    }
  }
  return out;
}

/** Group an integration's entities by the device they belong to.
 *  Returns [{device, entities:[registryEntry,...]}] sorted by device name. */
function groupByDevice(domainEntries, devices) {
  const byId = new Map(devices.map((d) => [d.id, d]));
  const groups = new Map();
  for (const e of domainEntries) {
    if (!e.device_id) continue;
    if (!groups.has(e.device_id)) groups.set(e.device_id, []);
    groups.get(e.device_id).push(e);
  }
  return [...groups.entries()]
    .map(([id, list]) => ({ device: byId.get(id), entities: list }))
    .filter((g) => g.device)
    .sort((a, b) => deviceName(a.device).localeCompare(deviceName(b.device)));
}

function deviceName(device) {
  return device.name_by_user || device.name || "";
}

/* --- Card helpers ---------------------------------------------------- */

const heading = (text, icon, badges) => {
  const card = { type: "heading", heading: text };
  if (icon) card.icon = icon;
  if (badges && badges.length) card.badges = badges;
  return card;
};

const grid = (cards, columnSpan) => {
  const section = { type: "grid", cards: cards.filter(Boolean) };
  if (columnSpan) section.column_span = columnSpan;
  return section;
};

const tile = (entity, extra = {}) => ({ type: "tile", entity, ...extra });

/** Map card fed from the integration's geo_location source.
 *  Deliberately uses geo_location_sources instead of an entity list: the
 *  markers are hidden entities, and the source keeps working when the
 *  set of markers changes between renders.
 *  labelAttribute writes the marker label into the source object, which is
 *  where the map card reads a geo-location source's label config from — the
 *  card-level label_mode only applies to `entities`. */
const mapCard = (domain, opts = {}) => ({
  type: "map",
  geo_location_sources: [
    opts.labelAttribute
      ? { source: domain, label_mode: "attribute", attribute: opts.labelAttribute }
      : domain,
  ],
  entities: opts.entities || ["zone.home"],
  default_zoom: opts.zoom ?? 8,
  theme_mode: "auto",
  grid_options: { columns: 12, rows: opts.rows ?? 6 },
});

/** Shown instead of an empty dashboard — an empty dashboard looks broken
 *  and gives the user nothing to act on. */
const emptyNotice = (text) => ({
  type: "markdown",
  content: text,
});

/* --- Localisation ----------------------------------------------------
 * Strategies run in the frontend, so hass.language is authoritative.
 * Falls back to English for any language the integration does not ship.
 */
function translator(strings, hass) {
  const lang = (hass.language || "en").split("-")[0];
  const table = strings[lang] || strings.en;
  return (key) => (table && table[key]) || (strings.en && strings.en[key]) || key;
}

/* --- Strategy base ---------------------------------------------------
 * Wraps the parts every strategy repeats: load registries, bail out
 * gracefully when the integration is not set up, and hand the concrete
 * strategy a prepared context.
 */

/* Options a user may put under `strategy:` in the raw configuration editor.
 * They are handled here in the core, so every integration supports the same
 * set without shipping its own option code:
 *
 *   map: false        drop the map: the full-screen map view as well as the
 *                     map cards inside section and panel views
 *   title: "..."      override the title
 *   max_columns: 3    column count of the generated section views (the view
 *                     flavour honours it too)
 *
 * Unknown keys are ignored on purpose - a strategy config is free-form, and a
 * typo should not take the dashboard down. */
const validColumns = (value) => {
  const cols = Number(value);
  return Number.isFinite(cols) && cols > 0 ? cols : undefined;
};

const isMapCard = (card) => Boolean(card) && card.type === "map";
const isHeadingCard = (card) => Boolean(card) && card.type === "heading";

/* Remove the map cards of one view. A section is dropped once only headings
 * remain - a heading merely labels the map that was just removed. Returns
 * null when nothing is left to show; views without a map card come back
 * untouched. */
const withoutMapCards = (view) => {
  let touched = false;
  const out = { ...view };
  if (Array.isArray(view.sections)) {
    out.sections = [];
    for (const section of view.sections) {
      const cards = Array.isArray(section.cards) ? section.cards : [];
      if (!cards.some(isMapCard)) {
        out.sections.push(section);
        continue;
      }
      touched = true;
      const rest = cards.filter((c) => !isMapCard(c));
      if (rest.some((c) => !isHeadingCard(c))) out.sections.push({ ...section, cards: rest });
    }
  }
  if (Array.isArray(view.cards) && view.cards.some(isMapCard)) {
    touched = true;
    out.cards = view.cards.filter((c) => !isMapCard(c));
  }
  if (!touched) return view;
  const empty = !(out.sections && out.sections.length) && !(out.cards && out.cards.length);
  return empty ? null : out;
};

const applyViewOptions = (views, config) => {
  const cfg = config || {};
  let out = views;
  if (cfg.map === false) {
    out = out
      .filter((v) => v.path !== "map")
      .map(withoutMapCards)
      .filter(Boolean);
  }
  const cols = validColumns(cfg.max_columns);
  if (cols) {
    out = out.map((v) => (v.type === "sections" ? { ...v, max_columns: cols } : v));
  }
  return out;
};

/* A view strategy must return exactly ONE view, while build() yields a list.
 * Section views are merged by concatenating their sections. A panel view (the
 * map) has no sections, so its cards become one full-width section instead -
 * that keeps the map visible rather than silently dropping it. */
const flattenToView = (views, title, icon, config) => {
  const sections = [];
  for (const v of views) {
    if (Array.isArray(v.sections) && v.sections.length) {
      sections.push(...v.sections);
    } else if (Array.isArray(v.cards) && v.cards.length) {
      sections.push(
        grid(
          v.cards.map((c) => ({
            ...c,
            grid_options: { columns: "full", rows: (c.grid_options || {}).rows ?? 8 },
          }))
        )
      );
    }
  }
  const sized = views.find((v) => v.type === "sections" && validColumns(v.max_columns));
  const view = {
    title,
    icon,
    type: "sections",
    max_columns: validColumns((config || {}).max_columns) ?? (sized ? validColumns(sized.max_columns) : 2),
    sections,
  };
  // header and badges live outside the sections and would be lost by the
  // merge above - keep the first ones the build produced.
  const withHeader = views.find((v) => v.header);
  if (withHeader) view.header = withHeader.header;
  const withBadges = views.find((v) => Array.isArray(v.badges) && v.badges.length);
  if (withBadges) view.badges = withBadges.badges;
  return view;
};

function defineDashboardStrategy(name, { domain, title, icon, build, strings, description }) {
  /* Shared by both strategy flavours: everything up to the finished view list. */
  const buildViews = async (config, hass) => {
    const t = translator(strings || {}, hass);
    let registry;
    try {
      registry = await loadRegistry(hass);
    } catch (err) {
      // Registry unreachable: render a readable message rather than
      // letting the dashboard fail with a blank screen.
      return [{ title: title, cards: [emptyNotice(`\u26a0\ufe0f ${err}`)] }];
    }
    const domainEntries = entriesOfDomain(registry.entities, domain);
    if (!domainEntries.length) {
      return [{ title: title, icon, cards: [emptyNotice(t("not_configured"))] }];
    }
    const views = await build({
      hass,
      config,
      t,
      domain,
      entities: domainEntries,
      devices: registry.devices,
      allEntities: registry.entities,
      helpers: { heading, grid, tile, mapCard, emptyNotice, bySuffix, groupByDevice, deviceName },
    });
    return applyViewOptions(views, config);
  };

  class Strategy extends HTMLElement {
    static async generate(config, hass) {
      const views = await buildViews(config, hass);
      return { title: (config && config.title) || title, views };
    }
  }

  /* The view flavour: fills a single view of a dashboard the user built
   * themselves, so adjusting the layout no longer requires "take control". */
  class ViewStrategy extends HTMLElement {
    static async generate(config, hass) {
      const views = await buildViews(config, hass);
      return flattenToView(views, (config && config.title) || title, icon, config);
    }
  }

  // getCreateSuggestions lets Home Assistant offer sensible defaults when the
  // strategy is picked from the "new dashboard" dialog.
  Strategy.getCreateSuggestions = () => ({ title, icon });

  customElements.define(`ll-strategy-dashboard-${name}`, Strategy);
  customElements.define(`ll-strategy-view-${name}`, ViewStrategy);

  // Announce the strategy to the frontend so it appears in the dashboard
  // creation dialog instead of having to be typed into the raw editor.
  window.customStrategies = window.customStrategies || [];
  if (!window.customStrategies.some((s) => s.type === name)) {
    window.customStrategies.push({
      type: name,
      strategyType: "dashboard",
      name: title,
      description: description || "",
    });
  }
  return Strategy;
}

/* =====================================================================
 * Dashboard strategy: Swiss Avalanche Bulletin
 * =====================================================================
 * Reproduces the dashboard that earlier versions created in the user's
 * Lovelace storage — but generated in the browser at render time, so
 * nothing is written to .storage and the user stays in control. It also
 * follows the config entries: a new location or station favourite shows
 * up on the next page load, a removed one disappears with no leftovers.
 *
 * Usage — create an empty dashboard, open the raw configuration editor
 * and replace its content with:
 *
 *     strategy:
 *       type: custom:swiss-avalanche-bulletin
 *     views: []
 *
 * Optional: `title:` overrides the dashboard title, `max_columns:` the
 * column count of the generated view. There is no map view, so the
 * core's `map: false` option has nothing to remove here.
 * ===================================================================== */

const SAB_STRINGS = {
  en: {
    view: "Avalanches",
    imis_stations: "IMIS measuring stations",
    nothing_to_show:
      "### Nothing to show\n\nEvery entity of this integration is hidden. Unhide at least one under **Settings → Devices & services → Entities**.",
    not_configured:
      "### Swiss Avalanche Bulletin is not set up yet\n\nAdd the integration under **Settings → Devices & services** first. This dashboard then fills itself — there is nothing to configure here.",
  },
  de: {
    view: "Lawinen",
    imis_stations: "IMIS-Messstationen",
    nothing_to_show:
      "### Nichts anzuzeigen\n\nAlle Entitäten dieser Integration sind ausgeblendet. Blende unter **Einstellungen → Geräte & Dienste → Entitäten** mindestens eine wieder ein.",
    not_configured:
      "### Swiss Avalanche Bulletin ist noch nicht eingerichtet\n\nFüge die Integration zuerst unter **Einstellungen → Geräte & Dienste** hinzu. Dieses Dashboard füllt sich danach von selbst — hier ist nichts einzustellen.",
  },
  fr: {
    view: "Avalanches",
    imis_stations: "Stations de mesure IMIS",
    nothing_to_show:
      "### Rien à afficher\n\nToutes les entités de cette intégration sont masquées. Réaffichez-en au moins une sous **Paramètres → Appareils et services → Entités**.",
    not_configured:
      "### Swiss Avalanche Bulletin n'est pas encore configuré\n\nAjoutez d'abord l'intégration sous **Paramètres → Appareils et services**. Ce tableau de bord se remplit ensuite tout seul.",
  },
  it: {
    view: "Valanghe",
    imis_stations: "Stazioni di misura IMIS",
    nothing_to_show:
      "### Niente da mostrare\n\nTutte le entità di questa integrazione sono nascoste. Rendine visibile almeno una in **Impostazioni → Dispositivi e servizi → Entità**.",
    not_configured:
      "### Swiss Avalanche Bulletin non è ancora configurato\n\nAggiungi prima l'integrazione in **Impostazioni → Dispositivi e servizi**. Questa dashboard si riempie poi da sola.",
  },
};

/* The bundled station card is configured with a station slug, not with an
 * entity: it reads sensor.slf_imis_<slug>_<key> straight from the state
 * machine. Its picker derives the slugs with this very pattern, so the
 * strategy applies the same one to the station device's registry entries
 * — whatever the card will look up is what the strategy hands it. */
const SAB_STATION_ID =
  /^sensor\.slf_imis_(.+)_(snow_height|air_temperature|wind_speed|wind_direction|humidity)$/;

const SAB_stationSlug = (registryEntries) => {
  for (const e of registryEntries) {
    const m = SAB_STATION_ID.exec(e.entity_id);
    if (m) return m[1];
  }
  return null;
};

defineDashboardStrategy("swiss-avalanche-bulletin", {
  domain: "slf_avalanche",
  title: "Swiss Avalanche Bulletin",
  icon: "mdi:snowflake-alert",
  description:
    "Danger level, warning region and avalanche problems per location, plus a card per IMIS station favourite — generated live from the integration.",
  strings: SAB_STRINGS,

  async build({ config, t, entities, devices, helpers }) {
    const { heading, grid, tile, emptyNotice, bySuffix, groupByDevice, deviceName } = helpers;

    // Every section spans the whole view, so its column span has to
    // follow the user's `max_columns` (the core applies the same value
    // to the view itself); the default is two columns.
    const cols = Number((config || {}).max_columns);
    const columns = Number.isFinite(cols) && cols > 0 ? cols : 2;

    // Two kinds of device, told apart by the unique_id scheme of the sensor
    // platform: a bulletin entry owns one device whose entities are
    // `<entry>_danger_level`, `<entry>_region` and `<entry>_problem_N`; an
    // IMIS entry owns one device per station, `<entry>_imis_<code>_<key>`.
    // groupByDevice already sorts by device name, which keeps the layout
    // stable between reloads.
    const bulletinSections = [];
    const stationsByEntry = new Map();

    for (const group of groupByDevice(entities, devices)) {
      const entryId = group.entities.find((e) => e.config_entry_id)?.config_entry_id;
      if (!entryId) continue;

      const isStation = group.entities.some(
        (e) => typeof e.unique_id === "string" && e.unique_id.startsWith(`${entryId}_imis_`)
      );
      if (isStation) {
        if (!stationsByEntry.has(entryId)) stationsByEntry.set(entryId, []);
        stationsByEntry.get(entryId).push(group);
        continue;
      }

      // --- Bulletin location ---------------------------------------------
      // Suffix lookup instead of entity_id patterns, so a renamed entity
      // keeps its place. Hidden entities are the user's choice — left out.
      const ids = bySuffix(
        group.entities.filter((e) => !e.hidden_by),
        entryId
      );
      const badges = ids.danger_level
        ? [{ type: "entity", entity: ids.danger_level, show_state: true }]
        : undefined;
      const cards = [
        heading(deviceName(group.device), "mdi:snowflake-alert", badges),
        ids.danger_level && tile(ids.danger_level, { color: "red", grid_options: { columns: 6 } }),
        ids.region && tile(ids.region, { grid_options: { columns: 6 } }),
        // Up to three problems in the order the bulletin reports them;
        // outside the season they simply read "unknown".
        ...Object.keys(ids)
          .filter((suffix) => /^problem_\d+$/.test(suffix))
          .sort()
          .map((suffix) => tile(ids[suffix], { grid_options: { columns: 12 } })),
      ].filter(Boolean);
      // Full width like the old dashboard's sections: the half-width tiles
      // pair up and a problem tile spans the row instead of a quarter page.
      if (cards.length > 1) bulletinSections.push(grid(cards, columns));
    }

    // --- IMIS stations: one section per entry, one card per station ------
    // Full-width section with half-width cards, so two stations sit side by
    // side — the same layout the earlier auto-created dashboard used.
    const imisSections = [];
    for (const groups of stationsByEntry.values()) {
      const cards = [heading(t("imis_stations"), "mdi:ruler")];
      for (const group of groups) {
        // A station whose sensors the user hid entirely stays off the
        // dashboard, like a hidden bulletin entity does above.
        const visible = group.entities.filter((e) => !e.hidden_by);
        if (!visible.length) continue;
        const slug = SAB_stationSlug(visible);
        if (slug) {
          cards.push({
            type: "custom:slf-imis-station-card",
            station: slug,
            grid_options: { columns: 6 },
          });
          continue;
        }
        // Entity ids renamed by hand no longer match what the card reads,
        // and it would only show "no data" — plain tiles keep the values
        // visible instead.
        cards.push(
          { ...heading(deviceName(group.device), "mdi:snowflake"), heading_style: "subtitle" },
          ...visible
            .map((e) => e.entity_id)
            .sort()
            .map((entityId) => tile(entityId, { grid_options: { columns: 6 } }))
        );
      }
      // Only the heading left: every station of this entry is hidden, so
      // the section is left out like a hidden bulletin entity is.
      if (cards.length > 1) imisSections.push(grid(cards, columns));
    }

    const sections = [...bulletinSections, ...imisSections];
    if (!sections.length) {
      // Entities exist, but every one of them is hidden: say so instead of
      // rendering an empty view that looks broken.
      return [
        { title: t("view"), icon: "mdi:snowflake-alert", cards: [emptyNotice(t("nothing_to_show"))] },
      ];
    }

    return [
      {
        title: t("view"),
        path: "avalanches",
        icon: "mdi:snowflake-alert",
        type: "sections",
        max_columns: columns,
        sections,
      },
    ];
  },
});
})();
