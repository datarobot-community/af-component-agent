from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request

from copier_template_extensions import ContextHook

ENABLE_AGENTIC_MEMORY_API = "ENABLE_AGENTIC_MEMORY_API"


def _load_dotenv(dst_path: str) -> dict[str, str]:
    env_path = Path(dst_path) / ".env"
    if not env_path.is_file():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def is_datarobot_feature_flag_enabled(flag_name: str, dst_path: str = ".") -> bool:
    """Return whether a feature flag is enabled on the user's DataRobot tenant."""
    dotenv = _load_dotenv(dst_path)
    endpoint = (
        os.environ.get("DATAROBOT_ENDPOINT") or dotenv.get("DATAROBOT_ENDPOINT") or ""
    ).rstrip("/")
    token = os.environ.get("DATAROBOT_API_TOKEN") or dotenv.get("DATAROBOT_API_TOKEN") or ""
    if not endpoint or not token:
        return False

    payload = json.dumps({"entitlements": [{"name": flag_name}]}).encode("utf-8")
    req = request.Request(
        f"{endpoint}/entitlements/evaluate/",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, json.JSONDecodeError, TimeoutError, OSError):
        return False

    for item in data.get("entitlements", []):
        if item.get("name") == flag_name:
            return bool(item.get("value"))
    return False


class DataRobotFeatureFlagsContext(ContextHook):
    def hook(self, context: dict[str, Any]) -> None:
        dst_path = context.get("_copier_conf", {}).get("dst_path", ".")
        context["enable_agentic_memory_api"] = is_datarobot_feature_flag_enabled(
            ENABLE_AGENTIC_MEMORY_API, dst_path
        )
