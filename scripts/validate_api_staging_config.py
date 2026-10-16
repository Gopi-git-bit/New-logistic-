"""Validate a synthetic Compose contract and canonical settings without app startup."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

PLACEHOLDER = "NOT_A_SECRET_ONLY_FOR_OFFLINE_VALIDATION"
DATABASES = {
    "DATABASE_URL": "postgresql://validation.invalid/operational",
    "PAPERCLIP_DATABASE_URL": "postgresql://validation.invalid/governance",
}
ENV_NAMES = frozenset(
    {
        *DATABASES,
        "APP_ENV",
        "AUTH_MODE",
        "AUTH_JWT_SECRET",
        "ZIPPY_PLATFORM_ID",
        "M3_PRICING_POLICY_VERSION",
        "M3_PRICING_CURRENCY",
        "M3_PRICING_BASE_AMOUNT",
        "M3_PRICING_PER_KM",
        "M3_PRICING_PER_KG",
        "PAPERCLIP_OWNER_SUBJECT",
        "PAPERCLIP_EXECUTOR_SUBJECT",
        "PAPERCLIP_POLICY_ID",
        "PAPERCLIP_AGENT_BINDINGS_JSON",
        "PAPERCLIP_ENVELOPE_SIGNING_KEY",
        "PAPERCLIP_ENVELOPE_TTL_SECONDS",
    }
)
CONTROLS: dict[str, object] = {
    "profiles": ["validation-only"],
    "image": "zippy-api-validation:unpublished",
    "entrypoint": ["/bin/false"],
    "network_mode": "none",
    "user": "10001:10001",
    "read_only": True,
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges:true"],
    "restart": "no",
}


class ContractError(ValueError):
    """The validation-only contract is malformed or unsafe."""


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def validate_contract(path: Path, repo: Path) -> dict[str, str]:
    raw = path.read_text(encoding="utf-8")
    if len(raw) > 16384:
        raise ContractError("CONTRACT_TOO_LARGE")
    value = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(value, dict) or set(value) != {"name", "services"}:
        raise ContractError("CONTRACT_SCHEMA_REJECTED")
    if value["name"] != "zippy-api-validation":
        raise ContractError("PROJECT_NAME_REJECTED")
    services = value["services"]
    if not isinstance(services, dict) or set(services) != {"api-validation"}:
        raise ContractError("SERVICE_SET_REJECTED")
    service = services["api-validation"]
    if not isinstance(service, dict) or set(service) != {*CONTROLS, "environment"}:
        raise ContractError("SERVICE_OPTIONS_REJECTED")
    if any(type(service[k]) is not type(v) or service[k] != v for k, v in CONTROLS.items()):
        raise ContractError("SERVICE_BOUNDARY_REJECTED")
    env = service["environment"]
    if (
        not isinstance(env, dict)
        or set(env) != ENV_NAMES
        or any(not isinstance(v, str) for v in env.values())
    ):
        raise ContractError("ENVIRONMENT_NAMES_OR_TYPES_REJECTED")
    env = cast(dict[str, str], env)
    if any(env[k] != v for k, v in DATABASES.items()) or any(
        env[k] != PLACEHOLDER for k in ("AUTH_JWT_SECRET", "PAPERCLIP_ENVELOPE_SIGNING_KEY")
    ):
        raise ContractError("NON_SYNTHETIC_CONNECTION_OR_SECRET")
    if (
        env["APP_ENV"] != "test"
        or env["AUTH_MODE"] != "test_jwt"
        or not env["M3_PRICING_POLICY_VERSION"].startswith("test-delivery-")
        or any(
            env[k] != "0"
            for k in ("M3_PRICING_BASE_AMOUNT", "M3_PRICING_PER_KM", "M3_PRICING_PER_KG")
        )
        or not env["PAPERCLIP_OWNER_SUBJECT"].startswith("synthetic-")
        or not env["PAPERCLIP_EXECUTOR_SUBJECT"].startswith("synthetic-")
        or "${" in raw
    ):
        raise ContractError("NON_SYNTHETIC_SETTINGS")
    bindings = json.loads(env["PAPERCLIP_AGENT_BINDINGS_JSON"], object_pairs_hook=unique_object)
    if not isinstance(bindings, dict) or any(not k.startswith("synthetic-") for k in bindings):
        raise ContractError("NON_SYNTHETIC_BINDINGS")

    # Load this pure stdlib settings module directly: never api.main or database pools.
    config_path = repo / "api/config.py"
    module = ModuleType("_zippy_delivery_config")
    module.__file__ = str(config_path)
    old_module = sys.modules.get(module.__name__)
    old_environment = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(env)
        sys.modules[module.__name__] = module
        # Compile source bytes directly: do not load or create an untracked pyc cache.
        exec(compile(config_path.read_bytes(), str(config_path), "exec"), module.__dict__)
        module.load_settings()
    except Exception:
        raise ContractError("CANONICAL_SETTINGS_REJECTED") from None
    finally:
        os.environ.clear()
        os.environ.update(old_environment)
        if old_module is None:
            sys.modules.pop(module.__name__, None)
        else:
            sys.modules[module.__name__] = old_module
    return {
        "status": "OFFLINE_CONTRACT_VALIDATED",
        "scope": "compose_schema_and_canonical_settings_only",
        "runtime_readiness": "UNVERIFIED",
        "provider_execution": "DENIED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    path = args.manifest or args.repo_root / "infra/staging/api-validation.compose.json"
    try:
        report = validate_contract(path, args.repo_root)
    except (OSError, ValueError, TypeError):
        # Never emit a parser/settings exception containing a supplied value or document.
        print(json.dumps({"status": "OFFLINE_CONTRACT_NOT_VERIFIED"}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
