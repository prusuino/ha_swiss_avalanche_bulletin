"""The bulletin: plain text out of its HTML, one region's report, the
language of the download and one shared download for several entries."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.slf_avalanche import bulletin as b
from custom_components.slf_avalanche.localization import get_language

# Shaped like the features of the winter bulletin of 2026-11-23 (trimmed).
RATED = {
    "properties": {
        "regions": [{"regionID": "CH-5123", "name": "Davos"}],
        "validTime": {"startTime": "2026-11-23T16:00:00Z", "endTime": "2026-11-24T16:00:00Z"},
        "nextUpdate": "2026-11-24T16:00:00Z",
        "publicationTime": "2026-11-23T16:00:00Z",
        "unscheduled": False,
        "dangerRatings": [
            {"mainValue": "moderate", "elevation": {"upperBound": "2200"}, "customData": {"CH": {"subdivision": "plus"}}},
            {"mainValue": "considerable", "elevation": {"lowerBound": "2200"}, "customData": {"CH": {"subdivision": "minus"}}},
        ],
        "avalancheProblems": [
            {
                "problemType": "persistent_weak_layers",
                "dangerRatingValue": "moderate",
                "comment": "Old snow.",
                "customData": {"CH": {"coreZoneText": "Danger level \"moderate\" (2+) on north slopes."}},
            },
            {
                "problemType": "wind_slab",
                "dangerRatingValue": "considerable",
                "comment": "Wind slabs are prone to triggering. <br/> Tours call for experience.",
                "customData": {"CH": {"coreZoneText": "Danger level \"considerable\" (3-) above 2200&nbsp;m."}},
            },
        ],
        "tendency": [{"comment": "<h2>Dry avalanches</h2><p>The danger decreases slowly.</p>"}],
        "snowpackStructure": {"comment": "Snow depths are well above average."},
        "weatherReview": {"comment": "<h2>22.11. 17:00 – 23.11. 17:00</h2><ul><li>Snowfall limit: 1070&nbsp;m</li><li>Wind: W</li></ul>"},
        "weatherForecast": None,
    }
}
# In winter the lowlands are listed without a rating.
UNRATED = {"properties": {"regions": [{"regionID": "CH-8226", "name": "Basel"}], "fill": None}}


def test_plain_text():
    assert b.plain_text(None) is None
    assert b.plain_text("") is None
    assert b.plain_text("One. <br/> Two.") == "One.\nTwo."
    assert b.plain_text("<h2>Title</h2><p>Text&nbsp;here.</p>") == "Title\nText here."
    assert b.plain_text("<ul><li>a</li><li>b &amp; c</li></ul>") == "• a\n• b & c"
    assert b.plain_text("<p> </p>") is None


def test_rated_region():
    report = b.region_report(RATED)
    assert report["active"] is True
    assert report["danger_level"] == 3
    assert report["danger_main_value"] == "considerable"
    assert report["subdivision"] == "minus"
    assert report["danger_level_detail"] == "3-"
    # the core zone of the problem that carries the day's level
    assert report["core_zone"] == 'Danger level "considerable" (3-) above 2200 m.'
    problems = report["avalanche_problems"]
    assert [p["problemType"] for p in problems] == ["persistent_weak_layers", "wind_slab"]
    assert problems[1]["comment"] == "Wind slabs are prone to triggering.\nTours call for experience."
    assert problems[0]["core_zone"] == 'Danger level "moderate" (2+) on north slopes.'
    assert report["tendency"] == "Dry avalanches\nThe danger decreases slowly."
    assert report["snowpack"] == "Snow depths are well above average."
    assert report["weather_review"] == "22.11. 17:00 – 23.11. 17:00\n• Snowfall limit: 1070 m\n• Wind: W"
    assert report["weather_forecast"] is None
    assert report["valid_to"] == "2026-11-24T16:00:00Z"
    assert report["publication_time"] == "2026-11-23T16:00:00Z"


def test_detail_without_subdivision_and_core_zone_fallback():
    feature = {"properties": {
        "dangerRatings": [{"mainValue": "low"}],
        "avalancheProblems": [{"problemType": "gliding_snow", "dangerRatingValue": "moderate",
                               "customData": {"CH": {"coreZoneText": "Gliding snow on grass."}}}],
    }}
    report = b.region_report(feature)
    assert report["danger_level_detail"] == "1"
    assert report["subdivision"] is None
    assert report["core_zone"] == "Gliding snow on grass."  # no problem carries the day's level


def test_unrated_region_and_missing_region_are_not_active():
    assert b.region_report(UNRATED) == {"active": False}
    assert b.region_report(None) == {"active": False}
    assert b.region_report({"properties": {"dangerRatings": []}}) == {"active": False}


@pytest.mark.parametrize(("ha_language", "bulletin_language"), [
    ("de", "de"), ("de-CH", "de"), ("fr", "fr"), ("it", "it"), ("en", "en"), ("en-GB", "en"), ("rm", "en"), ("nl", "en"),
])
def test_bulletin_language_follows_home_assistant(hass, ha_language, bulletin_language):
    hass.config.language = ha_language
    assert get_language(hass) == bulletin_language


class _Response:
    def __init__(self, status, payload=None, etag=None):
        self.status = status
        self._payload = payload
        self.headers = {"ETag": etag} if etag else {}

    def raise_for_status(self):
        if self.status >= 400:
            raise b.asyncio.TimeoutError()

    async def json(self, content_type=None):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None, **kwargs):
        self.calls.append((url, dict(headers or {})))
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_one_download_shared_and_revalidated_with_the_etag(hass):
    data = {"features": [RATED]}
    session = _Session([_Response(200, data, etag='W/"a"'), _Response(304)])
    with patch.object(b, "async_get_clientsession", return_value=session):
        first = await b.async_get_bulletin(hass, "fr")
        second = await b.async_get_bulletin(hass, "fr")  # another entry right after: no request
        assert first is second is data
        assert len(session.calls) == 1
        assert session.calls[0] == ("https://aws.slf.ch/api/bulletin/caaml/fr/geojson", {})

        b._copies(hass)["fr"].fetched -= b.SHARE_SECONDS + 1  # an hour later
        third = await b.async_get_bulletin(hass, "fr")
        assert third is data  # 304: the copy stays
        assert session.calls[1][1] == {"If-None-Match": 'W/"a"'}


@pytest.mark.asyncio
async def test_each_language_has_its_own_copy_and_errors_keep_the_old_one(hass):
    session = _Session([_Response(200, {"features": []}), _Response(200, {"features": [UNRATED]}), _Response(503)])
    with patch.object(b, "async_get_clientsession", return_value=session):
        await b.async_get_bulletin(hass, "de")
        await b.async_get_bulletin(hass, "it")
        assert [call[0].split("/")[-2] for call in session.calls] == ["de", "it"]

        b._copies(hass)["it"].fetched -= b.SHARE_SECONDS + 1
        with pytest.raises(TimeoutError):
            await b.async_get_bulletin(hass, "it")
        assert b._copies(hass)["it"].data == {"features": [UNRATED]}


@pytest.mark.asyncio
async def test_a_reply_that_is_not_an_object_is_an_error(hass):
    session = _Session([_Response(200, ["not", "a", "bulletin"])])
    with patch.object(b, "async_get_clientsession", return_value=session), pytest.raises(ValueError):
        await b.async_get_bulletin(hass, "de")
