/* SLF IMIS station card — shipped and auto-registered by the Swiss
 * Avalanche Bulletin integration.
 *
 *   slf-imis-station-card   snow, temperature and wind of one IMIS station
 *
 * The card provides a visual editor (getConfigElement) and follows the
 * Home Assistant frontend language (de/en/fr/it).
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

/* Station slugs present in the state machine: sensor.slf_imis_<slug>_<key> */
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
