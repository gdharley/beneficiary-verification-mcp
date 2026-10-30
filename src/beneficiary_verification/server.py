"""Beneficiary verification tools for a life insurance beneficiary change request.

These tools expose a third-party verification system of record: public records,
death registers, watchlists and fraud clearinghouse signals. They are intended
to be called by an agent that has already retrieved the policy and the requested
beneficiary change from the policy administration system.

Every tool returns evidence with confidence scores and never returns a decision.
Judging whether a change may proceed is the caller's job.
"""

import logging
import os
from datetime import date

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

from . import reference

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INSTRUCTIONS = """
Verification services for life insurance beneficiary change requests.

Retrieve the policy and the requested change from the policy administration
system first, then use these tools to gather independent evidence about the
parties involved. Tools report what the public record holds, with match scores
and discriminating details. They do not approve or decline a change.

A low match score or a near-match on a watchlist is not proof of anything. Weigh
the discriminators returned alongside it and escalate genuinely ambiguous cases
to a human reviewer rather than resolving them.
""".strip()


def _build_auth() -> StaticTokenVerifier | None:
    """Enable bearer token auth when MCP_AUTH_TOKEN is set."""
    token = os.environ.get("MCP_AUTH_TOKEN")
    if not token:
        logger.warning("MCP_AUTH_TOKEN is not set; server is running unauthenticated")
        return None
    return StaticTokenVerifier(tokens={token: {"client_id": "flowable-demo", "scopes": []}})


mcp = FastMCP("Beneficiary Verification Services", instructions=INSTRUCTIONS, auth=_build_auth())


def _age_on(date_of_birth: str, as_of: date | None = None) -> int | None:
    """Return the age in whole years implied by a date of birth."""
    try:
        born = date.fromisoformat(date_of_birth)
    except (TypeError, ValueError):
        return None
    today = as_of or date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _not_found(name: str, score: float) -> dict:
    """Shape the response for a subject with no sufficiently close record."""
    return {
        "found": False,
        "searchedName": name,
        "bestMatchScore": score,
        "evidence": "No public record matched this name closely enough to report.",
        "note": "Absence of a record is not evidence of a problem. Thin-file individuals and recent immigrants commonly have no footprint.",
    }


@mcp.tool
def verify_identity(name: str, date_of_birth: str | None = None, address: str | None = None) -> dict:
    """Corroborate that a named individual exists in the public record.

    Returns the matched record's confidence, known addresses and any
    discrepancies against the supplied details. A date of birth sharpens the
    match but a mismatch is reported rather than used to exclude the record.
    """
    logger.info("verify_identity name=%s dob=%s", name, date_of_birth)
    record, score = reference.find_individual(name, date_of_birth)
    if record is None:
        return _not_found(name, score)

    discrepancies = []
    if date_of_birth and record["dateOfBirth"] != date_of_birth:
        discrepancies.append(
            f"Supplied date of birth {date_of_birth} does not match the record value {record['dateOfBirth']}."
        )
    if address and not any(address.lower() in a["line1"].lower() for a in record["addresses"]):
        discrepancies.append(f"Supplied address '{address}' does not appear in the recorded address history.")

    age = _age_on(record["dateOfBirth"])
    return {
        "found": True,
        "recordId": record["recordId"],
        "matchedName": record["name"],
        "nameMatchScore": score,
        "identityConfidence": record["identityConfidence"],
        "dateOfBirth": record["dateOfBirth"],
        "ageYears": age,
        "isMinor": age is not None and age < 18,
        "addresses": record["addresses"],
        "discrepancies": discrepancies,
        "sourceNote": record["notes"],
    }


@mcp.tool
def check_deceased(name: str, date_of_birth: str | None = None) -> dict:
    """Check a named individual against the death register.

    Returns the register match score, recorded date of death and how current the
    source is. Register data lags reality, so a negative result is weaker
    evidence than a positive one.
    """
    logger.info("check_deceased name=%s dob=%s", name, date_of_birth)
    record, score = reference.find_individual(name, date_of_birth)
    if record is None:
        return _not_found(name, score)

    entry = record.get("deathRegister")
    if not entry:
        return {
            "found": True,
            "matchedName": record["name"],
            "nameMatchScore": score,
            "registerHit": False,
            "note": "No death register entry. Register updates lag by weeks to months, so this does not confirm the subject is living.",
        }

    return {
        "found": True,
        "matchedName": record["name"],
        "nameMatchScore": score,
        "registerHit": True,
        "matchScore": entry["matchScore"],
        "dateOfDeath": entry["dateOfDeath"],
        "source": entry["source"],
        "sourceUpdated": entry["sourceUpdated"],
        "matchNote": entry["note"],
    }


@mcp.tool
def verify_relationship(policy_holder_name: str, beneficiary_name: str, claimed_relationship: str) -> dict:
    """Corroborate a claimed relationship between a policy holder and a beneficiary.

    Returns marriage, divorce and cohabitation records linking the two parties,
    and whether the public record is consistent with what was claimed. A claim
    that cannot be corroborated is not necessarily false.
    """
    logger.info(
        "verify_relationship holder=%s beneficiary=%s claimed=%s",
        policy_holder_name,
        beneficiary_name,
        claimed_relationship,
    )
    record = reference.find_relationship(policy_holder_name, beneficiary_name)
    records = record["records"] if record else []
    status = record["currentStatus"] if record else "no recorded relationship"
    claimed = claimed_relationship.strip().lower()

    if not records:
        return {
            "recordsFound": False,
            "policyHolder": policy_holder_name,
            "beneficiary": beneficiary_name,
            "claimedRelationship": claimed_relationship,
            "recordedStatus": status,
            "records": [],
            "consistentWithClaim": False,
            "searched": record is not None,
            "note": "No public record links these parties. Relationships such as friend, carer or business partner frequently leave no record, so this neither supports nor refutes the claim.",
        }

    return {
        "recordsFound": True,
        "policyHolder": record["partyA"],
        "beneficiary": record["partyB"],
        "claimedRelationship": claimed_relationship,
        "recordedStatus": status,
        "records": records,
        "consistentWithClaim": claimed in status.lower() or (claimed == "spouse" and status == "married"),
        "searched": True,
        "note": "Where the recorded status contradicts the claim, check the dates: a designation may simply predate a change in circumstances.",
    }


@mcp.tool
def screen_watchlist(name: str, date_of_birth: str | None = None) -> dict:
    """Screen a named individual against sanctions and PEP watchlists.

    Returns each hit with its match score, which fields matched and which
    identifiers discriminate against it. Phonetic near-matches on common names
    are frequent and are reported in full for adjudication.
    """
    logger.info("screen_watchlist name=%s dob=%s", name, date_of_birth)
    record, score = reference.find_individual(name, date_of_birth)
    if record is None:
        return _not_found(name, score)

    hits = record.get("watchlist", [])
    return {
        "found": True,
        "matchedName": record["name"],
        "nameMatchScore": score,
        "hitCount": len(hits),
        "hits": hits,
        "note": "Lists screened are synthetic demo lists. A hit requires adjudication against the discriminators before any action is taken.",
    }


@mcp.tool
def check_contactability(name: str, email: str | None = None, phone: str | None = None) -> dict:
    """Assess whether a party can be reached at the contact details on file.

    Returns last-verified dates, bounce counts and delivery status. Relevant to
    a beneficiary change because an uncontactable party cannot confirm a
    designation out of band.
    """
    logger.info("check_contactability name=%s email=%s", name, email)
    record, score = reference.find_individual(name)
    if record is None:
        return _not_found(name, score)

    emails = record["emails"]
    phones = record["phones"]
    unknown_email = bool(email) and not any(e["address"].lower() == email.lower() for e in emails)
    undeliverable = [a for a in record["addresses"] if a.get("status") == "undeliverable"]

    return {
        "found": True,
        "matchedName": record["name"],
        "nameMatchScore": score,
        "emails": emails,
        "phones": phones,
        "suppliedEmailOnRecord": not unknown_email if email else None,
        "undeliverableAddresses": undeliverable,
        "contactable": bool(emails or phones) and not undeliverable,
        "note": "A supplied email absent from the record is common after a change of provider, but is also the pattern seen when a third party substitutes their own contact details.",
    }


@mcp.tool
def assess_fraud_signals(policy_number: str, beneficiary_name: str) -> dict:
    """Retrieve fraud clearinghouse signals for a proposed beneficiary change.

    Returns signals recorded against the proposed beneficiary together with the
    channel and authentication history of the request itself. Signals are
    observations, not findings: weigh severity and corroboration together.
    """
    logger.info("assess_fraud_signals policy=%s beneficiary=%s", policy_number, beneficiary_name)
    signals = reference.find_fraud_signals(beneficiary_name)
    history = reference.find_channel_history(policy_number)

    return {
        "policyNumber": policy_number,
        "beneficiaryName": beneficiary_name,
        "beneficiaryProfiled": signals is not None,
        "signals": signals or [],
        "highestSeverity": max((s["severity"] for s in signals or []), key=_severity_rank, default=None),
        "requestHistory": history,
        "note": "No signals recorded means the clearinghouse holds nothing on this subject, not that the subject is cleared.",
    }


def _severity_rank(severity: str) -> int:
    """Order severity labels so the highest can be selected."""
    return {"low": 1, "medium": 2, "high": 3}.get(severity, 0)
