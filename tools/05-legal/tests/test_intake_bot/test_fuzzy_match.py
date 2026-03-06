"""Tests for fuzzy name matching."""

from legal.intake_bot.fuzzy_match import (
    combined_match_score,
    fuzzy_score,
    phonetic_match_score,
    validate_hkid_last4,
)


def test_exact_match_score_1():
    assert fuzzy_score("Chan Tai Man", "Chan Tai Man") == 1.0


def test_similar_names_high_score():
    score = fuzzy_score("Chan Tai Man", "Chan Tai Mun")
    assert score > 0.8


def test_different_names_low_score():
    score = fuzzy_score("Chan", "Wong")
    assert score < 0.5


def test_chinese_phonetic_match():
    score = phonetic_match_score("陳大文", "陈大文")
    assert score > 0.6


def test_combined_best_score():
    score, match_type = combined_match_score("Chan Tai Man", "Chan Tai Mun")
    assert score > 0.8
    assert match_type in ("exact", "fuzzy", "phonetic")


def test_hkid_valid():
    assert validate_hkid_last4("A123") is True


def test_hkid_invalid_format():
    assert validate_hkid_last4("1234") is False


def test_hkid_invalid_length():
    assert validate_hkid_last4("AB12") is False
