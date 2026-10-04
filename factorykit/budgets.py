"""Finite consumption policy; importing this module never checks credentials."""
from __future__ import annotations

import json
import math
from pathlib import Path
import time
from uuid import UUID


FINITE_LIMITS = (
    "max_active_seats", "max_repairs", "turn_timeout_seconds",
    "stage_timeout_seconds", "overall_timeout_seconds",
    "max_turns_per_seat", "max_total_tokens",
)


def subscription_only(limits: dict) -> bool:
    return limits.get("billing_mode", "spend_cap") == "subscription_only"


def budget_errors(limits: dict) -> list[str]:
    errors = []
    for name in FINITE_LIMITS + (("ack_timeout_seconds",) if "ack_timeout_seconds" in limits else ()):
        value = limits.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            errors.append(f"budgets.{name} requires a finite positive integer")
    if not isinstance(limits.get("approved"), bool):
        errors.append("budgets.approved must be an explicit boolean")
    mode = limits.get("billing_mode", "spend_cap")
    if mode not in ("spend_cap", "subscription_only"):
        errors.append("budgets.billing_mode must be spend_cap or subscription_only")
    cap = limits.get("spend_cap_usd")
    if subscription_only(limits):
        if cap is not None:
            errors.append("subscription_only requires spend_cap_usd: null; it is not a measured zero-dollar cost")
        for name in ("api_billing_allowed", "paid_provisioning_allowed"):
            if limits.get(name) is not False:
                errors.append(f"subscription_only requires budgets.{name}: false")
    elif cap is not None and (isinstance(cap, bool) or not isinstance(cap, (int, float)) or not 0 < cap < float("inf")):
        errors.append("spend_cap_usd must be a finite positive number or null")
    if errors:
        return errors
    if limits["max_active_seats"] > 7:
        errors.append("max_active_seats cannot exceed seven")
    if limits["turn_timeout_seconds"] > limits["stage_timeout_seconds"] or limits["stage_timeout_seconds"] > limits["overall_timeout_seconds"]:
        errors.append("Timeouts must satisfy turn <= stage <= overall")
    return errors


def budget_blockers(limits: dict) -> list[str]:
    errors = budget_errors(limits)
    if limits.get("approved") is not True:
        errors.append("Approve finite active-work and consumption budgets before live seat work (budgets.approved=false)")
    if not subscription_only(limits) and limits.get("spend_cap_usd") is None:
        errors.append("Set an approved positive spend_cap_usd with provider billing enforcement, or explicitly approve the subscription_only policy")
    return errors


def room_scope(config: dict) -> tuple[list[str], list[str]]:
    """Return current messaging rooms and cumulative accounting rooms.

    Archived UUIDs retain consumption only; this helper never changes a ledger.
    Adding a room requires explicit reconciliation of its persisted exact scope.
    """
    band = config["band"]
    active = [band.get(f"{mode}_room_id") for mode in ("rehearsal", "judged")]
    archived = band.get("archived_room_ids", [])
    if (any(not isinstance(room, str) or not room.strip() or room != room.strip() for room in active)
            or len(set(active)) != 2):
        raise ValueError("Cumulative accounting requires two distinct configured active rooms.")
    if not isinstance(archived, list):
        raise ValueError("band.archived_room_ids must be a list of exact canonical room UUIDs.")
    try:
        valid = all(isinstance(room, str) and str(UUID(room)) == room for room in archived)
    except ValueError:
        valid = False
    if not valid or len(set(archived)) != len(archived) or set(active).intersection(archived):
        raise ValueError("band.archived_room_ids requires unique canonical UUIDs disjoint from active rooms.")
    return active, sorted(active + archived)


def persisted_budget_blockers(config: dict, *, now: float | None = None, require_existing: bool = False) -> list[str]:
    """Inspect aggregate consumption without constructing/writing a ledger.

    An absent ledger is normal before first rehearsal. Room stage halts remain
    live-start concerns: a completed rehearsal must not block a fresh judged room.
    """
    limits = config["budgets"]
    if not subscription_only(limits):
        return []
    invalid = ["Existing cumulative budget ledger is malformed or has changed scope; preserve it before launch."]
    try:
        active, rooms = room_scope(config)
    except (ValueError, TypeError, KeyError):
        return invalid
    path = Path(config["paths"]["runs"]) / "runtime/budget-subscription.json"
    if not path.exists() and not path.is_symlink():
        return ["Judged readiness requires the existing cumulative budget ledger; preserve rehearsal accounting before launch."] if require_existing or len(rooms) > len(active) else []
    try:
        if path.is_symlink():
            return invalid
        data = json.loads(path.read_text())
        instant = time.time() if now is None else now
        seats = {seat["id"] for seat in config["seats"]}
        def counts(value, allowed=None):
            return (isinstance(value, dict) and (allowed is None or set(value).issubset(allowed))
                    and all(isinstance(k, str) and type(v) is int and v >= 0 for k, v in value.items()))
        def epoch(value):
            return type(value) in (int, float) and math.isfinite(value) and 0 < value <= instant
        if (not isinstance(data, dict) or not {"room_id", "room_ids", "started_epoch", "tokens", "turns", "token_threads", "stopped_reason"}.issubset(data)
                or type(instant) not in (int, float) or not math.isfinite(instant)
                or data["room_id"] is not None or data["room_ids"] != rooms
                or type(data["tokens"]) is not int or data["tokens"] < 0
                or not counts(data["turns"], seats) or not counts(data["token_threads"])
                or (data["stopped_reason"] is not None and (not isinstance(data["stopped_reason"], str) or not data["stopped_reason"]))):
            return invalid
        origins = data.get("room_started_epochs", {})
        room_turns = data.get("room_turns", {})
        room_stops = data.get("room_stopped_reasons", {})
        if (any(not isinstance(value, dict) or not set(value).issubset(rooms) for value in (origins, room_turns, room_stops))
                or any(not epoch(value) for value in origins.values())
                or any(not counts(value, seats) for value in room_turns.values())
                or any(not isinstance(value, str) or not value for value in room_stops.values())):
            return invalid
        start = data["started_epoch"]
        if start is None:
            if data["tokens"] or any(data["turns"].values()) or data["token_threads"] or origins or room_turns or room_stops:
                return invalid
        elif not epoch(start) or any(value < start for value in origins.values()):
            return invalid
        blockers = []
        if data["stopped_reason"]:
            blockers.append("Persisted cumulative budget has a global stopped_reason; explicit reconciliation is required.")
        if start is not None and instant - start >= limits["overall_timeout_seconds"]:
            blockers.append("Cumulative overall time budget exhausted.")
        if data["tokens"] >= limits["max_total_tokens"]:
            blockers.append("Cumulative observed token budget exhausted.")
        blockers.extend(f"Cumulative turn budget exhausted for {seat}." for seat, value in sorted(data["turns"].items()) if value >= limits["max_turns_per_seat"])
        return blockers
    except (OSError, ValueError, TypeError, KeyError):
        return invalid


# This is an authentication restriction, not a promise of zero charge or a
# replacement for provider-side plan and billing controls.
SUBSCRIPTION_CONFIG = (
    '-c', 'forced_login_method="chatgpt"',
    '-c', 'model_provider="openai"',
    '-c', 'openai_base_url=""',
)
API_ENVIRONMENT = ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "CODEX_ACCESS_TOKEN", "OPENAI_FEDERATION_RULE_ID", "OPENAI_IDENTITY_TOKEN_FILE", "OPENAI_WORKLOAD_IDENTITY_CONTEXT")


def codex_argv(config: dict, *arguments: str) -> list[str]:
    extra = SUBSCRIPTION_CONFIG if subscription_only(config["budgets"]) else ()
    # BAND merges codex_env into inherited env; empty auth values can still
    # select an auth path. env -u truly removes these variables without a shell.
    prefix = ["/usr/bin/env", *(part for name in API_ENVIRONMENT for part in ("-u", name))] if extra else []
    return [*prefix, config["runtime"]["codex_command"], *extra, *arguments]


def subscription_auth_errors(config: dict) -> list[str]:
    """Read local login status only; never create a thread/turn or echo keys."""
    if not subscription_only(config["budgets"]):
        return []
    import os
    from .common import run_command
    if any(os.environ.get(name) for name in API_ENVIRONMENT):
        return ["subscription_only rejects API credential, external-token, workload-identity or endpoint environment overrides; remove them without exposing their values"]
    # Inspect existing authentication first, with no forced-login setting that
    # could invalidate an incompatible saved login at CLI startup.
    result = run_command([config["runtime"]["codex_command"], "login", "status"], config["paths"]["factory"], timeout=15)
    lines = (result.get("stdout", "") + "\n" + result.get("stderr", "")).splitlines()
    if result.get("exit_code") != 0 or "Logged in using ChatGPT" not in lines:
        return ["subscription_only requires verified ChatGPT login from the pinned CLI; API-key, unknown or unavailable authentication is blocked"]
    # preflight can run inside serve's event loop. A separate thread owns this
    # short-lived read-only SDK connection; it never starts a thread or turn.
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            verified = pool.submit(lambda: asyncio.run(subscription_auth_probe(config))).result()
    except Exception:
        return ["subscription_only could not verify effective provider/authentication without inference; no raw provider response printed"]
    if not verified:
        return ["subscription_only requires effective OpenAI provider and existing ChatGPT account; managed/provider overrides or unknown authentication are blocked"]
    return []


async def subscription_auth_probe(config: dict) -> bool:
    """Read supported account/config RPCs; discard personal and secret values."""
    import asyncio
    from band.integrations.codex.stdio_client import CodexStdioClient
    client = CodexStdioClient(command=codex_argv(config, "app-server", "--listen", "stdio://"), cwd=config["paths"]["factory"], env={name: "" for name in API_ENVIRONMENT})
    try:
        async with asyncio.timeout(20):
            await client.connect()
            await client.initialize(client_name="factory_subscription_probe", client_title="Factory subscription policy probe", client_version="1.0")
            account = await client.request("account/read", {"refreshToken": False})
            if account.get("requiresOpenaiAuth") is not True or (account.get("account") or {}).get("type") != "chatgpt":
                return False
            paths = {config["paths"][name] for name in ("factory", "rehearsal", "result")}
            paths.update(seat[key] for seat in config.get("seats", []) for key in ("cwd", "rehearsal_cwd", "judged_cwd") if seat.get(key))
            for path in sorted(paths):
                result = await client.request("config/read", {"cwd": path, "includeLayers": False})
                effective = result.get("config", {})
                if effective.get("model_provider") != "openai" or effective.get("forced_login_method") != "chatgpt":
                    return False
            return True
    finally:
        await client.close()
