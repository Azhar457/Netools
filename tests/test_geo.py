"""Tests for country auto-detection and country->TLD-preset mapping."""

from unittest import mock

from netools.libs import dns_db, geo


def test_preset_key_for_country():
    presets = dns_db.load_tld_presets()
    assert dns_db.preset_key_for_country("ID", presets) == "indonesia"
    assert dns_db.preset_key_for_country("jp", presets) == "japan"
    assert dns_db.preset_key_for_country("ZZ", presets) == ""
    assert dns_db.preset_key_for_country("", presets) == ""


def test_all_country_presets_have_valid_shape():
    for key, v in dns_db.TLD_PRESETS.items():
        assert v["name"], key
        assert len(v["domains"]) >= 5, key
        cc = v.get("country", "")
        assert cc == "" or (len(cc) == 2 and cc.isupper()), key


def test_detect_country_prefers_manual_override():
    with mock.patch.object(geo, "load_user_config", return_value={"country": "de"}):
        assert geo.detect_country() == "DE"


def test_detect_country_uses_cache_without_network():
    with (
        mock.patch.object(geo, "load_user_config", return_value={"detected_country": "SG"}),
        mock.patch.object(geo, "_via_trace", side_effect=AssertionError("network hit")),
    ):
        assert geo.detect_country() == "SG"


def test_detect_country_falls_back_to_locale(tmp_path):
    cfg_file = tmp_path / "config.json"
    with (
        mock.patch.object(geo, "load_user_config", return_value={}),
        mock.patch.object(geo, "USER_CONFIG_FILE", cfg_file),
        mock.patch.object(geo, "_via_trace", return_value=""),
        mock.patch.object(geo, "_via_locale", return_value="BR"),
    ):
        assert geo.detect_country() == "BR"
    # result cached
    assert "BR" in cfg_file.read_text()
