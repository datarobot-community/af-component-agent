#!/usr/bin/env python
"""Detect version-floor drift between datarobot-genai's CVE overrides and this repo's template.

datarobot-genai pins CVE-safe floors for transitive deps via `[tool.uv]`
`override-dependencies` / `constraint-dependencies` in its own pyproject.toml. Those settings
are workspace-local to uv and never propagate to consumers, so every floor genai adds has to be
manually mirrored into template/{{agent_app_name}}/pyproject.toml.jinja. This script flags any
genai floor that isn't matched (or is undercut) anywhere in the rendered template text.

This is a static text scan, not a real dependency resolution -- it will not catch every possible
drift (e.g. markers/extras nuance) and false positives are expected occasionally. Treat findings
as "go check the lockfile", not ground truth.
"""

import re
import sys
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO_ROOT / "template" / "{{agent_app_name}}" / "pyproject.toml.jinja"

# Packages whose version floor is satisfied by datarobot-genai's own [project] dependency
# declaration (which DOES propagate normally to consumers), not by its [tool.uv] overrides
# (which don't) -- so they don't need to be mirrored here even though they appear in genai's
# override-dependencies/constraint-dependencies list.
IGNORE = {"crewai"}


def genai_floors(genai_pyproject_text: str) -> dict[str, Version]:
    """Extract {package_name: minimum_version} from genai's override/constraint arrays."""
    data = tomllib.loads(genai_pyproject_text)
    uv_config = data.get("tool", {}).get("uv", {})
    specs = [*uv_config.get("override-dependencies", []), *uv_config.get("constraint-dependencies", [])]

    floors: dict[str, Version] = {}
    for spec in specs:
        try:
            req = Requirement(spec)
        except ValueError:
            continue
        floor = next((s.version for s in req.specifier if s.operator in (">=", "==")), None)
        if floor is None:
            continue
        name = req.name.lower().replace("_", "-")
        version = Version(floor)
        if name not in floors or version > floors[name]:
            floors[name] = version


    return floors


def template_max_versions(template_text: str) -> dict[str, Version]:
    """Best-effort scan for every `"<name><specifier>"` dependency string in the template."""
    versions: dict[str, Version] = {}
    for match in re.finditer(r'"([A-Za-z0-9][A-Za-z0-9_.\-]*(?:\[[^\]]*\])?[^"]*)"', template_text):
        try:
            req = Requirement(match.group(1))
        except ValueError:
            continue
        floor = next((s.version for s in req.specifier if s.operator in (">=", "==")), None)
        if floor is None:
            continue
        name = req.name.lower().replace("_", "-")
        version = Version(floor)
        if name not in versions or version > versions[name]:
            versions[name] = version
    return versions


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <path-to-genai-pyproject.toml>", file=sys.stderr)
        return 2

    genai_text = Path(sys.argv[1]).read_text()
    template_text = TEMPLATE_PATH.read_text()

    floors = genai_floors(genai_text)
    template_versions = template_max_versions(template_text)

    gaps = []
    for name, floor in sorted(floors.items()):
        if name in IGNORE:
            continue
        ours = template_versions.get(name)
        if ours is None:
            gaps.append(f"  {name}: MISSING from template (datarobot-genai requires >={floor})")
        elif ours < floor:
            gaps.append(f"  {name}: template has >={ours}, datarobot-genai requires >={floor}")

    if gaps:
        print("CVE-floor drift detected between datarobot-genai and this repo's template:")
        print("\n".join(gaps))
        print(
            "\nMirror these floors into "
            "template/{{agent_app_name}}/pyproject.toml.jinja's [tool.uv].override-dependencies, "
            "then run: UPGRADE_LOCK=1 task update-lock-file-all"
        )
        return 1

    print("No CVE-floor drift detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
