"""
Unit tests for OmniSight State Fingerprinting & SQLite Ledger Engine.
"""

import os
import tempfile
import pytest
from core.omnisight import OmniSightEngine


@pytest.fixture
def temp_omnisight():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_path = tf.name
    engine = OmniSightEngine(db_path=temp_path)
    yield engine
    if os.path.exists(temp_path):
        os.remove(temp_path)


def test_normalize_title():
    t1 = "Software Development Engineer - I"
    t2 = "Software Engineer 1"
    t3 = "SDE - 1"
    # All should canonicalize to 'sde 1'
    assert OmniSightEngine.normalize_title(t1) == "sde 1"
    assert OmniSightEngine.normalize_title(t2) == "sde 1"
    assert OmniSightEngine.normalize_title(t3) == "sde 1"


def test_normalize_location():
    assert OmniSightEngine.normalize_location("Bengaluru, Karnataka") == "bangalore"
    assert OmniSightEngine.normalize_location("Bangalore Urban") == "bangalore"
    assert OmniSightEngine.normalize_location("Gurugram (Gurgaon)") == "gurgaon"
    assert OmniSightEngine.normalize_location("Remote - India") == "remote"


def test_fingerprint_equivalence_across_variations():
    # Job posted on Greenhouse with slightly different title punctuation and location text
    fp1 = OmniSightEngine.generate_fingerprint(
        company="Microsoft",
        title="Software Engineer - I",
        location="Bengaluru, India"
    )
    fp2 = OmniSightEngine.generate_fingerprint(
        company="microsoft",
        title="SDE 1",
        location="Bangalore"
    )
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 length


def test_is_new_listing_and_duplicate_suppression(temp_omnisight):
    fp = temp_omnisight.generate_fingerprint("Amazon", "SDE 1", "Hyderabad")

    # First time -> New listing
    is_new = temp_omnisight.is_new_listing(fp, "Amazon", "SDE 1", "Hyderabad")
    assert is_new is True

    # Second time -> Duplicate suppressed
    is_new_second = temp_omnisight.is_new_listing(fp, "Amazon", "SDE 1", "Hyderabad")
    assert is_new_second is False

    assert temp_omnisight.get_total_fingerprints_count() == 1


def test_batch_check_and_register(temp_omnisight):
    candidates = [
        {"company_name": "Google", "job_title": "Software Engineer 1", "location": "Bangalore"},
        {"company_name": "google", "job_title": "SDE - I", "location": "Bengaluru"},  # Duplicate of item 1
        {"company_name": "Meta", "job_title": "Research Engineer", "location": "Remote"},
    ]

    new_items, duplicates = temp_omnisight.batch_check_and_register(candidates)
    assert len(new_items) == 2  # Google + Meta
    assert duplicates == 1
    assert temp_omnisight.get_total_fingerprints_count() == 2

    # Run again with same candidates -> 0 new items, 3 duplicates
    new_items_2, duplicates_2 = temp_omnisight.batch_check_and_register(candidates)
    assert len(new_items_2) == 0
    assert duplicates_2 == 3


def test_db_size_reporting(temp_omnisight):
    size_mb = temp_omnisight.get_db_size_mb()
    assert size_mb >= 0.0

