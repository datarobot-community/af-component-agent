"""Collect library version information for diagnostic reporting."""

from importlib.metadata import version as _pkg_version


def get_lib_versions() -> str:
    """Return a formatted string of key library versions."""
    genai = _pkg_version("datarobot-genai")
    pydantic = _pkg_version("pydantic")
    try:
        pydantic_ai_slim = _pkg_version("pydantic-ai-slim")
    except Exception:
        pydantic_ai_slim = "not installed"
    return (
        f"datarobot-genai=={genai}, "
        f"pydantic=={pydantic}, "
        f"pydantic-ai-slim=={pydantic_ai_slim}"
    )


LIB_VERSIONS = get_lib_versions()
