#!/usr/bin/env python
"""Detect version-floor drift between datarobot-genai's CVE overrides and this repo's template.

datarobot-genai pins CVE-safe floors for transitive deps via `[tool.uv]`
`override-dependencies` / `constraint-dependencies` in its own pyproject.toml. Those settings
are workspace-local to uv and never propagate to consumers, so every floor genai adds has to be
manually mirrored into template/{{agent_app_name}}/pyproject.toml.jinja. This script flags any
genai floor that isn't matched (or is undercut) anywhere in the rendered template text.

Sometimes a genai floor CAN'T be mirrored -- the template deliberately holds a package below
genai's floor to work around an incompatibility (see the opentelemetry family, pinned to 1.39.x).
Those intentional caps are declared as an explicit upper bound (`<`/`<=`) in the template. The
script recognizes that signal: a floor gap explained by such a cap is reported as an acknowledged
deviation (informational, exit 0), and only unexplained drift -- a package that is missing or
merely undercut with no cap -- fails the check (exit 1).

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


def template_specifiers(template_text: str) -> dict[str, list]:
    """Best-effort scan collecting every SpecifierSet per package in the template.

    A package can appear more than once (e.g. a `[project]` dependency plus a `[tool.uv]`
    override); we keep all of them so callers can reason about the effective floor and any
    intentional ceiling.
    """
    specifiers: dict[str, list] = {}
    for match in re.finditer(r'"([A-Za-z0-9][A-Za-z0-9_.\-]*(?:\[[^\]]*\])?[^"]*)"', template_text):
        try:
            req = Requirement(match.group(1))
        except ValueError:
            continue
        name = req.name.lower().replace("_", "-")
        specifiers.setdefault(name, []).append(req.specifier)
    return specifiers


def template_floor(specifier_sets: list) -> Version | None:
    """Highest `>=`/`==` lower bound declared for a package across all its specifiers."""
    floors = [
        Version(s.version)
        for spec in specifier_sets
        for s in spec
        if s.operator in (">=", "==")
    ]
    return max(floors) if floors else None


def template_caps_below(specifier_sets: list, floor: Version) -> bool:
    """True if the template pins the package such that `floor` is intentionally excluded.

    We treat a version-floor gap as a *deliberate* override (not drift to mirror) when the
    template declares an upper bound (`<`/`<=`/`==`) that genai's required floor would violate.
    You cannot accidentally cap a package below a floor genai requires, so this signals a
    conscious, documented pin (see the inline comments in the template's override-dependencies).
    """
    return any(not spec.contains(floor, prereleases=True) for spec in specifier_sets if spec)


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <path-to-genai-pyproject.toml>", file=sys.stderr)
        return 2

    genai_text = Path(sys.argv[1]).read_text()
    template_text = TEMPLATE_PATH.read_text()

    floors = genai_floors(genai_text)
    template_specs = template_specifiers(template_text)

    gaps = []
    deviations = []
    for name, floor in sorted(floors.items()):
        if name in IGNORE:
            continue
        specs = template_specs.get(name)
        ours = template_floor(specs) if specs else None
        if specs and template_caps_below(specs, floor):
            # Template deliberately pins this package below genai's floor. Surface it so it's
            # visible on every genai bump, but don't fail -- it's an acknowledged override.
            declared = ours if ours is not None else "?"
            deviations.append(
                f"  {name}: template intentionally pins >={declared} (capped below "
                f"datarobot-genai's >={floor})"
            )
        elif ours is None:
            gaps.append(f"  {name}: MISSING from template (datarobot-genai requires >={floor})")
        elif ours < floor:
            gaps.append(f"  {name}: template has >={ours}, datarobot-genai requires >={floor}")

    if deviations:
        print("Intentional CVE-floor deviations (capped below datarobot-genai; not failing):")
        print("\n".join(deviations))
        print(
            "\nEach of these is held back by an explicit upper bound in "
            "template/{{agent_app_name}}/pyproject.toml.jinja. Re-check the inline rationale there "
            "when bumping datarobot-genai; remove the cap once the underlying conflict is resolved."
        )
        if gaps:
            print()

    if gaps:
        print("CVE-floor drift detected between datarobot-genai and this repo's template:")
        print("\n".join(gaps))
        print(
            "\nMirror these floors into "
            "template/{{agent_app_name}}/pyproject.toml.jinja's [tool.uv].override-dependencies, "
            "then run: UPGRADE_LOCK=1 task update-lock-file-all"
        )
        return 1

    print("No CVE-floor drift detected." if not deviations else "No unacknowledged CVE-floor drift detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
