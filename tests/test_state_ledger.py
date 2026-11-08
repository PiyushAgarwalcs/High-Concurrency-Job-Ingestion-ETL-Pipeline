"""
Unit tests for StateLedger Fingerprinting & Deduplication Ledger.
"""

import os
import tempfile
import pytest
from core.state_ledger import StateLedger


@pytest.fixture
def temp_ledger():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_path = tf.name
    ledger = StateLedger(db_path=temp_path)
    yield ledger
    if os.path.exists(temp_path):
        os.remove(temp_path)


def test_normalize_title():
    t1 = "Software Development Engineer - I"
    t2 = "Software Engineer 1"
    t3 = "SDE - 1"
    # All variants canonicalize to 'sde 1'
    assert StateLedger.normalize_title(t1) == "sde 1"
    assert StateLedger.normalize_title(t2) == "sde 1"
    assert StateLedger.normalize_title(t3) == "sde 1"


def test_normalize_location():
    assert StateLedger.normalize_location("Bengaluru, Karnataka") == "bangalore"
    assert StateLedger.normalize_location("Bangalore Urban") == "bangalore"
    assert StateLedger.normalize_location("Gurugram (Gurgaon)") == "gurgaon"
    assert StateLedger.normalize_location("Remote - India") == "remote"


def test_fingerprint_equivalence_across_variations():
    # Job cross-posted on different platforms with minor punctuation/casing differences
    fp1 = StateLedger.generate_fingerprint(
        company="Microsoft",
        title="Software Engineer - I",
        location="Bengaluru, India"
    )
    fp2 = StateLedger.generate_fingerprint(
        company="microsoft",
        title="SDE 1",
        location="Bangalore"
    )
    assert fp1 == fp2
    assert len(fp1) == 64  # Valid SHA-256 length


def test_is_new_listing_and_duplicate_suppression(temp_ledger):
    fp = temp_ledger.generate_fingerprint("Amazon", "SDE 1", "Hyderabad")

    # First encounter -> brand new listing
    assert temp_ledger.is_new_listing(fp, "Amazon", "SDE 1", "Hyderabad") is True

    # Second encounter -> duplicate suppressed
    assert temp_ledger.is_new_listing(fp, "Amazon", "SDE 1", "Hyderabad") is False
    assert temp_ledger.get_total_fingerprints_count() == 1


def test_batch_check_and_register(temp_ledger):
    candidates = [
        {"company_name": "Google", "job_title": "Software Engineer 1", "location": "Bangalore"},
        {"company_name": "google", "job_title": "SDE - I", "location": "Bengaluru"},  # Duplicate
        {"company_name": "Meta", "job_title": "Research Engineer", "location": "Remote"},
    ]

    new_items, duplicates = temp_ledger.batch_check_and_register(candidates)
    assert len(new_items) == 2  # Google + Meta
    assert duplicates == 1
    assert temp_ledger.get_total_fingerprints_count() == 2

    # Second run with same listings -> 0 new, 3 duplicates
    new_items_2, duplicates_2 = temp_ledger.batch_check_and_register(candidates)
    assert len(new_items_2) == 0
    assert duplicates_2 == 3


def test_db_size_reporting(temp_ledger):
    assert temp_ledger.get_db_size_mb() >= 0.0

