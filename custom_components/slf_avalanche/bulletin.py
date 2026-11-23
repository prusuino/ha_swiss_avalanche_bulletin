"""The SLF avalanche bulletin: one shared download per language, and the
reading of one warning region out of it.

The bulletin covers all of Switzerland in one GeoJSON document. Every
bulletin entry needs the same document, so it is fetched once per language
and shared: entries that refresh at about the same time use the copy that is
already there, and a later refresh asks the server with the copy's ETag
whether anything changed (an unchanged bulletin then costs no download).
"""
from __future__ import annotations

import asyncio
import html
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import BULLETIN_URL, DANGER_LEVEL_NUMBERS, DOMAIN

# Several entries refreshing within this many seconds share one request.
SHARE_SECONDS = 300

# The Swiss bulletin refines the level by a subdivision of the level itself.
SUBDIVISION_SIGN = {"minus": "-", "neutral": "=", "plus": "+"}
SUBDIVISION_RANK = {"minus": -1, "neutral": 0, "plus": 1}


@dataclass
class _Copy:
    """The last bulletin fetched in one language."""

    data: dict | None = None
    etag: str | None = None
    fetched: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def _copies(hass: HomeAssistant) -> dict[str, _Copy]:
    return hass.data.setdefault(f"{DOMAIN}_bulletin", {})


async def async_get_bulletin(hass: HomeAssistant, language: str) -> dict:
    """The current bulletin in a language, shared between the entries.

    Raises aiohttp.ClientError, TimeoutError or ValueError when the service
    does not answer usefully; the coordinator turns that into UpdateFailed.
    """
    copy = _copies(hass).setdefault(language, _Copy())
    async with copy.lock:
        if copy.data is not None and time.monotonic() - copy.fetched < SHARE_SECONDS:
            return copy.data
        headers = {"If-None-Match": copy.etag} if copy.etag and copy.data is not None else {}
        session = async_get_clientsession(hass)
        async with session.get(BULLETIN_URL.format(lang=language), headers=headers, timeout=25) as resp:
            if resp.status == 304 and copy.data is not None:
                copy.fetched = time.monotonic()
                return copy.data
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            if not isinstance(data, dict):
                raise ValueError("The SLF bulletin is not a JSON object")
            copy.data = data
            copy.etag = resp.headers.get("ETag")
            copy.fetched = time.monotonic()
            return data


def plain_text(value: str | None) -> str | None:
    """The bulletin's small HTML fragments as plain text with line breaks.

    Headings and paragraphs become lines of their own, list items get a
    bullet, entities such as &nbsp; are resolved and other tags dropped.
    """
    if not value:
        return None
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    text = re.sub(r"<li[^>]*>", "\n• ", text, flags=re.I)
    text = re.sub(r"</(h\d|p|ul|ol|li|div)>|<(h\d|p|ul|ol|div)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line) or None


def find_feature(bulletin: dict, region_id: str) -> dict | None:
    """The bulletin feature that lists a warning region."""
    for feature in bulletin.get("features") or []:
        regions = (feature.get("properties") or {}).get("regions") or []
        if any(r.get("regionID") == region_id for r in regions):
            return feature
    return None


def worst_danger_rating(danger_ratings: list[dict]) -> dict | None:
    """The highest reported danger level (when split by elevation or time)."""
    best = None
    best_level = -1
    for rating in danger_ratings:
        level = DANGER_LEVEL_NUMBERS.get(rating.get("mainValue", ""), 0)
        if level > best_level:
            best_level = level
            best = rating
    return best


def _subdivision(rating: dict | None) -> str | None:
    return (((rating or {}).get("customData") or {}).get("CH") or {}).get("subdivision")


def _core_zone(problem: dict) -> str | None:
    return plain_text((((problem.get("customData") or {}).get("CH")) or {}).get("coreZoneText"))


def _comments(value) -> str | None:
    """The comment text of a bulletin section (an object or a list of them)."""
    items = value if isinstance(value, list) else [value]
    texts = [plain_text((item or {}).get("comment")) for item in items if isinstance(item, dict)]
    return "\n".join(t for t in texts if t) or None


def _level_detail(rating: dict | None) -> tuple[int | None, str | None]:
    """The level 1-5 of a rating and its Swiss form with subdivision (3+)."""
    level = DANGER_LEVEL_NUMBERS.get((rating or {}).get("mainValue") or "")
    if level is None:
        return None, None
    return level, f"{level}{SUBDIVISION_SIGN.get(_subdivision(rating) or '', '')}"


def _rank(rating: dict | None) -> tuple[int, int] | None:
    level = DANGER_LEVEL_NUMBERS.get((rating or {}).get("mainValue") or "")
    if level is None:
        return None
    return level, SUBDIVISION_RANK.get(_subdivision(rating) or "", 0)


def _parse_time(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def _next_day(props: dict, today_rating: dict | None) -> dict:
    """The level the SLF expects for the day after the bulletin's day.

    The Swiss bulletin lists the danger level per day under
    customData.CH.dangerRatingEvolution: past days, the bulletin's own day
    (the date its validity ends) and the next one. The trend compares the
    next day with today, subdivision included (3- < 3= < 3+).
    """
    end = _parse_time((props.get("validTime") or {}).get("endTime"))
    evolution = (((props.get("customData") or {}).get("CH")) or {}).get("dangerRatingEvolution") or []
    if end is None or not evolution:
        return {}
    tomorrow = (end.date() + timedelta(days=1)).isoformat()
    rating = next((e.get("dangerRating") for e in evolution if e.get("date") == tomorrow), None)
    level, detail = _level_detail(rating)
    if level is None:
        return {}
    trend = None
    now_rank, next_rank = _rank(today_rating), _rank(rating)
    if now_rank is not None:
        trend = "increasing" if next_rank > now_rank else "decreasing" if next_rank < now_rank else "steady"
    return {
        "danger_level_tomorrow": level,
        "danger_main_value_tomorrow": rating.get("mainValue"),
        "danger_level_tomorrow_detail": detail,
        "tomorrow_date": tomorrow,
        "trend": trend,
    }


def _new_snow(period: dict | None) -> dict | None:
    """New snow of a weather period: the value at the highest elevation the
    SLF gives, and all elevations as {elevation_m: cm}."""
    values = {}
    for item in (period or {}).get("newSnow") or []:
        if item.get("elevationM") is not None and item.get("snowCm") is not None:
            values[int(item["elevationM"])] = item["snowCm"]
    if not values:
        return None
    top = max(values)
    # string keys: the mapping also goes out as JSON (attributes, card API)
    return {"cm": values[top], "elevation_m": top, "by_elevation": {str(k): v for k, v in sorted(values.items())}}


def _weather(props: dict) -> dict:
    """The structured weather of the region: the forecast period (the one
    that starts with the bulletin's validity) and the last 24 h before it."""
    periods = (((props.get("customData") or {}).get("CH")) or {}).get("weather") or []
    periods = [p for p in periods if isinstance(p, dict) and _parse_time((p.get("period") or {}).get("start"))]
    if not periods:
        return {}
    periods.sort(key=lambda p: _parse_time(p["period"]["start"]))
    start = _parse_time((props.get("validTime") or {}).get("startTime"))
    forecast = next((p for p in periods if start and _parse_time(p["period"]["start"]) >= start), None)
    past = [p for p in periods if p is not forecast and (forecast is None or _parse_time(p["period"]["start"]) < _parse_time(forecast["period"]["start"]))]
    review = past[-1] if past else None

    out: dict = {"new_snow_forecast": _new_snow(forecast), "new_snow_last_24h": _new_snow(review)}
    if forecast:
        wind = forecast.get("wind") or {}
        out["wind_speed_forecast"] = wind.get("speedKmh")
        out["wind_direction_forecast"] = wind.get("direction")
        series = forecast.get("timeSeries") or {}
        limits = [x.get("elevationM") for x in series.get("snowfallLimit") or [] if x.get("elevationM") is not None]
        reasons = {x.get("reasonForNull") for x in series.get("snowfallLimit") or [] if x.get("elevationM") is None}
        out["snowfall_limit"] = {
            "min_m": min(limits) if limits else None,
            "max_m": max(limits) if limits else None,
            # BELOW_REGION: the snow line stays below the region all day
            "below_region": not limits and "BELOW_REGION" in reasons,
        }
        temps = [x for x in series.get("temperatures") or [] if x.get("valueC") is not None]
        if temps:
            out["temperature_max"] = max(x["valueC"] for x in temps)
            out["temperature_elevation_m"] = temps[0].get("elevationM")
    return out


def region_report(feature: dict | None) -> dict:
    """What the bulletin says about one warning region.

    `active` is true only when the region carries a danger rating: in winter
    the lowlands (Mittelland, Jura, southern Ticino) are listed without one.
    """
    props = (feature or {}).get("properties") or {}
    ratings = props.get("dangerRatings") or []
    if not ratings:
        return {"active": False}

    worst = worst_danger_rating(ratings)
    main_value = (worst or {}).get("mainValue")
    level = DANGER_LEVEL_NUMBERS.get(main_value or "")
    subdivision = _subdivision(worst)
    detail = None
    if level is not None:
        detail = f"{level}{SUBDIVISION_SIGN.get(subdivision or '', '')}"

    problems = []
    for problem in props.get("avalancheProblems") or []:
        problems.append({**problem, "comment": plain_text(problem.get("comment")), "core_zone": _core_zone(problem)})

    core_zone = next((p["core_zone"] for p in problems if p["core_zone"] and p.get("dangerRatingValue") == main_value), None)
    core_zone = core_zone or next((p["core_zone"] for p in problems if p["core_zone"]), None)

    valid = props.get("validTime") or {}
    return {
        "active": True,
        "danger_level": level,
        "danger_main_value": main_value,
        "danger_level_detail": detail,
        "subdivision": subdivision,
        "core_zone": core_zone,
        "danger_ratings_raw": ratings,
        "valid_from": valid.get("startTime"),
        "valid_to": valid.get("endTime"),
        "next_update": props.get("nextUpdate"),
        "publication_time": props.get("publicationTime"),
        "unscheduled": props.get("unscheduled"),
        "avalanche_problems": problems,
        "tendency": _comments(props.get("tendency")),
        "snowpack": _comments(props.get("snowpackStructure")),
        "weather_review": _comments(props.get("weatherReview")),
        "weather_forecast": _comments(props.get("weatherForecast")),
        **_next_day(props, worst),
        **_weather(props),
    }
