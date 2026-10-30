import json
import unittest

from fastmcp import Client

from simple_mcp_server.server import mcp


async def call(tool: str, args: dict) -> dict:
    async with Client(mcp) as client:
        result = await client.call_tool(tool, args)
    return json.loads(result.content[0].text)


class ToolSurfaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_tools_are_exposed(self) -> None:
        async with Client(mcp) as client:
            tools = await client.list_tools()

        self.assertEqual(
            {t.name for t in tools},
            {
                "verify_identity",
                "check_deceased",
                "verify_relationship",
                "screen_watchlist",
                "check_contactability",
                "assess_fraud_signals",
            },
        )


class IdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_reports_date_of_birth_discrepancy_without_dropping_record(self) -> None:
        result = await call("verify_identity", {"name": "Carlos Garcia", "date_of_birth": "1990-01-01"})

        self.assertTrue(result["found"])
        self.assertEqual(result["identityConfidence"], 0.86)
        self.assertEqual(len(result["discrepancies"]), 1)

    async def test_flags_a_minor(self) -> None:
        result = await call("verify_identity", {"name": "Rebecca Thompson"})

        self.assertTrue(result["isMinor"])

    async def test_unknown_name_is_reported_as_absence_not_failure(self) -> None:
        result = await call("verify_identity", {"name": "Wilhelmina Fotheringay"})

        self.assertFalse(result["found"])
        self.assertIn("not evidence of a problem", result["note"])


class DeathRegisterTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_register_hit_with_source_currency(self) -> None:
        result = await call("check_deceased", {"name": "Lisa Nguyen"})

        self.assertTrue(result["registerHit"])
        self.assertEqual(result["dateOfDeath"], "2025-02-14")
        self.assertEqual(result["matchScore"], 0.91)

    async def test_absence_of_hit_is_qualified(self) -> None:
        result = await call("check_deceased", {"name": "Mark Thompson"})

        self.assertFalse(result["registerHit"])
        self.assertIn("does not confirm", result["note"])


class RelationshipTests(unittest.IsolatedAsyncioTestCase):
    async def test_divorce_contradicts_a_spouse_claim(self) -> None:
        result = await call(
            "verify_relationship",
            {
                "policy_holder_name": "James Mitchell",
                "beneficiary_name": "Patricia Mitchell",
                "claimed_relationship": "spouse",
            },
        )

        self.assertEqual(result["recordedStatus"], "divorced")
        self.assertFalse(result["consistentWithClaim"])
        self.assertTrue(any(r["type"] == "divorce" for r in result["records"]))

    async def test_marriage_corroborates_a_spouse_claim(self) -> None:
        result = await call(
            "verify_relationship",
            {
                "policy_holder_name": "Sarah Thompson",
                "beneficiary_name": "Mark Thompson",
                "claimed_relationship": "spouse",
            },
        )

        self.assertTrue(result["consistentWithClaim"])

    async def test_unrecorded_relationship_is_not_asserted_false(self) -> None:
        result = await call(
            "verify_relationship",
            {
                "policy_holder_name": "Sarah Thompson",
                "beneficiary_name": "Daniel Reeves",
                "claimed_relationship": "friend",
            },
        )

        self.assertFalse(result["recordsFound"])
        self.assertTrue(result["searched"])
        self.assertIn("frequently leave no record", result["note"])


class WatchlistTests(unittest.IsolatedAsyncioTestCase):
    async def test_near_match_is_returned_with_discriminators(self) -> None:
        result = await call("screen_watchlist", {"name": "Helen Kim"})

        self.assertEqual(result["hitCount"], 1)
        hit = result["hits"][0]
        self.assertEqual(hit["matchScore"], 0.84)
        self.assertIn("dateOfBirth", hit["discriminators"])

    async def test_clean_subject_returns_no_hits(self) -> None:
        result = await call("screen_watchlist", {"name": "Mark Thompson"})

        self.assertEqual(result["hitCount"], 0)


class ContactabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_undeliverable_address_makes_party_uncontactable(self) -> None:
        result = await call("check_contactability", {"name": "Carlos Garcia"})

        self.assertFalse(result["contactable"])
        self.assertEqual(len(result["undeliverableAddresses"]), 1)

    async def test_supplied_email_absent_from_record_is_flagged(self) -> None:
        result = await call(
            "check_contactability",
            {"name": "Carlos Garcia", "email": "someone.else@example.com"},
        )

        self.assertFalse(result["suppliedEmailOnRecord"])


class FraudSignalTests(unittest.IsolatedAsyncioTestCase):
    async def test_serial_beneficiary_surfaces_as_high_severity(self) -> None:
        result = await call(
            "assess_fraud_signals",
            {"policy_number": "NWM-2025-002", "beneficiary_name": "Daniel Reeves"},
        )

        self.assertEqual(result["highestSeverity"], "high")
        self.assertIn("SERIAL_BENEFICIARY", [s["code"] for s in result["signals"]])

    async def test_request_history_accompanies_the_signals(self) -> None:
        result = await call(
            "assess_fraud_signals",
            {"policy_number": "NWM-2025-002", "beneficiary_name": "Daniel Reeves"},
        )

        history = result["requestHistory"]
        self.assertFalse(history["lastRequest"]["stepUpAuthCompleted"])
        self.assertEqual(len(history["priorChanges"]), 1)

    async def test_unprofiled_subject_is_distinguished_from_a_clean_one(self) -> None:
        result = await call(
            "assess_fraud_signals",
            {"policy_number": "NWM-2025-001", "beneficiary_name": "Wilhelmina Fotheringay"},
        )

        self.assertFalse(result["beneficiaryProfiled"])
        self.assertEqual(result["signals"], [])


if __name__ == "__main__":
    unittest.main()
