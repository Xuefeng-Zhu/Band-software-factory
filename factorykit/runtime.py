"""Official BAND CodexAdapter integration and narrowly owned process lifecycle.

All network/model operations are explicit CLI commands. Importing this module is inert.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import tempfile
import time
from typing import Any

import psutil
import yaml
from .budgets import API_ENVIRONMENT, budget_blockers, codex_argv, subscription_auth_errors, subscription_only

SDK_VERSION = "4.0.0"
EMITTED = ("tool_calls", "task_events", "usage")


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            output.write(json.dumps(value, indent=2) + "\n")
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def fingerprint(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def state_dir(config: dict) -> Path:
    return Path(config["paths"]["runs"]) / "runtime"


def get_config(args) -> dict:
    from .common import load_config
    return getattr(args, "loaded_config", None) or load_config(args.config)


async def discover_models(config: dict) -> dict:
    """Only initialize + model/list; never create a thread or inference turn."""
    from band.integrations.codex.stdio_client import CodexStdioClient
    # Discovery reads the existing account without imposing login restrictions.
    # Subscription authentication is checked separately before any seat launch.
    command = [config["runtime"]["codex_command"], "app-server", "--listen", "stdio://"]
    client = CodexStdioClient(command=command, cwd=config["paths"]["factory"])
    try:
        async with asyncio.timeout(35):
            await client.connect()
            initialized = await client.initialize(client_name="factory_model_discovery", client_title="Factory model discovery", client_version="1.0")
            models = []
            cursor = None
            for _ in range(20):
                params = {"limit": 100, "includeHidden": False}
                if cursor:
                    params["cursor"] = cursor
                result = await client.request("model/list", params)
                models.extend(result.get("data", []))
                cursor = result.get("nextCursor")
                if not cursor:
                    break
            else:
                raise RuntimeError("model/list pagination exceeded bound")
            return {"checked_at": timestamp(), "method": "initialize + model/list", "inference_started": False, "sdk_version": SDK_VERSION, "codex_version": config["runtime"].get("version"), "server": initialized, "models": models}
    finally:
        await client.close()


def cmd_discover(args) -> int:
    config = get_config(args)
    result = asyncio.run(discover_models(config))
    output = Path(args.output) if args.output else state_dir(config) / "models.json"
    save_json(output, result)
    print(json.dumps({"output": str(output), "models": [{"id": m.get("id"), "model": m.get("model"), "reasoning": m.get("supportedReasoningEfforts")} for m in result["models"]], "inference_started": False}, indent=2))
    return 0


def register_commands(subparsers) -> None:
    parser = subparsers.add_parser("discover-models", help="Read authenticated Codex model/list; no inference")
    parser.add_argument("--output")
    parser.set_defaults(func=cmd_discover)
    parser = subparsers.add_parser("probe-registration", help="Read BAND identity and room membership; no model or room messages")
    parser.add_argument("--mode", choices=["rehearsal", "judged"], default="rehearsal")
    parser.set_defaults(func=cmd_probe)
    parser = subparsers.add_parser("start-seats", help="Start gated BAND seats as one owned supervisor")
    parser.add_argument("--mode", choices=["rehearsal", "judged"], default="rehearsal")
    parser.set_defaults(func=cmd_start)
    parser = subparsers.add_parser("seat-status", help="Inspect the owned supervisor and local budget state")
    parser.set_defaults(func=cmd_status)
    parser = subparsers.add_parser("stop-seats", help="Stop only identity-verified factory-owned processes")
    parser.set_defaults(func=cmd_stop)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "config/factory.yaml"))
    sub = parser.add_subparsers(dest="command", required=True)
    register_commands(sub)
    worker = sub.add_parser("_serve", help=argparse.SUPPRESS)
    worker.add_argument("--mode", required=True, choices=["rehearsal", "judged"])
    worker.add_argument("--owner-token", required=True)
    worker.set_defaults(func=cmd_serve)
    args = parser.parse_args()
    try:
        return args.func(args) or 0
    except Exception as error:
        # Provider exceptions can include credentials and headers. Do not print them.
        print(json.dumps({"status": "blocked", "error_type": type(error).__name__, "detail": str(error) if isinstance(error, GateError) else "Operation failed; no raw provider response printed."}))
        return 2


class GateError(RuntimeError):
    """A safe, deliberately redacted actionable preflight error."""


def credentials(config: dict) -> dict:
    path = Path(config["band"]["credentials_file"])
    if not path.is_file():
        raise GateError("BAND SDK credentials file is missing; obtain credentials through official dashboard for configured identities.")
    if path.is_symlink():
        raise GateError("BAND credentials file must be a regular private file, not a symlink.")
    if stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
        raise GateError("BAND credentials directory must be owner-only (chmod 700).")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise GateError("BAND credentials file must be owner-only (chmod 600).")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise GateError("BAND credentials file must map seat ids to agent_id/api_key.")
    for seat in config["seats"]:
        value = data.get(seat["id"], {})
        if not value.get("agent_id") or not value.get("api_key"):
            raise GateError(f"BAND credentials missing for seat {seat['id']}.")
        if seat.get("agent_id") and value["agent_id"] != seat["agent_id"]:
            raise GateError(f"Credential identity differs from configured seat {seat['id']}.")
    ids = [data[s["id"]]["agent_id"] for s in config["seats"]]
    if len(ids) != len(set(ids)):
        raise GateError("Each seat requires a distinct registered BAND identity.")
    return data


def preflight_runtime(config: dict, mode: str = "rehearsal") -> list[str]:
    errors = []
    rt, bd, limits = config["runtime"], config["band"], config["budgets"]
    if importlib.metadata.version("band-sdk") != SDK_VERSION:
        errors.append(f"Install pinned band-sdk=={SDK_VERSION}.")
    if not bd.get(f"{mode}_room_id"):
        errors.append(f"Set band.{mode}_room_id to the verified existing room UUID.")
    if bd.get("rehearsal_room_id") and bd.get("rehearsal_room_id") == bd.get("judged_room_id"):
        errors.append("Rehearsal and judged rooms must be distinct.")
    if rt.get("sandbox") != "workspace-write" or rt.get("approval_policy") != "never" or rt.get("approval_mode") != "auto_decline" or rt.get("allow_network"):
        errors.append("Runtime requires workspace-write, never, auto_decline and allow_network=false.")
    # Use the same hash-bound observed evidence as freeze, but only permission
    # prerequisites: requiring completed toy collaboration here would deadlock
    # the very rehearsal needed to obtain that proof.
    from .validation import observations
    observed, _ = observations(config)
    verified_permissions = {item["id"] for item in observed}
    for check in ("permissions_agent_write_git", "permissions_docker_build", "permissions_browser", "permissions_development_network"):
        if check not in verified_permissions:
            errors.append(f"Verified agent permission evidence is required: {check} (host-only checks do not suffice).")
    errors.extend(budget_blockers(limits))
    errors.extend(subscription_auth_errors(config))
    if subscription_only(limits) and any((state_dir(config) / f"budget-{other}.json").exists() for other in ("rehearsal", "judged")):
        errors.append("Subscription aggregate accounting cannot migrate existing per-mode ledgers automatically; reconcile prior consumption before authorizing a new session.")
    assigned = [room_workspace(config, seat, mode) for seat in config["seats"]]
    if limits.get("max_active_seats", 3) > 1 and len(assigned) != len(set(assigned)):
        errors.append("Shared checkouts require max_active_seats=1; use the real single-writer fallback.")
    if limits.get("max_active_seats", 3) > 1:
        git_dirs = []
        for path in assigned:
            if not path.is_dir() or not (path / ".git").is_file():
                errors.append("Concurrent seats require real separate Git worktrees after the first team-authored commit.")
                continue
            try:
                git_dir = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], cwd=path, capture_output=True, text=True, timeout=5, check=True).stdout.strip()
                subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=path, capture_output=True, timeout=5, check=True)
                git_dirs.append(git_dir)
            except (OSError, subprocess.SubprocessError):
                errors.append("Concurrent seat worktree commit/isolation could not be verified.")
        if len(git_dirs) != len(set(git_dirs)):
            errors.append("Concurrent seat paths share Git metadata; use distinct worktrees.")
    roots = [Path(config["paths"]["result"]).resolve(), Path(config["paths"]["rehearsal"]).resolve()]
    for path in assigned:
        if any(path != root and path.is_relative_to(root) for root in roots):
            errors.append("Seat worktrees must live outside result and rehearsal result directories.")
    if limits.get("max_active_seats", 3) > 2:
        errors.append("At most two seats may run Codex turns concurrently.")
    try:
        credentials(config)
    except GateError as error:
        errors.append(str(error))
    models_path = state_dir(config) / "models.json"
    models = json.loads(models_path.read_text()).get("models", []) if models_path.is_file() else []
    known = {m.get("model", m.get("id")): m for m in models}
    for seat in config["seats"]:
        model = seat.get("model") or rt.get("model")
        if not model or model not in known:
            errors.append(f"Seat {seat['id']} needs an explicit model verified by discover-models.")
        elif seat.get("reasoning_effort") not in {e.get("reasoningEffort") for e in known[model].get("supportedReasoningEfforts", [])}:
            errors.append(f"Seat {seat['id']} reasoning_effort is not advertised by that model.")
        if not seat.get("handle") or not seat.get("agent_id") or not seat.get("registration_verified"):
            errors.append(f"Seat {seat['id']} needs its real BAND handle/id and registration verification.")
        if not Path(seat["mandate"]).is_file():
            errors.append(f"Seat {seat['id']} mandate file is missing.")
    proof_path = state_dir(config) / f"registration-{mode}.json"
    proof = json.loads(proof_path.read_text()) if proof_path.is_file() else {}
    if proof.get("config_sha256") != fingerprint(config) or not proof.get("verified"):
        errors.append(f"Run probe-registration --mode {mode} after finalizing configuration; matching proof is missing.")
    if mode == "judged" and not config.get("launch", {}).get("practice_mode") and not config.get("launch", {}).get("submission_open_verified"):
        errors.append("Judged launch is blocked until the event submission window is verified open.")
    return errors


def room_workspace(config: dict, seat: dict, mode: str) -> Path:
    # Shared checkout is the initial single-writer fallback. Toolkit/team owns
    # later external worktree creation and .env copying; never create silently.
    custom = seat.get(f"{mode}_cwd") or seat.get("cwd")
    if custom:
        return Path(custom).resolve()
    base = Path(config["paths"]["rehearsal"] if mode == "rehearsal" else config["paths"]["result"])
    return base.resolve()


def adapter_config(config: dict, seat: dict, mode: str):
    from band.adapters import CodexAdapterConfig
    room = config["band"][f"{mode}_room_id"]
    workspace = room_workspace(config, seat, mode)
    if not workspace.is_dir():
        raise GateError(f"Seat {seat['id']} workspace is missing: {workspace}")
    def resolve(room_id: str) -> str:
        if room_id != room:
            raise GateError("Unexpected room blocked before creating a Codex process.")
        return str(workspace)
    options = dict(
        transport="stdio", model=seat.get("model") or config["runtime"].get("model"),
        workspace_for_room=resolve,
        codex_command=tuple(codex_argv(config, "app-server", "--listen", "stdio://")),
        codex_env={"GIT_AUTHOR_NAME": seat["git_name"], "GIT_COMMITTER_NAME": seat["git_name"], "GIT_AUTHOR_EMAIL": seat["git_email"], "GIT_COMMITTER_EMAIL": seat["git_email"], **({name: "" for name in API_ENVIRONMENT} if subscription_only(config["budgets"]) else {})},
        custom_section=standing_instructions(config, seat),
        reasoning_effort=seat["reasoning_effort"], reasoning_summary="none",
        approval_policy="never", approval_mode="auto_decline", approval_timeout_decision="decline", approval_text_notifications=False,
        sandbox="workspace-write", sandbox_policy={"type": "workspaceWrite", "writableRoots": [str(workspace)], "networkAccess": False},
        turn_timeout_s=config["budgets"]["turn_timeout_seconds"],
        enable_self_config_tools=False, emit_turn_task_markers=False, emit_turn_lifecycle_events=True,
        stream_reasoning_events=False, stream_commentary_events=False, stream_plan_events=False,
        emit_diff_events=True, emit_token_usage_events=True,
        additional_dynamic_tools=[], skill_roots=[], personality="pragmatic",
    )
    # Explicit values win over every CODEX_* environment variable, including
    # fields not used by this runner. Pin defaults so shell settings cannot
    # silently change a frozen adapter's behavior.
    defaults = {name: field.get_default(call_default_factory=True) for name, field in CodexAdapterConfig.model_fields.items()}
    return CodexAdapterConfig(**(defaults | options))


def standing_instructions(config: dict, seat: dict) -> str:
    root = Path(config["paths"]["factory"])
    sections = [Path(seat["mandate"]).read_text()]
    sections.extend(path.read_text() for path in sorted((root / "protocols").glob("*.md")))
    roster = [{k: s.get(k) for k in ("id", "display_name", "handle", "agent_id", "model", "harness", "reasoning_effort")} for s in config["seats"]]
    sections.append("# Frozen runtime metadata\n" + json.dumps({"seat": seat["id"], "roster": roster, "budgets": config["budgets"], "slash_commands": "disabled; model, reasoning and permissions are immutable"}, indent=2))
    return "\n\n".join(sections)


def slash_command(content: str) -> bool:
    # Match the SDK's public mention normalizer, blocking ALL slash commands.
    from band.runtime.formatters import strip_leading_mentions
    return strip_leading_mentions(content).lstrip().startswith("/")


class RoomPreprocessor:
    """Supported Agent.create(preprocessor=) seam; filters before hydration/tools."""
    def __init__(self, room: str | None):
        from band.preprocessing.default import DefaultPreprocessor
        self.room = room
        self.default = DefaultPreprocessor()

    async def process(self, ctx, event, agent_id):
        from band.platform.event import MessageEvent
        if not self.room or not isinstance(event, MessageEvent) or event.room_id != self.room:
            return None
        if not event.payload or slash_command(event.payload.content):
            return None
        inp = await self.default.process(ctx=ctx, event=event, agent_id=agent_id)
        if inp and slash_command(inp.msg.content):
            return None
        return inp


class BudgetLedger:
    """Single supervisor owns this persistent ledger; no polling/turn count reset."""
    def __init__(self, limits: dict, path: Path, room: str, allowed_rooms: list[str] | None = None):
        self.limits, self.path = limits, path
        self.room, self.allowed_rooms = room, sorted(allowed_rooms) if allowed_rooms else None
        if self.allowed_rooms and (room not in self.allowed_rooms or len(set(self.allowed_rooms)) != 2):
            raise GateError("Subscription ledger requires both distinct configured rooms and an allowed active room.")
        self.stop = asyncio.Event()
        self.semaphore = asyncio.Semaphore(int(limits["max_active_seats"]))
        self.data = json.loads(path.read_text()) if path.exists() else {"room_id": None if self.allowed_rooms else room, "room_ids": self.allowed_rooms, "started_epoch": None if self.allowed_rooms else time.time(), "turns": {}, "tokens": 0, "token_threads": {}, "stopped_reason": None}
        if self.allowed_rooms and self.data.get("room_ids") != self.allowed_rooms:
            raise GateError("Subscription ledger room scope changed; reconcile consumption before authorizing a new session.")
        if not self.allowed_rooms and self.data["room_id"] != room:
            raise GateError("Budget ledger belongs to another room; select a new runs directory.")
        self.save()

    def save(self):
        self.data["updated_at"] = timestamp()
        save_json(self.path, self.data)

    def reason(self, seat: str | None = None) -> str | None:
        if self.data.get("stopped_reason"):
            return self.data["stopped_reason"]
        if self.allowed_rooms and self.data.get("room_stopped_reasons", {}).get(self.room):
            return self.data["room_stopped_reasons"][self.room]
        elapsed = time.time() - self.data["started_epoch"] if self.data["started_epoch"] is not None else 0
        if elapsed >= self.limits["overall_timeout_seconds"]:
            return "overall time budget exhausted"
        stage_started = self.data.get("room_started_epochs", {}).get(self.room) if self.allowed_rooms else self.data["started_epoch"]
        stage_elapsed = time.time() - stage_started if stage_started is not None else 0
        if stage_elapsed >= self.limits["stage_timeout_seconds"]:
            return "conservative whole-session stage time budget exhausted"
        if self.data["tokens"] >= self.limits["max_total_tokens"]:
            return "observed token budget exhausted"
        if seat and self.data["turns"].get(seat, 0) >= self.limits["max_turns_per_seat"]:
            return f"turn budget exhausted for {seat}"
        return None

    def reserve(self, seat: str) -> bool:
        if self.reason(seat):
            return False
        if self.data["started_epoch"] is None:
            self.data["started_epoch"] = time.time()
        self.data["turns"][seat] = self.data["turns"].get(seat, 0) + 1
        if self.allowed_rooms:
            self.data.setdefault("room_started_epochs", {}).setdefault(self.room, time.time())
            scoped = self.data.setdefault("room_turns", {}).setdefault(self.room, {})
            scoped[seat] = scoped.get(seat, 0) + 1
        self.save()
        return True

    def record(self, seat: str, metadata: dict):
        # Codex task metadata has cumulative counters. Account deltas once per
        # thread, ignoring duplicate lifecycle/usage events and restart replay.
        thread = metadata.get("codex_thread_id")
        total = metadata.get("codex_total_tokens")
        if thread and isinstance(total, int) and total >= 0:
            key = (self.room + ":" if self.allowed_rooms else "") + seat + ":" + thread
            previous = self.data["token_threads"].get(key, 0)
            self.data["tokens"] += max(0, total - previous)
            self.data["token_threads"][key] = max(previous, total)
            self.save()
            if self.reason():
                self.halt(self.reason())

    def halt(self, reason: str):
        if self.allowed_rooms and reason == "conservative whole-session stage time budget exhausted":
            self.data.setdefault("room_stopped_reasons", {})[self.room] = reason
        else:
            self.data["stopped_reason"] = reason
        self.save()
        self.stop.set()


def session_ledger(config: dict, mode: str) -> BudgetLedger:
    """Subscription caps are shared across rehearsal and judged sessions."""
    room = config["band"][f"{mode}_room_id"]
    if subscription_only(config["budgets"]):
        if any((state_dir(config) / f"budget-{other}.json").exists() for other in ("rehearsal", "judged")):
            raise GateError("Existing per-mode ledgers require explicit consumption reconciliation before subscription-only work.")
        rooms = [config["band"][f"{other}_room_id"] for other in ("rehearsal", "judged")]
        return BudgetLedger(config["budgets"], state_dir(config) / "budget-subscription.json", room, allowed_rooms=rooms)
    return BudgetLedger(config["budgets"], state_dir(config) / f"budget-{mode}.json", room)


class AuditedTools:
    """SDK-supported tools wrapper. Suppresses thoughts and observes task usage."""
    def __init__(self, tools, ledger: BudgetLedger, seat: str, audit_path: Path, roster: list[dict] | None = None):
        self.tools, self.ledger, self.seat, self.audit_path = tools, ledger, seat, audit_path
        self.roster = roster or []

    def __getattr__(self, name):
        return getattr(self.tools, name)

    async def add_participant(self, identifier: str, role: str = "member"):
        matched = next((s for s in self.roster if identifier in {s.get("agent_id"), s.get("handle"), "@" + str(s.get("handle", "")).lstrip("@")} ), None)
        if self.seat != "pm" or not matched or role != "member":
            raise GateError("Only PM may restore an exact frozen roster identity with member role.")
        agent_id = matched["agent_id"]
        participants = await self.tools.get_participants()
        for participant in participants:
            value = participant if isinstance(participant, dict) else participant.model_dump()
            if value.get("id") == agent_id:
                return {"id": agent_id, "name": matched["display_name"], "role": "member", "status": "already_in_room"}
        attempts = self.ledger.data.setdefault("membership_attempts", {})
        if attempts.get(agent_id, 0) >= min(2, self.ledger.limits["max_repairs"]):
            raise GateError("Bounded membership recovery is exhausted for this configured peer.")
        attempts[agent_id] = attempts.get(agent_id, 0) + 1
        self.ledger.save()
        return await self.tools.add_participant(agent_id, role="member")

    async def send_event(self, content, message_type, metadata=None):
        if message_type == "thought":
            return None
        metadata = metadata or {}
        self.ledger.record(self.seat, metadata)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a") as output:
            # Only structured execution data, never message content or thoughts.
            safe = {k: v for k, v in metadata.items() if k in {"codex_event_type", "codex_thread_id", "codex_turn_id", "codex_room_id", "codex_turn_status", "codex_duration_s", "codex_total_tokens", "codex_input_tokens", "codex_output_tokens", "codex_reasoning_tokens", "codex_turn_total_tokens", "band_usage"}}
            output.write(json.dumps({"at": timestamp(), "seat": self.seat, "type": message_type, "metadata": safe}) + "\n")
        return await self.tools.send_event(content=content, message_type=message_type, metadata=metadata)


async def probe_registration(config: dict, mode: str) -> dict:
    from band import Agent
    from band.core import SimpleAdapter
    from band.runtime.types import AgentConfig, SessionConfig
    class SilentAdapter(SimpleAdapter[list]):
        async def on_message(self, *args, **kwargs):
            return None
    creds = credentials(config)
    room = config["band"].get(f"{mode}_room_id")
    if not room:
        raise GateError(f"Set band.{mode}_room_id before a membership probe.")
    report = {"checked_at": timestamp(), "config_sha256": fingerprint(config), "room_id": room, "mode": mode, "verified": True, "seats": []}
    for seat in config["seats"]:
        value = creds[seat["id"]]
        agent = Agent.create(adapter=SilentAdapter(), agent_id=value["agent_id"], api_key=value["api_key"], rest_url=config["band"]["rest_url"], ws_url=config["band"]["ws_url"], config=AgentConfig(auto_subscribe_existing_rooms=False), session_config=SessionConfig(enable_working_state=False), preprocessor=RoomPreprocessor(None))
        try:
            async with asyncio.timeout(45):
                await agent.start()
                me = (await agent.runtime.link.rest.agent_api_identity.get_agent_me()).data
                participants = (await agent.runtime.link.rest.agent_api_participants.list_agent_chat_participants(chat_id=room)).data
                found = next((p for p in participants if p.id == me.id), None)
                verified = bool(found and found.handle and found.handle == me.handle and me.id == seat.get("agent_id") and me.handle.lstrip("@") == str(seat.get("handle", "")).lstrip("@") and me.name == seat["display_name"])
                report["seats"].append({"seat": seat["id"], "agent_id": me.id, "name": agent.agent_name, "handle": me.handle, "room_member": bool(found), "matches_config": verified})
                report["verified"] = report["verified"] and verified
        finally:
            await agent.stop(timeout=0)
    return report


def cmd_probe(args) -> int:
    config = get_config(args)
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        report = asyncio.run(probe_registration(config, args.mode))
    finally:
        logging.disable(previous)
    save_json(state_dir(config) / f"registration-{args.mode}.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["verified"] else 2


def process_identity(process: psutil.Process) -> dict:
    return {"pid": process.pid, "created": process.create_time(), "cmdline": process.cmdline()}


def is_owned(identity: dict, token: str | None = None) -> bool:
    try:
        process = psutil.Process(identity["pid"])
        if abs(process.create_time() - identity["created"]) > 0.001:
            return False
        command = process.cmdline()
        if command != identity["cmdline"]:
            return False
        if token is not None and ("factorykit.runtime" not in command or "_serve" not in command or "--owner-token" not in command or token not in command):
            return False
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.Error, KeyError, TypeError):
        return False


def registry_path(config):
    return state_dir(config) / "owner.json"


def read_registry(config):
    path = registry_path(config)
    return json.loads(path.read_text()) if path.is_file() else {}


@contextlib.contextmanager
def launch_lock(config):
    import fcntl
    path = state_dir(config) / "launch.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def require_ready(config, mode):
    errors = preflight_runtime(config, mode)
    for seat in config["seats"]:
        if not room_workspace(config, seat, mode).is_dir():
            errors.append(f"Prepare worktree for {seat['id']}: {room_workspace(config, seat, mode)}")
    if mode == "judged":
        errors.extend(judged_launch_errors(config))
    if errors:
        raise GateError("; ".join(errors))


def judged_launch_errors(config: dict) -> list[str]:
    """Connect judged seats only against the exact ready frozen launch."""
    from .common import canonical, digest, verify_sources
    from .tasks import verify_tasks
    from .operations import pristine_result
    errors = []
    freeze = Path(config["paths"]["runs"]) / "freeze/latest.json"
    if not freeze.is_file():
        return ["Judged start requires a READY_TO_LAUNCH freeze."]
    frozen = json.loads(freeze.read_text())
    if frozen.get("status") != "READY_TO_LAUNCH":
        errors.append("Judged start requires a READY_TO_LAUNCH freeze.")
    if frozen.get("configuration_sha256") != digest(canonical(config)):
        errors.append("Configuration changed after freeze.")
    root = Path(config["paths"]["factory"]).resolve()
    for name, expected in frozen.get("files", {}).items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or digest(path) != expected:
            errors.append(f"Frozen input changed: {name}")
    errors.extend(verify_sources(config))
    try:
        tasks = verify_tasks(config)
        if tasks["tasks"] != frozen.get("tasks"):
            errors.append("Generated task packet changed after freeze.")
    except Exception:
        errors.append("Cannot verify exact frozen task packet.")
    launch_path = Path(config["paths"]["runs"]) / "launch/ledger.json"
    launch = json.loads(launch_path.read_text()) if launch_path.is_file() else {}
    dispatched = [e for e in launch.get("entries", []) if e.get("state") in {"DISPATCHED", "ACCEPTED"} and e.get("room_event") and e.get("freeze_sha256") == digest(freeze)]
    if not dispatched:
        errors.extend(pristine_result(config))
    return errors


def cmd_start(args) -> int:
    config = get_config(args)
    require_ready(config, args.mode)
    with launch_lock(config):
        old = read_registry(config)
        if old and is_owned(old.get("parent", {}), old.get("token")):
            raise GateError("Factory supervisor is already running; use seat-status.")
        if old and any(is_owned(p) for p in old.get("children", [])):
            raise GateError("Owned child processes remain from previous supervisor; use stop-seats first.")
        token = secrets.token_hex(24)
        command = [config["runtime"]["python"], "-m", "factorykit.runtime", "--config", str(Path(args.config).resolve()), "_serve", "--mode", args.mode, "--owner-token", token]
        logfile = state_dir(config) / "supervisor.log"
        with logfile.open("ab") as output:
            child = subprocess.Popen(command, cwd=config["paths"]["factory"], stdout=output, stderr=output, start_new_session=True)
        record = {"token": token, "parent": process_identity(psutil.Process(child.pid)), "children": [], "mode": args.mode, "started_at": timestamp(), "config_sha256": fingerprint(config), "log": str(logfile)}
        save_json(registry_path(config), record)
    # Read local ready-state handshake; PID existence alone is never success.
    deadline = time.monotonic() + min(45 * len(config["seats"]) + 10, config["budgets"]["overall_timeout_seconds"])
    while time.monotonic() < deadline:
        if not is_owned(record["parent"], token):
            raise GateError("Supervisor exited before all seats connected; consult sanitized supervisor status.")
        current = read_registry(config)
        if current.get("token") == token and current.get("status") == "running":
            print(json.dumps({"status": "running", "pid": child.pid, "mode": args.mode, "seats": current.get("seats"), "active_turn_limit": config["budgets"]["max_active_seats"]}, indent=2))
            return 0
        time.sleep(0.2)
    raise GateError("Supervisor startup timed out; inspect seat-status and stop-seats before retrying.")


def cmd_status(args) -> int:
    config = get_config(args)
    record = read_registry(config)
    if not record:
        print(json.dumps({"status": "not_started"}))
        return 0
    live = is_owned(record.get("parent", {}), record.get("token"))
    result = {"status": record.get("status", "starting") if live else "stopped", "owned_parent_alive": live, "pid": record.get("parent", {}).get("pid"), "mode": record.get("mode"), "seats": record.get("seats", []), "owned_children_alive": sum(is_owned(p) for p in record.get("children", [])), "updated_at": record.get("updated_at"), "last_error": record.get("last_error")}
    ledger = state_dir(config) / ("budget-subscription.json" if subscription_only(config["budgets"]) else f"budget-{record.get('mode')}.json")
    if ledger.exists():
        data = json.loads(ledger.read_text())
        result["budget"] = {k: data.get(k) for k in ["tokens", "turns", "stopped_reason", "started_epoch", "room_ids", "room_started_epochs", "room_turns", "room_stopped_reasons"]}
    print(json.dumps(result, indent=2))
    return 0


def cmd_stop(args) -> int:
    config = get_config(args)
    with launch_lock(config):
        record = read_registry(config)
        if not record:
            print(json.dumps({"status": "not_started", "signaled": []}))
            return 0
        signaled = []
        parent = record.get("parent", {})
        if is_owned(parent, record.get("token")):
            # Snapshot known descendants while the verified owner is alive.
            try:
                record["children"] = [process_identity(p) for p in psutil.Process(parent["pid"]).children(recursive=True)]
            except psutil.Error:
                pass
            psutil.Process(parent["pid"]).terminate()
            signaled.append(parent["pid"])
            try:
                psutil.Process(parent["pid"]).wait(timeout=15)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                pass
        for identity in reversed(record.get("children", [])):
            if is_owned(identity):
                process = psutil.Process(identity["pid"])
                process.terminate()
                signaled.append(process.pid)
                try:
                    process.wait(timeout=2)
                except psutil.TimeoutExpired:
                    if is_owned(identity):
                        process.kill()
                except psutil.NoSuchProcess:
                    pass
        if is_owned(parent, record.get("token")):
            psutil.Process(parent["pid"]).kill()
        record["status"] = "stopped"
        record["updated_at"] = timestamp()
        save_json(registry_path(config), record)
        print(json.dumps({"status": "stopped", "signaled_owned_pids": signaled}, indent=2))
        return 0


async def serve(config: dict, mode: str, token: str):
    from band import Agent
    from band.adapters import CodexAdapter
    from band.core.types import Emit, Capability
    from band.runtime.types import SessionConfig
    require_ready(config, mode)
    room = config["band"][f"{mode}_room_id"]
    ledger = session_ledger(config, mode)
    if ledger.reason():
        raise GateError(ledger.reason())
    creds = credentials(config)
    agents = []
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, ledger.stop.set)

    class GuardedCodexAdapter(CodexAdapter):
        def __init__(self, seat):
            self.seat = seat
            excluded = ["band_remove_participant", "band_create_chatroom", "band_lookup_peers"]
            if seat["id"] != "pm":
                excluded.append("band_add_participant")
            super().__init__(config=adapter_config(config, seat, mode), emit=[Emit.TOOL_CALLS, Emit.TASK_EVENTS, Emit.USAGE], capabilities=[Capability.TASKS], exclude_tools=excluded)

        async def on_event(self, inp):
            if inp.room_id != room or slash_command(inp.msg.content):
                return
            async with ledger.semaphore:
                if not ledger.reserve(self.seat["id"]):
                    return
                wrapped = AuditedTools(inp.tools, ledger, self.seat["id"], state_dir(config) / "execution-events.jsonl", config["seats"])
                try:
                    async with asyncio.timeout(config["budgets"]["turn_timeout_seconds"] + 15):
                        await super().on_event(replace(inp, tools=wrapped))
                except TimeoutError:
                    ledger.halt("outer turn deadline exceeded")

    async def heartbeat():
        while not ledger.stop.is_set():
            record = read_registry(config)
            if record.get("token") != token:
                ledger.halt("ownership registry mismatch")
                return
            try:
                record["children"] = [process_identity(p) for p in psutil.Process().children(recursive=True)]
            except psutil.Error:
                pass
            record.update(status="running", updated_at=timestamp(), seats=[s["id"] for s in config["seats"]])
            save_json(registry_path(config), record)
            reason = ledger.reason()
            if all(ledger.reason(s["id"]) for s in config["seats"]):
                reason = reason or "all seats reached their turn budgets"
            if reason:
                ledger.halt(reason)
                return
            try:
                await asyncio.wait_for(ledger.stop.wait(), timeout=1)
            except TimeoutError:
                pass

    try:
        # Parent writes ownership registry immediately after spawn, before we connect.
        for _ in range(50):
            if read_registry(config).get("token") == token:
                break
            await asyncio.sleep(0.1)
        else:
            raise GateError("Missing matching supervisor ownership registry.")
        for seat in config["seats"]:
            value = creds[seat["id"]]
            adapter = GuardedCodexAdapter(seat)
            agent = Agent.create(adapter=adapter, agent_id=value["agent_id"], api_key=value["api_key"], rest_url=config["band"]["rest_url"], ws_url=config["band"]["ws_url"], session_config=SessionConfig(max_message_retries=1, max_cycle_seconds=config["budgets"]["turn_timeout_seconds"] + 20), preprocessor=RoomPreprocessor(room))
            agents.append(agent)
            await asyncio.wait_for(agent.start(), timeout=45)
            record = read_registry(config)
            if record.get("token") == token:
                record["children"] = [process_identity(p) for p in psutil.Process().children(recursive=True)]
                save_json(registry_path(config), record)
            if agent.agent_name != seat["display_name"]:
                raise GateError(f"Platform display name changed for {seat['id']}.")
        await heartbeat()
    finally:
        record = read_registry(config)
        if record.get("token") == token:
            try:
                record["children"] = [process_identity(p) for p in psutil.Process().children(recursive=True)]
            except psutil.Error:
                pass
            save_json(registry_path(config), record)
        await asyncio.gather(*(agent.stop(timeout=5) for agent in agents), return_exceptions=True)
        record = read_registry(config)
        if record.get("token") == token:
            record.update(status="stopped", updated_at=timestamp())
            save_json(registry_path(config), record)


def cmd_serve(args) -> int:
    # Never allow provider logs to accidentally record auth response headers/body.
    logging.disable(logging.CRITICAL)
    config = get_config(args)
    try:
        asyncio.run(serve(config, args.mode, args.owner_token))
        return 0
    except Exception as error:
        record = read_registry(config)
        if record.get("token") == args.owner_token:
            record.update(status="failed", last_error={"type": type(error).__name__, "detail": str(error) if isinstance(error, GateError) else "Provider failure; inspect credentials/connectivity without printing secrets."}, updated_at=timestamp())
            save_json(registry_path(config), record)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
