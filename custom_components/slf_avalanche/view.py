"""The bulletin for the bundled cards: the danger map of all regions and the
full report of every bulletin location, in one authenticated request.

GET /api/slf_avalanche/bulletin?lang=de

The answer is built from the shared bulletin download (see bulletin.py), so
a card costs no extra request to the SLF while the copy is fresh.
"""
from __future__ import annotations

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .bulletin import async_get_bulletin, find_feature, region_report
from .const import CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE, CONF_NAME, DOMAIN, MODE_BULLETIN
from .coordinator import API_ERRORS
from .localization import DANGER_LEVEL_TEXT, PROBLEM_TYPE_TEXT, SUPPORTED_LANGUAGES, get_language

# Outline precision of the map: 4 decimals are about 10 m, plenty for a card.
DECIMALS = 4


def _ring(ring: list) -> list:
    return [[round(point[0], DECIMALS), round(point[1], DECIMALS)] for point in ring if len(point) >= 2]


def _polygons(geometry: dict | None) -> list:
    """The outer and inner rings of a (Multi)Polygon as a list of polygons."""
    geometry = geometry or {}
    coords = geometry.get("coordinates") or []
    if geometry.get("type") == "Polygon":
        return [[_ring(r) for r in coords]]
    if geometry.get("type") == "MultiPolygon":
        return [[_ring(r) for r in polygon] for polygon in coords]
    return []


def map_regions(bulletin: dict, language: str) -> list[dict]:
    """Every feature of the bulletin as a map region with its level."""
    texts = DANGER_LEVEL_TEXT.get(language, DANGER_LEVEL_TEXT["en"])
    regions = []
    for feature in bulletin.get("features") or []:
        props = feature.get("properties") or {}
        report = region_report(feature)
        regions.append({
            "ids": [r.get("regionID") for r in props.get("regions") or []],
            "name": ", ".join(r.get("name") or "" for r in props.get("regions") or []),
            "level": report.get("danger_level"),
            "detail": report.get("danger_level_detail"),
            "text": texts.get(report.get("danger_main_value") or ""),
            "polygons": _polygons(feature.get("geometry")),
        })
    return regions


def localized_report(report: dict, language: str) -> dict:
    """A region report with the texts the cards show in the given language."""
    levels = DANGER_LEVEL_TEXT.get(language, DANGER_LEVEL_TEXT["en"])
    problems = PROBLEM_TYPE_TEXT.get(language, PROBLEM_TYPE_TEXT["en"])
    out = {k: v for k, v in report.items() if k != "danger_ratings_raw"}
    out["danger_text"] = levels.get(report.get("danger_main_value") or "")
    out["danger_text_tomorrow"] = levels.get(report.get("danger_main_value_tomorrow") or "")
    out["avalanche_problems"] = [
        {
            "type": p.get("problemType"),
            "name": problems.get(p.get("problemType") or "", p.get("problemType")),
            "level": p.get("dangerRatingValue"),
            "aspects": p.get("aspects") or [],
            "elevation": p.get("elevation") or {},
            "core_zone": p.get("core_zone"),
            "comment": p.get("comment"),
        }
        for p in report.get("avalanche_problems") or []
    ]
    return out


class SlfBulletinView(HomeAssistantView):
    """The map regions and the reports of the bulletin locations."""

    url = "/api/slf_avalanche/bulletin"
    name = "api:slf_avalanche:bulletin"
    requires_auth = True

    async def get(self, request):
        hass: HomeAssistant = request.app[KEY_HASS]
        language = request.query.get("lang") or get_language(hass)
        if language not in SUPPORTED_LANGUAGES:
            language = "en"
        try:
            bulletin = await async_get_bulletin(hass, language)
        except API_ERRORS:
            return self.json_message("The SLF bulletin could not be fetched", 503)

        locations = []
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED or entry.data.get(CONF_MODE, MODE_BULLETIN) != MODE_BULLETIN:
                continue
            coordinator = getattr(getattr(entry, "runtime_data", None), "bulletin", None)
            data = (coordinator.data if coordinator else None) or {}
            if not data.get("sector_id"):
                continue
            region_id = f"CH-{data['sector_id']}"
            report = region_report(find_feature(bulletin, region_id))
            locations.append({
                "entry_id": entry.entry_id,
                "name": entry.data.get(CONF_NAME) or entry.title,
                "region_id": region_id,
                "region": data.get("sector_name"),
                "latitude": entry.data.get(CONF_LATITUDE),
                "longitude": entry.data.get(CONF_LONGITUDE),
                **localized_report(report, language),
            })

        return self.json({
            "language": language,
            "season": any("dangerRatings" in (f.get("properties") or {}) for f in bulletin.get("features") or []),
            "regions": map_regions(bulletin, language),
            "locations": locations,
        })


def async_register_view(hass: HomeAssistant) -> None:
    """Register the view once per Home Assistant run."""
    key = f"{DOMAIN}_view_registered"
    if not hass.data.get(key):
        hass.http.register_view(SlfBulletinView())
        hass.data[key] = True
