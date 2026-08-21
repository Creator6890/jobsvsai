from collections import Counter
from decimal import Decimal

import pytest

from ingestion.onet_import import (
    RawRecord, _canonical_hash, _dedupe, _natural_key, _public_slug,
    _title_review_reasons, normalize_scale, succession_mapping_type,
)


def test_scale_normalization_preserves_boundaries() -> None:
    assert normalize_scale(Decimal("1"), Decimal("1"), Decimal("5")) == Decimal("0.0000")
    assert normalize_scale(Decimal("3"), Decimal("1"), Decimal("5")) == Decimal("50.0000")
    assert normalize_scale(Decimal("5"), Decimal("1"), Decimal("5")) == Decimal("100.0000")


def test_row_hash_is_key_order_independent() -> None:
    assert _canonical_hash({"b": "2", "a": "1"}) == _canonical_hash({"a": "1", "b": "2"})


def test_task_rating_natural_key_preserves_category() -> None:
    row = {"O*NET-SOC Code": "15-1252.00", "Task ID": "123", "Scale ID": "FT", "Category": "4"}
    assert _natural_key("task_ratings", row) == "15-1252.00|123|FT|4"


def test_conflicting_natural_key_fails_closed() -> None:
    first = RawRecord("occupation_data", "15-1252.00", "source", "a" * 64, {"Title": "One"})
    second = RawRecord("occupation_data", "15-1252.00", "source", "b" * 64, {"Title": "Two"})
    with pytest.raises(ValueError, match="Conflicting rows"):
        _dedupe([first, second])


@pytest.mark.parametrize(("predecessors", "successors", "expected"), [
    (Counter({"10": 1}), Counter({"20": 1}), "recoded"),
    (Counter({"10": 2}), Counter({"20": 1}), "split"),
    (Counter({"10": 1}), Counter({"20": 2}), "merge"),
    (Counter({"10": 2}), Counter({"20": 2}), "complex"),
])
def test_succession_cardinality_is_explicit(predecessors, successors, expected) -> None:
    row = {
        "O*NET-SOC 2010 Code": "10", "O*NET-SOC 2010 Title": "Old",
        "O*NET-SOC 2019 Code": "20", "O*NET-SOC 2019 Title": "New",
    }
    assert succession_mapping_type(row, predecessors, successors) == expected


def test_succession_does_not_invent_change_when_source_is_unchanged() -> None:
    row = {
        "O*NET-SOC 2010 Code": "10", "O*NET-SOC 2010 Title": "Same",
        "O*NET-SOC 2019 Code": "10", "O*NET-SOC 2019 Title": "Same",
    }
    assert succession_mapping_type(row, Counter({"10": 1}), Counter({"10": 1})) == "unchanged"


def test_public_title_policy_flags_taxonomic_and_us_specific_titles() -> None:
    reasons = _title_review_reasons("Federal Legislators, All Other")
    assert "source_title_is_taxonomic_or_exclusionary" in reasons
    assert "source_title_is_us_specific" in reasons
    assert _title_review_reasons("Nurse Practitioners") == []


def test_private_publication_slug_is_stable_and_source_scoped() -> None:
    assert _public_slug("Nurse Practitioners", "29-1171.00") == "nurse-practitioners-29-1171-00"
