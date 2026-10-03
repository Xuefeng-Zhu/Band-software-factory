"""Configuration, source, runtime metadata and readiness validation."""
from __future__ import annotations

from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import tempfile

from .common import FactoryError, canonical, contains_secret, digest, run_command, utc_now, verify_sources, write_json
from .budgets import budget_blockers, subscription_auth_errors, subscription_only
from .permissions import profile_arguments

REQUIRED_OBSERVATIONS = (
    "permissions_agent_write_git", "permissions_docker_build", "permissions_browser",
    "permissions_development_network", "band_registration_room_visibility",
    "all_seat_directed_replies", "all_seat_checkout_commit_visibility",
    "toy_pm_assignment_peer_handoffs", "toy_independent_fixed_candidate_review",
    "toy_missing_peer_delayed_message", "toy_isolated_harness", "semantic_generic_instructions",
    "toy_full_room_export", "toy_offline_submission_check",
)


def runtime_permission_arguments(runtime: dict) -> list[str]:
    """Validate configured isolation and return immutable named-profile args.

    Legacy settings remain a narrow fallback only. Profile-backed adapters must
    omit both SDK sandbox fields so they cannot replace the selected profile.
    """
    if runtime.get("approval_policy") != "never":
        raise FactoryError("Runtime requires never approval policy")
    if runtime.get("allow_network", False) is not False:
        raise FactoryError("Legacy allow_network must be false or absent; network access requires an exact named permission profile")
    if "permission_profile" not in runtime:
        if "docker_host" in runtime:
            raise FactoryError("runtime.docker_host requires a named permission profile with its exact Unix socket")
        if runtime.get("sandbox") != "workspace-write":
            raise FactoryError("Runtime requires workspace-write sandbox or an explicit narrow permission_profile")
        return []
    if runtime.get("sandbox") not in (None, "workspace-write"):
        raise FactoryError("Named permission profiles cannot be combined with broader legacy sandbox settings")
    profile = runtime["permission_profile"]
    if not isinstance(profile, dict):
        raise FactoryError("runtime.permission_profile must be a mapping with name and exact domains")
    try:
        arguments = profile_arguments(**profile)
    except TypeError:
        raise FactoryError("runtime.permission_profile requires name/domains and permits only allow_local_binding/unix_sockets as optional fields") from None
    except ValueError as error:
        raise FactoryError(f"Invalid runtime.permission_profile: {error}") from None
    if "docker_host" in runtime:
        host = runtime["docker_host"]
        if not isinstance(host, str) or not host.startswith("unix:///") or host[len("unix://"):] not in profile.get("unix_sockets", ()):
            raise FactoryError("runtime.docker_host must be a Unix URI matching an exact permission_profile.unix_sockets entry")
    return arguments


def validate(config: dict, check_sources: bool = True) -> dict:
    errors, blockers = [], []
    if check_sources:
        try:
            errors.extend(verify_sources(config))
        except FactoryError as exc:
            errors.append(str(exc))
    model = config["runtime"].get("model")
    if not model:
        blockers.append("Resolve and pin a model from the authenticated runtime")
    try:
        runtime_permission_arguments(config["runtime"])
    except FactoryError as error:
        errors.append(str(error))
    paths = config["paths"]
    for seat in config["seats"]:
        name = seat["id"]
        mandate = Path(seat["mandate"])
        if not mandate.is_file():
            errors.append(f"Missing mandate for {name}")
            continue
        text = mandate.read_text()
        slug = lambda value: re.sub(r"[^a-z0-9]", "", value.lower())
        if slug(mandate.stem) != slug(seat["display_name"]):
            errors.append(f"Mandate filename does not correspond to {name}'s display name")
        if contains_secret(text):
            errors.append(f"Potential credential in mandate for {name}; value withheld")
        for field, expected in (("Harness", seat["harness"]), ("Model", seat.get("model"))):
            found = re.search(rf"(?im)^[-*_ \t]*{field}[*_ \t]*:[*_ \t]*(.+)$", text)
            if not found:
                errors.append(f"{name} mandate lacks {field}: metadata")
            elif expected and found.group(1).strip().strip("`") != expected:
                errors.append(f"{name} mandate {field}: differs from configured runtime")
        if seat.get("model") != model:
            errors.append(f"{name} model differs from pinned common runtime model")
        if not seat.get("handle") or not seat.get("agent_id") or not seat.get("registration_verified"):
            blockers.append(f"Verify actual BAND identity, handle and room visibility for {name}")
        if not seat.get("model"):
            blockers.append(f"Resolve {name}'s model metadata")
        explicit_sentinel = re.search(r"\b(?:TODO|TBD|UNRESOLVED|UNKNOWN|REPLACE_ME)\b|\{\{.+?\}\}", text)
        metadata_placeholder = re.search(
            r"(?im)^[-*_` \t]*(?:Harness|Model|BAND handle|BAND identity|Agent ID|Seat handle)[*_` \t]*:[*_` \t]*(?:TODO|TBD|UNRESOLVED|UNKNOWN|REPLACE_ME)\b",
            text,
        )
        if explicit_sentinel or metadata_placeholder:
            blockers.append(f"Resolve placeholders in {name}'s mandate")
    # Scan every standing instruction surface, not only final mandate files.
    standing = [Path(paths["factory"]) / part for part in ("mandates", "protocols", "agents")]
    suspicious = re.compile(r"\b(?:tablekeeper|pocketful|restaurant|reservations?|sqlite|typescript|vite)\b|\b(?:GET|POST|PATCH|DELETE)\s+/[a-z]", re.I)
    for directory in standing:
        for path in sorted(directory.rglob("*.md")) if directory.exists() else []:
            text = path.read_text()
            if suspicious.search(text):
                errors.append(f"Potential track-specific standing instruction: {path.name}; semantic review required")
            if contains_secret(text):
                errors.append(f"Potential credential in standing instruction: {path.name}; value withheld")
    # Run organizer vocabulary implementation from the pinned checkout.
    if Path(config["runtime"]["harness_python"]).is_file():
        script = "from harness.check import _mandates; import pathlib,json,sys; print(json.dumps(_mandates(pathlib.Path(sys.argv[1]), 'tablekeeper')))"
        check = run_command([config["runtime"]["harness_python"], "-c", script, paths["factory"]], paths["challenge"])
        if check["exit_code"]:
            errors.append("Official mandate vocabulary check could not run")
        else:
            try:
                errors.extend(json.loads(check["stdout"]))
            except ValueError:
                errors.append("Official mandate vocabulary check returned malformed output")
    else:
        blockers.append("Install pinned official harness dependencies")
    blockers.extend(budget_blockers(config["budgets"]))
    for key in ("rehearsal_room_id", "judged_room_id"):
        if not config["band"].get(key):
            blockers.append(f"Discover and configure BAND {key}")
    if not config["launch"].get("practice_mode"):
        for key in ("registration_verified", "submission_open_verified"):
            if not config["launch"].get(key):
                blockers.append(f"Verify competition {key}, or explicitly use practice mode")
    return {"created_at": utc_now(), "status": "PASS" if not errors else "FAIL",
            "errors": errors, "launch_blockers": blockers,
            "semantic_review": "Required; keyword scans alone do not establish generic mandates"}


def doctor(config: dict) -> dict:
    checks = []
    def add(name, status, evidence):
        checks.append({"id": name, "status": status, "evidence": evidence})
    add("platform", "PASS", {"system": platform.system(), "release": platform.release(), "architecture": platform.machine()})
    add("python", "PASS" if sys.version_info >= (3, 12) else "FAIL", {"version": platform.python_version(), "executable": sys.executable})
    commands = {
        "git": ["git", "--version"], "node": ["node", "--version"],
        "npm": ["npm", "--version"], "docker_cli": ["docker", "--version"],
        "docker_daemon": ["docker", "info", "--format", "{{.ServerVersion}}"],
        "codex_version": [config["runtime"]["codex_command"], "--version"],
        "codex_auth": [config["runtime"]["codex_command"], "login", "status"],
        "harness_help": [config["runtime"]["harness_python"], "-m", "harness", "--help"],
    }
    for name, argv in commands.items():
        result = run_command(argv, config["paths"]["challenge"], timeout=15)
        add(name, "PASS" if result["exit_code"] == 0 else "FAIL", result)
    if subscription_only(config["budgets"]):
        auth_errors = subscription_auth_errors(config)
        add("subscription_auth", "FAIL" if auth_errors else "PASS", auth_errors or "ChatGPT authentication verified without inference; provider costs unmeasured")
    try:
        from band.adapters import CodexAdapter, CodexAdapterConfig  # noqa: F401
        add("band_sdk", "PASS", {"version": version("band-sdk"), "adapter": "band.adapters.CodexAdapter"})
    except (ImportError, PackageNotFoundError):
        add("band_sdk", "FAIL", "Supported Codex adapter cannot be imported")
    band_cli = {name: shutil.which(name) for name in ("band", "jam")}
    add("band_cli", "PASS" if any(band_cli.values()) else "NOT_TESTED",
        {"executables": band_cli, "required": False, "note": "The supported Python SDK is the selected transport; a separate CLI is optional"})
    if platform.system() == "Darwin":
        candidates = [base / name for base in (Path("/Applications"), Path.home() / "Applications")
                      for name in ("Band Desktop.app", "BAND.app", "Band.app", "Jam.app")]
        found = sorted({str(path) for path in candidates if path.is_dir()})
        add("band_desktop", "PASS" if found else "FAIL",
            {"installed_candidates": found, "checked_paths": [str(path) for path in candidates],
             "note": "Installation availability only; account sign-in and room visibility require live verification"})
    else:
        add("band_desktop", "NOT_TESTED", "Check supported BAND Desktop installation and sign-in on this platform")
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = config["runtime"]["browser_path"]
    script = "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); page=b.new_page(); page.set_content('<title>Factory browser probe</title>'); print(page.title()); b.close(); p.stop()"
    result = run_command([config["runtime"]["harness_python"], "-c", script], config["paths"]["runs"], timeout=30, env=env)
    add("browser_launch", "PASS" if result["exit_code"] == 0 else "FAIL", result)
    for name, value in config["paths"].items():
        path = Path(value)
        add(f"path_{name}", "PASS" if path.is_dir() else "FAIL", str(path))
    # Only scratch writes in runs; result remains pristine.
    try:
        with tempfile.TemporaryDirectory(prefix="doctor-write-", dir=config["paths"]["runs"]) as path:
            probe = Path(path) / "probe.txt"
            probe.write_text("factory permission probe\n")
            result = run_command(["git", "init", "-q", str(Path(path) / "repo")], path)
        add("host_scratch_write_git", "PASS" if result["exit_code"] == 0 else "FAIL", result)
    except OSError:
        add("host_scratch_write_git", "FAIL", "Scratch write failed; no result files created")
    saved = {}
    try:
        saved = json.loads((Path(config["paths"]["runs"]) / "readiness/observations.json").read_text())
        lock_path = Path(config["paths"]["factory"]) / "config/source-lock.json"
        if saved.get("configuration_sha256") != digest(canonical(config)) or saved.get("source_lock_sha256") != digest(lock_path):
            saved = {}
    except (OSError, ValueError, AttributeError):
        saved = {}
    for check in REQUIRED_OBSERVATIONS:
        matches = [r for r in saved.get("observations", []) if isinstance(r, dict) and r.get("id") == check]
        item = matches[0] if len(matches) == 1 else {}
        status = item.get("status", "NOT_TESTED")
        evidence = item.get("evidence", [])
        verified = isinstance(evidence, list) and bool(evidence) and item.get("observed") is True and bool(item.get("observed_at")) and bool(item.get("observer"))
        for entry in evidence if isinstance(evidence, list) else []:
            path = Path(entry.get("path", "")) if isinstance(entry, dict) else Path()
            verified = verified and path.is_absolute() and path.is_file() and entry.get("sha256") == digest(path)
        if status in ("PASS", "FAIL") and verified:
            add(check, status, item)
        else:
            add(check, "NOT_TESTED", "Requires current recorded live evidence; host checks alone do not prove a seat's permission or BAND collaboration")
    report = {"created_at": utc_now(), "configuration_sha256": digest(canonical(config)), "status": "FAIL" if any(c["status"] == "FAIL" for c in checks) else "PASS",
              "checks": checks, "usage": {"measured_cost_usd": None, "status": "UNAVAILABLE"}}
    write_json(Path(config["paths"]["runs"]) / "doctor-latest.json", report)
    return report


def toy_repository_digest(config: dict) -> str:
    """Bind checked file contents and layout, including empty stages/nested Git."""
    root = Path(config["paths"]["rehearsal"])
    ignored = {"node_modules", "__pycache__", ".venv", "venv", "target", "dist"}
    entries = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[0] == ".git" or ignored.intersection(relative.parts):
            continue
        if ".git" in relative.parts and relative.name != ".git":
            continue
        if path.is_symlink():
            entries[str(relative)] = {"type": "symlink", "target": os.readlink(path)}
            # The official offline checker follows file links when reading them.
            if path.is_file():
                entries[str(relative)]["sha256"] = digest(path)
            continue
        kind = "directory" if path.is_dir() else "file" if path.is_file() else "other"
        if ".git" in relative.parts:
            # The official layout check rejects a stage's .git file OR directory;
            # bind the marker's presence/type, while ignoring its internal history.
            if relative.name == ".git":
                entries[str(relative)] = {"type": kind, "exists": path.exists()}
            continue
        entries[str(relative)] = {"type": kind}
        if path.is_file():
            entries[str(relative)]["sha256"] = digest(path)
    return digest(canonical(entries))


def _referenced_evidence(item: dict, reference: object) -> bool:
    if not isinstance(reference, dict) or reference not in item.get("evidence", []):
        return False
    path = Path(reference.get("path", ""))
    return path.is_absolute() and path.is_file() and path.stat().st_size > 0 and reference.get("sha256") == digest(path)


def _toy_export_valid(config: dict, item: dict) -> bool:
    """Check recorded provenance and shape, never synthesize a room download."""
    export = item.get("room_export", {})
    if not isinstance(export, dict):
        return False
    reference = export.get("file")
    if not _referenced_evidence(item, reference):
        return False
    expected = Path(config["paths"]["rehearsal"]) / "room.json"
    if Path(reference["path"]) != expected or export.get("room_id") != config["band"].get("rehearsal_room_id") or not export.get("room_id"):
        return False
    if (export.get("method") != "band_console_full_session" or not export.get("downloaded_at")
            or export.get("after_work_complete") is not True):
        return False
    if export.get("contents") == "credential_redaction_only":
        if not _referenced_evidence(item, export.get("redaction_incident")):
            return False
    elif export.get("contents") != "unchanged":
        return False
    room = json.loads(expected.read_text())
    messages = room.get("messages") if isinstance(room, dict) else None
    return (isinstance(room, dict) and room.get("scope", "full") == "full"
            and isinstance(messages, list) and bool(messages)
            and all(isinstance(message, dict) for message in messages))


def _toy_check_valid(config: dict, item: dict, exports: list[dict]) -> bool:
    if len(exports) != 1 or exports[0].get("status") != "PASS" or exports[0].get("observed") is not True or not _toy_export_valid(config, exports[0]):
        return False
    reference = item.get("invocation")
    if not _referenced_evidence(item, reference):
        return False
    invocation = json.loads(Path(reference["path"]).read_text())
    if not isinstance(invocation, dict):
        return False
    expected = [config["runtime"]["harness_python"], "-m", "harness", "check", config["paths"]["rehearsal"], "--track", "toy"]
    snapshot = toy_repository_digest(config)
    return (invocation.get("argv") == expected and invocation.get("cwd") == config["paths"]["challenge"]
            and type(invocation.get("exit_code")) is int and invocation["exit_code"] == 0
            and bool(invocation.get("started_at")) and bool(invocation.get("finished_at"))
            and isinstance(invocation.get("stdout"), str) and isinstance(invocation.get("stderr"), str)
            and invocation.get("repository_before_sha256") == snapshot
            and invocation.get("repository_after_sha256") == snapshot)


def observations(config: dict) -> tuple[list[dict], list[str]]:
    path = Path(config["paths"]["runs"]) / "readiness/observations.json"
    try:
        report = json.loads(path.read_text())
    except (OSError, ValueError):
        return [], [f"Observed readiness evidence missing: {name}" for name in REQUIRED_OBSERVATIONS]
    records, blockers = [], []
    lock_path = Path(config["paths"]["factory"]) / "config/source-lock.json"
    if (not isinstance(report, dict) or report.get("configuration_sha256") != digest(canonical(config))
            or not lock_path.is_file() or report.get("source_lock_sha256") != digest(lock_path)):
        return [], ["Readiness observations do not match the current configuration and source lock"]
    entries = report.get("observations", []) if isinstance(report, dict) else []
    for name in REQUIRED_OBSERVATIONS:
        match = [r for r in entries if isinstance(r, dict) and r.get("id") == name]
        valid = len(match) == 1
        item = match[0] if valid else {}
        evidence = item.get("evidence", [])
        valid = valid and item.get("status") == "PASS" and item.get("observed") is True and bool(item.get("observed_at")) and bool(item.get("observer")) and bool(evidence)
        for entry in evidence if isinstance(evidence, list) else []:
            if not isinstance(entry, dict):
                valid = False
                continue
            target = Path(entry.get("path", ""))
            valid = valid and target.is_absolute() and target.is_file() and entry.get("sha256") == digest(target) and target.stat().st_size > 0
        if not isinstance(evidence, list):
            valid = False
        if valid and name in {"toy_full_room_export", "toy_offline_submission_check"}:
            try:
                if name == "toy_full_room_export":
                    valid = _toy_export_valid(config, item)
                else:
                    exports = [entry for entry in entries if isinstance(entry, dict) and entry.get("id") == "toy_full_room_export"]
                    valid = _toy_check_valid(config, item, exports)
            except (OSError, ValueError, TypeError, KeyError):
                valid = False
        if not valid:
            blockers.append(f"Observed readiness evidence missing/invalid: {name}")
        else:
            records.append(item)
    return records, blockers
