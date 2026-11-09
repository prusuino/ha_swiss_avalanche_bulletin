"""Pure helpers: bulletin feature lookup, worst danger rating, station
distances and the merge of IMIS measurement records."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.slf_avalanche.coordinator import _find_feature_for_region, _worst_danger_rating
from custom_components.slf_avalanche.imis import (
    async_fetch_station_measurements,
    haversine_km,
    stations_by_distance,
)

BULLETIN = {"features": [
    {"properties": {"regions": [{"regionID": "CH-1111"}, {"regionID": "CH-1112"}], "bulletinID": "a"}},
    {"properties": {"regions": [{"regionID": "CH-2222"}], "bulletinID": "b"}},
]}


def test_feature_lookup_by_region():
    assert _find_feature_for_region(BULLETIN, "CH-1112")["properties"]["bulletinID"] == "a"
    assert _find_feature_for_region(BULLETIN, "CH-2222")["properties"]["bulletinID"] == "b"
    assert _find_feature_for_region(BULLETIN, "CH-9999") is None
    assert _find_feature_for_region({}, "CH-1111") is None


def test_worst_danger_rating_wins():
    ratings = [
        {"mainValue": "moderate", "elevation": {"upperBound": "2200"}},
        {"mainValue": "considerable", "elevation": {"lowerBound": "2200"}},
    ]
    assert _worst_danger_rating(ratings)["mainValue"] == "considerable"
    assert _worst_danger_rating([{"mainValue": "no_rating"}])["mainValue"] == "no_rating"
    assert _worst_danger_rating([]) is None


def test_stations_by_distance():
    stations = [
        {"code": "WFJ2", "label": "Weissfluhjoch", "lat": 46.83, "lon": 9.81},
        {"code": "BER2", "label": "Bern", "lat": 46.95, "lon": 7.45},
        {"code": "BAD", "label": "broken", "lat": None, "lon": 7.0},
    ]
    ordered = stations_by_distance(stations, 46.95, 7.45)
    assert [s["code"] for s in ordered] == ["BER2", "WFJ2"]  # the broken one is skipped
    assert ordered[0]["distance_km"] == 0.0
    assert 175 < ordered[1]["distance_km"] < 185
    assert round(haversine_km(46.948, 7.447, 47.377, 8.540)) == 95


class _Response:
    def __init__(self, payload):
        self._payload = payload
        self.status = 200

    def raise_for_status(self):
        pass

    async def json(self, content_type=None):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Session:
    def __init__(self, payload):
        self._payload = payload

    def get(self, url, **kwargs):
        return _Response(self._payload)


@pytest.mark.asyncio
async def test_measurements_take_the_newest_non_null_value_per_field():
    now = dt_util.utcnow().replace(microsecond=0)
    old = (now - timedelta(hours=20)).isoformat()
    recent = (now - timedelta(minutes=60)).isoformat()
    newest = (now - timedelta(minutes=30)).isoformat()
    records = [
        {"measure_date": old, "HS": 80, "TA_30MIN_MEAN": -3.0, "VW_30MIN_MEAN": 2.0},
        {"measure_date": recent, "HS": 82, "TA_30MIN_MEAN": -2.5, "VW_30MIN_MEAN": None},
        {"measure_date": newest, "HS": None, "TA_30MIN_MEAN": -2.0, "VW_30MIN_MEAN": None},
    ]
    with patch("custom_components.slf_avalanche.imis.async_get_clientsession", return_value=_Session(records)):
        result = await async_fetch_station_measurements(None, "WFJ2")
    assert result["measure_date"] == newest
    assert result["values"]["snow_height"] == 82  # the newest record's null does not wipe the value
    assert result["dates"]["snow_height"] == recent
    assert result["values"]["air_temperature"] == -2.0
    assert "wind_speed" not in result["values"]  # only measured 20 h ago: too old to be current
    assert "wind_speed" in result["fields"]  # but the station measures it, so it keeps its sensor


@pytest.mark.asyncio
async def test_measurements_without_records():
    with patch("custom_components.slf_avalanche.imis.async_get_clientsession", return_value=_Session([])):
        result = await async_fetch_station_measurements(None, "WFJ2")
    assert result == {"values": {}, "dates": {}, "fields": set(), "measure_date": None}
