# beneficiary-verification-mcp

An MCP server providing **third-party verification data for life insurance
beneficiary change requests**, built for a Flowable demo.

It is deliberately *not* a wrapper over the policy administration system. The
Flowable process retrieves the policy and the requested change through the
existing REST services; an agent then calls these tools for the independent
evidence the policy system cannot hold — public records, death registers,
watchlists and fraud clearinghouse signals.

Every tool returns **evidence with confidence scores, never a decision**. Judging
whether a change may proceed is left to the agent and, where the evidence is
ambiguous, to a human task in Flowable.

## Tools

| Tool | Returns |
| --- | --- |
| `verify_identity(name, date_of_birth?, address?)` | Match score, identity confidence, address history, discrepancies, minor flag |
| `check_deceased(name, date_of_birth?)` | Death register match score, date of death, source currency |
| `verify_relationship(policy_holder_name, beneficiary_name, claimed_relationship)` | Marriage/divorce/cohabitation records and consistency with the claim |
| `screen_watchlist(name, date_of_birth?)` | Sanctions and PEP hits with match scores and discriminators |
| `check_contactability(name, email?, phone?)` | Last-verified dates, bounce counts, undeliverable addresses |
| `assess_fraud_signals(policy_number, beneficiary_name)` | Clearinghouse signals plus the request's channel and authentication history |

## Demo scenarios

The reference data is seeded so that each policy in the demo JSON server
produces a materially different outcome. In every case the external evidence is
something the policy system could not know on its own.

| Policy | Proposed beneficiary | What the evidence shows | Expected handling |
| --- | --- | --- | --- |
| LIF-2025-001 (James Mitchell) | Caroline Whitfield, domestic partner | Divorce from the existing beneficiary recorded 2023; shared address with the new beneficiary since 2024 | Change is corroborated — proceed |
| LIF-2025-002 (Sarah Thompson) | Daniel Reeves, friend | Named on 3 unrelated policies in 9 months, contact email reused across designations, no step-up auth, prior change reversed by the holder | Fraud investigation |
| LIF-2025-003 (David Nguyen) | Lisa Nguyen, spouse | Death register hit at 0.91, date of death 2025-02-14 | Cannot name a deceased beneficiary — clarify with holder |
| LIF-2025-004 (Maria Garcia) | Carlos Garcia, spouse | Identity confidence 0.86 on a common name, date of birth mismatch, mail returned twice | Genuinely ambiguous — escalate for outreach |
| LIF-2023-005 (Robert Kim) | Helen Kim, spouse | Watchlist phonetic near-match at 0.84, no corroborating identifiers | Adjudicate the near-match before proceeding |

Note that LIF-2025-001 carries `otp_processing_allowed: true` in the policy
system. The demo's point is that external evidence can override straight-through
processing in either direction.

All individuals, lists and records are synthetic.

## Requirements

- Python 3.12+

## Install

```bash
./.venv/bin/python -m pip install -e .
```

## Run the server

```bash
PYTHONPATH=src ./.venv/bin/python -m beneficiary_verification
```

Or, after installing:

```bash
beneficiary-verification-mcp
```

The MCP endpoint is `http://127.0.0.1:9000/mcp`.

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Bind address. Render sets this to `0.0.0.0`. |
| `PORT` | `9000` | Bind port. Injected by Render. |
| `MCP_AUTH_TOKEN` | unset | When set, requires `Authorization: Bearer <token>`. When unset, the server runs unauthenticated and logs a warning. |

Set `MCP_AUTH_TOKEN` for any deployment that is publicly reachable.

## Run tests

```bash
PYTHONPATH=src ./.venv/bin/python -m unittest discover -s tests -v
```

## Deploy to Render

The repo includes a `render.yaml` blueprint. In Render, choose **New > Blueprint**
and point it at this repository; it provisions a single web service. The
blueprint declares `MCP_AUTH_TOKEN` with `sync: false`, so Render prompts for the
value rather than storing it in the repo.

Once deployed, the MCP endpoint is:

```text
https://<service-name>.onrender.com/mcp
```

Note: the blueprint sets no `healthCheckPath`. A plain `GET /mcp` returns `406`
because the transport requires an SSE-capable `Accept` header, so a health check
against it would fail the deploy. Render falls back to port detection instead.

On the free plan the service sleeps after ~15 minutes idle, and the next request
pays a cold start of roughly 30 seconds.
