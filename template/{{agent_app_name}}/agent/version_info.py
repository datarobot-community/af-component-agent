"""Collect library version information for diagnostic reporting."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version


def _safe_version(pkg: str) -> str:
    try:
        return _pkg_version(pkg)
    except PackageNotFoundError:
        return "n/a"


def get_lib_versions() -> str:
    """Return a formatted string of key library versions."""
    return (
        f"datarobot-genai=={_safe_version('datarobot-genai')}, "
        f"fastmcp=={_safe_version('fastmcp')}, "
        f"openai=={_safe_version('openai')}"
    )


LIB_VERSIONS = get_lib_versions()
