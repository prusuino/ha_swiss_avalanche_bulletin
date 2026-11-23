"""The structured Swiss part of the bulletin: the level of the next day, the
trend, and the weather (new snow, snowfall limit, wind, temperature)."""
from __future__ import annotations

import pytest

from custom_components.slf_avalanche import bulletin as b

# The structured part of a Swiss bulletin feature (2026-11-23, trimmed).
SWISS = {
    "properties": {
        "regions": [{"regionID": "CH-5123", "name": "Davos"}],
        "validTime": {"startTime": "2026-11-23T16:00:00Z", "endTime": "2026-11-24T16:00:00Z"},
        "dangerRatings": [{"mainValue": "considerable", "customData": {"CH": {"subdivision": "neutral"}}}],
        "avalancheProblems": [],
        "customData": {"CH": {
            "dangerRatingEvolution": [
                {"date": "2026-11-24", "dangerRating": {"mainValue": "considerable", "customData": {"CH": {"subdivision": "neutral"}}}},
                {"date": "2026-11-25", "dangerRating": {"mainValue": "considerable", "customData": {"CH": {"subdivision": "minus"}}}},
                {"date": "2026-11-23", "dangerRating": {"mainValue": "considerable", "customData": {"CH": {"subdivision": "plus"}}}},
            ],
            "weather": [
                {"period": {"start": "2026-11-23T16:00:00.000Z", "end": "2026-11-24T16:00:00.000Z"},
                 "wind": {"speedKmh": 20, "direction": "NW"},
                 "newSnow": [{"snowCm": 4, "elevationM": 1500}, {"snowCm": 6, "elevationM": 2500}],
                 "timeSeries": {
                     "temperatures": [{"valueC": -4.7, "elevationM": 2000}, {"valueC": -0.3, "elevationM": 2000}],
                     "snowfallLimit": [{"elevationM": None, "reasonForNull": "BELOW_REGION"}],
                 }},
                {"period": {"start": "2026-11-21T16:00:00.000Z", "end": "2026-11-22T16:00:00.000Z"},
                 "newSnow": [{"snowCm": 1, "elevationM": 1500}, {"snowCm": 3, "elevationM": 2500}]},
                {"period": {"start": "2026-11-22T16:00:00.000Z", "end": "2026-11-23T16:00:00.000Z"},
                 "newSnow": [{"snowCm": 12, "elevationM": 1500}, {"snowCm": 16, "elevationM": 2500}],
                 "timeSeries": {"snowfallLimit": [{"elevationM": 1070}, {"elevationM": 1430}]}},
            ],
        }},
    }
}


def test_next_day_and_trend():
    report = b.region_report(SWISS)
    assert report["danger_level_tomorrow"] == 3
    assert report["danger_level_tomorrow_detail"] == "3-"
    assert report["tomorrow_date"] == "2026-11-25"
    assert report["trend"] == "decreasing"  # 3= today, 3- tomorrow


@pytest.mark.parametrize(("tomorrow", "trend"), [
    ({"mainValue": "high"}, "increasing"),
    ({"mainValue": "considerable", "customData": {"CH": {"subdivision": "plus"}}}, "increasing"),
    ({"mainValue": "considerable", "customData": {"CH": {"subdivision": "neutral"}}}, "steady"),
    ({"mainValue": "moderate", "customData": {"CH": {"subdivision": "plus"}}}, "decreasing"),
])
def test_trend_compares_level_and_subdivision(tomorrow, trend):
    feature = {"properties": {**SWISS["properties"], "customData": {"CH": {
        "dangerRatingEvolution": [{"date": "2026-11-25", "dangerRating": tomorrow}]}}}}
    assert b.region_report(feature)["trend"] == trend


def test_no_next_day_without_evolution():
    report = b.region_report({"properties": {**SWISS["properties"], "customData": {}}})
    assert "danger_level_tomorrow" not in report
    assert "trend" not in report


def test_weather_of_the_forecast_and_the_day_before():
    report = b.region_report(SWISS)
    assert report["new_snow_forecast"] == {"cm": 6, "elevation_m": 2500, "by_elevation": {1500: 4, 2500: 6}}
    # the period right before the forecast, not the oldest one
    assert report["new_snow_last_24h"] == {"cm": 16, "elevation_m": 2500, "by_elevation": {1500: 12, 2500: 16}}
    assert report["wind_speed_forecast"] == 20
    assert report["wind_direction_forecast"] == "NW"
    assert report["snowfall_limit"] == {"min_m": None, "max_m": None, "below_region": True}
    assert report["temperature_max"] == -0.3
    assert report["temperature_elevation_m"] == 2000


def test_snowfall_limit_range_and_missing_weather():
    props = dict(SWISS["properties"])
    props["validTime"] = {"startTime": "2026-11-22T16:00:00Z", "endTime": "2026-11-23T16:00:00Z"}
    report = b.region_report({"properties": props})
    assert report["snowfall_limit"] == {"min_m": 1070, "max_m": 1430, "below_region": False}
    assert report["new_snow_last_24h"]["cm"] == 3
    bare = b.region_report({"properties": {**SWISS["properties"], "customData": {"CH": {"weather": []}}}})
    assert "new_snow_forecast" not in bare
