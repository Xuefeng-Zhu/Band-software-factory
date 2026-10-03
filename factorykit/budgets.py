"""Finite consumption policy; importing this module never checks credentials."""
from __future__ import annotations


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
