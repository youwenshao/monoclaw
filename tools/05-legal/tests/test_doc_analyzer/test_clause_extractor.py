"""Tests for clause extraction logic."""

import asyncio

from legal.doc_analyzer.clause_extractor import (
    _classify_clause_by_keywords,
    _split_into_raw_clauses,
    extract_clauses,
)

SAMPLE_CONTRACT = """\
1. TERM
This agreement shall commence on 1 January 2026.

2. RENT
The monthly rent shall be HK$30,000.

3. TERMINATION
Either party may terminate this agreement by giving two months' notice.

4. INDEMNITY
The Tenant shall indemnify the Landlord against all losses."""


def test_extract_numbered_clauses():
    clauses = _split_into_raw_clauses(SAMPLE_CONTRACT)
    numbers = [c["clause_number"] for c in clauses]

    assert numbers == ["1", "2", "3", "4"]
    assert "TERM" in clauses[0]["text"]
    assert "RENT" in clauses[1]["text"]
    assert "TERMINATION" in clauses[2]["text"]
    assert "INDEMNITY" in clauses[3]["text"]

    for i in range(len(clauses) - 1):
        assert clauses[i]["end_offset"] == clauses[i + 1]["start_offset"]


def test_extract_schedule_clauses():
    text = """\
SCHEDULE A
The property located at 123 Des Voeux Road Central.

SCHEDULE B
List of fixtures and fittings included in the tenancy."""

    clauses = _split_into_raw_clauses(text)
    numbers = [c["clause_number"] for c in clauses]

    assert "SCHEDULE A" in numbers
    assert "SCHEDULE B" in numbers
    assert len(clauses) == 2


def test_clause_type_classification():
    results = asyncio.run(extract_clauses(SAMPLE_CONTRACT, "tenancy"))
    type_map = {c["clause_number"]: c["clause_type"] for c in results}

    assert type_map["3"] == "termination"
    assert type_map["4"] == "indemnity"


def test_empty_text():
    results = asyncio.run(extract_clauses("", "tenancy"))
    assert len(results) == 1
    assert results[0]["text_content"] == ""
    assert results[0]["clause_type"] == "general"


def test_chinese_text():
    text = """\
1. 租約期限
本租約由二零二六年一月一日起生效。

2. 租金
每月租金為港幣三萬元。

3. 終止條款
任何一方可提前兩個月書面通知終止本協議。"""

    results = asyncio.run(extract_clauses(text, "tenancy"))
    assert len(results) == 3
    assert results[0]["clause_number"] == "1"
    assert "租約期限" in results[0]["text_content"]
    assert results[2]["clause_number"] == "3"
    assert "終止" in results[2]["text_content"]
