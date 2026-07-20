"""Unit tests for modules.location (shared location service)."""

from __future__ import annotations

import configparser
from unittest.mock import MagicMock, Mock, patch

import pytest

from modules.location import (
    INTERNATIONAL_CITIES,
    OPTIONS_AQI,
    OPTIONS_PREFIX,
    OPTIONS_RAIN,
    ResolveOptions,
    classify_location,
    get_neighborhood_queries,
    parse_coordinates,
    resolve_location,
    titlecase_location,
    join_location,
)


@pytest.fixture
def bot():
    b = MagicMock()
    cfg = configparser.ConfigParser()
    cfg.add_section("Weather")
    cfg.set("Weather", "default_state", "WA")
    cfg.set("Weather", "default_country", "US")
    cfg.add_section("Bot")
    b.config = cfg
    b.db_manager = Mock()
    b.db_manager.get_cached_geocoding = Mock(return_value=(None, None))
    b.db_manager.cache_geocoding = Mock()
    b.db_manager.get_cached_json = Mock(return_value=None)
    b.db_manager.cache_json = Mock()
    b.db_manager.execute_query = Mock(return_value=[])
    b.logger = Mock()
    rl = Mock()
    rl.wait_for_request_sync = Mock()
    rl.record_request = Mock()
    b.nominatim_rate_limiter = rl
    return b


def _loc(lat=47.6, lon=-122.3, address="Seattle, WA, USA", info=None):
    loc = Mock()
    loc.latitude = lat
    loc.longitude = lon
    loc.address = address
    loc.raw = {"address": info or {"city": "Seattle", "state": "Washington", "country": "United States", "country_code": "us"}}
    return loc


@pytest.mark.unit
class TestClassifyLocation:
    def test_coordinates(self):
        q, t = classify_location("47.6,-122.3")
        assert t == "coordinates"

    def test_zip_with_whitespace(self):
        q, t = classify_location(" 98101 ")
        assert t == "zipcode"
        assert q == "98101"

    def test_intl_single(self):
        q, t = classify_location("london")
        assert t == "city"
        assert q == "london, uk"

    def test_intl_multiword(self):
        q, t = classify_location("mexico city")
        assert t == "city"
        assert q == "mexico city, mexico"

    def test_space_country(self):
        q, t = classify_location("vancouver canada")
        assert t == "city"
        assert q == "vancouver, canada"

    def test_intl_disabled(self):
        q, t = classify_location("london", use_international_cities=False)
        assert q == "london"


@pytest.mark.unit
class TestParseCoordinates:
    def test_valid(self):
        assert parse_coordinates("47.6, -122.3") == pytest.approx((47.6, -122.3))

    def test_invalid_range(self):
        assert parse_coordinates("200,0") is None

    def test_invalid_format(self):
        assert parse_coordinates("seattle") is None


@pytest.mark.unit
class TestNeighborhoods:
    def test_greenwood(self):
        qs = get_neighborhood_queries("greenwood")
        assert qs[0] == "greenwood, Seattle, WA, USA"

    def test_unknown(self):
        assert get_neighborhood_queries("nowhere") == []


@pytest.mark.unit
class TestKazakhstanDedup:
    def test_single_canonical(self):
        assert INTERNATIONAL_CITIES["kazakhstan"] == "nur-sultan, kazakhstan"


@pytest.mark.unit
class TestResolveLocation:
    def test_coords(self, bot):
        r = resolve_location(bot, "47.6,-122.3", options=OPTIONS_AQI)
        assert r.location_type == "coordinates"
        assert r.lat == pytest.approx(47.6)
        assert r.error is None

    def test_empty_no_fallback(self, bot):
        r = resolve_location(bot, None, options=OPTIONS_AQI)
        assert r.error == "no_location"

    def test_empty_with_fallback(self, bot):
        opts = ResolveOptions(fallback_coords=(48.0, -122.0), label_style="numeric")
        r = resolve_location(bot, "", options=opts)
        assert r.lat == pytest.approx(48.0)
        assert r.location_type == "fallback"

    def test_city_via_geocode(self, bot):
        with patch(
            "modules.location.geocode_city_sync",
            return_value=(47.6, -122.3, {"city": "Seattle", "state": "Washington", "country": "United States"}),
        ):
            r = resolve_location(bot, "seattle", options=OPTIONS_AQI)
        assert r.lat == pytest.approx(47.6)
        assert r.location_type == "city"

    def test_region_capitals_flag(self, bot):
        loc = _loc(48.85, 2.35, "Paris, France", {"city": "Paris", "country": "France"})
        with patch(
            "modules.location.rate_limited_nominatim_geocode_sync",
            return_value=loc,
        ), patch(
            "modules.location.rate_limited_nominatim_reverse_sync",
            return_value=loc,
        ):
            r = resolve_location(bot, "france", options=OPTIONS_RAIN)
        assert r.region_note is not None
        assert r.lat == pytest.approx(48.85)
        assert "Paris" in r.query or "paris" in r.query.lower()

    def test_repeater_lookup(self, bot):
        bot.db_manager.execute_query.return_value = [
            {"latitude": 47.1, "longitude": -122.1, "name": "KR7ABC"}
        ]
        r = resolve_location(bot, "KR7ABC", options=OPTIONS_PREFIX)
        assert r.location_type == "repeater"
        assert r.lat == pytest.approx(47.1)

    def test_zip_override(self, bot):
        loc = _loc(47.45, -122.46, "Vashon, WA, USA")
        with patch("modules.location.rate_limited_nominatim_geocode_sync", return_value=loc), patch(
            "modules.location.rate_limited_nominatim_reverse_sync", return_value=loc
        ):
            r = resolve_location(bot, "98013", options=OPTIONS_AQI)
        assert r.lat == pytest.approx(47.45)
        assert r.location_type == "zipcode"


@pytest.mark.unit
class TestRainReexports:
    def test_helpers_importable_from_rain(self):
        from modules.commands.rain_command import (
            city_display_name,
            join_location,
            reverse_geocode_region,
            titlecase_location,
        )
        assert titlecase_location("memphis") == "Memphis"
        assert join_location("Paris", "France") == "Paris, France"
        assert city_display_name("london ky") == "London"
        assert callable(reverse_geocode_region)
