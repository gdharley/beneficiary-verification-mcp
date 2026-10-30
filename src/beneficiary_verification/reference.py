"""Access layer for the verification reference data.

This data represents a third-party system of record. It is deliberately
independent of the policy administration system: records are keyed by name and
date of birth rather than by policy number, and may disagree with what the
policy system holds.
"""

import json
from difflib import SequenceMatcher
from functools import lru_cache
from importlib import resources
from typing import Any

NAME_MATCH_THRESHOLD = 0.80


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    """Load and cache the reference dataset."""
    source = resources.files(__package__) / "data" / "reference_data.json"
    return json.loads(source.read_text(encoding="utf-8"))


def name_similarity(left: str, right: str) -> float:
    """Return a 0..1 similarity score for two personal names."""
    return round(SequenceMatcher(None, left.strip().lower(), right.strip().lower()).ratio(), 2)


def find_individual(name: str, date_of_birth: str | None = None) -> tuple[dict[str, Any] | None, float]:
    """Return the best individual record for a name, with its match score.

    Date of birth is used to discriminate between similarly named records, not
    to exclude them: a date mismatch is reported to the caller rather than
    silently dropping the record.
    """
    best: dict[str, Any] | None = None
    best_score = 0.0

    for record in load()["individuals"]:
        score = name_similarity(name, record["name"])
        if date_of_birth and record.get("dateOfBirth") == date_of_birth:
            score = min(1.0, score + 0.05)
        if score > best_score:
            best, best_score = record, score

    if best_score < NAME_MATCH_THRESHOLD:
        return None, best_score
    return best, best_score


def find_relationship(party_a: str, party_b: str) -> dict[str, Any] | None:
    """Return the relationship record linking two parties, in either direction."""
    for record in load()["relationships"]:
        pair = {record["partyA"].lower(), record["partyB"].lower()}
        if pair == {party_a.strip().lower(), party_b.strip().lower()}:
            return record
    return None


def find_fraud_signals(name: str) -> list[dict[str, Any]] | None:
    """Return recorded fraud signals for a subject, or None if not profiled."""
    for record in load()["fraudSignals"]:
        if name_similarity(name, record["subjectName"]) >= NAME_MATCH_THRESHOLD:
            return record["signals"]
    return None


def find_channel_history(policy_number: str) -> dict[str, Any] | None:
    """Return the request channel history recorded for a policy."""
    for record in load()["requestChannelHistory"]:
        if record["policyNumber"].strip().lower() == policy_number.strip().lower():
            return record
    return None
