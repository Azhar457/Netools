"""
Unit tests for the Netools i18n Localization Engine.
Tests dynamic translation, language registry, persistence, formatting, and extensibility.
"""

import unittest
from netools.gui import i18n


class TestI18nEngine(unittest.TestCase):
    def setUp(self):
        self.original_locale = i18n.get_locale()

    def tearDown(self):
        i18n.set_locale(self.original_locale)

    def test_default_locale(self):
        current = i18n.get_locale()
        self.assertIn(current, ["en", "id"])

    def test_english_translation_fallback(self):
        i18n.set_locale("en")
        self.assertEqual(i18n.tr("📊 Dashboard"), "📊 Dashboard")
        self.assertEqual(i18n.tr("🚀 Start Pool"), "🚀 Start Pool")
        self.assertEqual(i18n.tr("NonExistentKey123"), "NonExistentKey123")

    def test_indonesian_translation(self):
        i18n.set_locale("id")
        self.assertEqual(i18n.tr("📊 Dashboard"), "📊 Dasbor")
        self.assertEqual(i18n.tr("🚀 Start Pool"), "🚀 Jalankan Pool")
        self.assertEqual(i18n.tr("🛑 Stop Pool"), "🛑 Hentikan Pool")
        self.assertEqual(i18n.tr("● System Ready"), "● Sistem Siap")

    def test_string_formatting_kwargs(self):
        i18n.set_locale("id")
        res = i18n.tr("✓ Successfully connected {assigned} connections to 9Router!", assigned=5)
        self.assertEqual(res, "✓ Berhasil menghubungkan 5 koneksi ke 9Router!")

        i18n.set_locale("en")
        res = i18n.tr("✓ Successfully connected {assigned} connections to 9Router!", assigned=5)
        self.assertEqual(res, "✓ Successfully connected 5 connections to 9Router!")

    def test_label_mappings(self):
        locales = i18n.get_available_locales()
        self.assertIn("en", locales)
        self.assertIn("id", locales)

        labels = i18n.get_locale_labels()
        self.assertIn("🇬🇧 English", labels)
        self.assertIn("🇮🇩 Bahasa Indonesia", labels)

        self.assertEqual(i18n.locale_from_label("🇬🇧 English"), "en")
        self.assertEqual(i18n.locale_from_label("🇮🇩 Bahasa Indonesia"), "id")
        self.assertEqual(i18n.label_from_locale("en"), "🇬🇧 English")
        self.assertEqual(i18n.label_from_locale("id"), "🇮🇩 Bahasa Indonesia")

    def test_extensibility_register_new_locale(self):
        """Verify that adding a new language (e.g. Japanese) is 100% scalable and modular."""
        ja_strings = {
            "📊 Dashboard": "📊 ダッシュボード",
            "🚀 Start Pool": "🚀 プールを開始",
            "🛑 Stop Pool": "🛑 プールを停止",
            "● System Ready": "● システム準備完了",
            "Hello {name}": "こんにちは、{name}さん！"
        }
        i18n.register_locale("ja", "🇯🇵 日本語", ja_strings)

        self.assertIn("ja", i18n.get_available_locales())
        self.assertIn("🇯🇵 日本語", i18n.get_locale_labels())
        self.assertEqual(i18n.locale_from_label("🇯🇵 日本語"), "ja")

        i18n.set_locale("ja")
        self.assertEqual(i18n.get_locale(), "ja")
        self.assertEqual(i18n.tr("🚀 Start Pool"), "🚀 プールを開始")
        self.assertEqual(i18n.tr("🛑 Stop Pool"), "🛑 プールを停止")
        self.assertEqual(i18n.tr("Hello {name}", name="Azhar"), "こんにちは、Azharさん！")

    def test_canary_info_paragraphs(self):
        paragraphs_id = i18n.canary_info_paragraphs("id")
        self.assertIsInstance(paragraphs_id, list)
        self.assertGreater(len(paragraphs_id), 0)

        paragraphs_en = i18n.canary_info_paragraphs("en")
        self.assertIsInstance(paragraphs_en, list)
        self.assertGreater(len(paragraphs_en), 0)


if __name__ == "__main__":
    unittest.main()
