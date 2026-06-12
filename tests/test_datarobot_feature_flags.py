import json
from io import BytesIO
from pathlib import Path
from unittest import mock

from extensions.datarobot_feature_flags import is_datarobot_feature_flag_enabled


def test_is_datarobot_feature_flag_enabled_reads_env_and_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "DATAROBOT_ENDPOINT=https://app.datarobot.com/api/v2\n"
        "DATAROBOT_API_TOKEN=token-from-env-file\n",
        encoding="utf-8",
    )
    response = BytesIO(
        json.dumps(
            {"entitlements": [{"name": "ENABLE_AGENTIC_MEMORY_API", "value": True}]}
        ).encode("utf-8")
    )

    with mock.patch("extensions.datarobot_feature_flags.request.urlopen", return_value=response):
        enabled = is_datarobot_feature_flag_enabled("ENABLE_AGENTIC_MEMORY_API", str(tmp_path))

    assert enabled is True


def test_is_datarobot_feature_flag_enabled_without_credentials(tmp_path: Path) -> None:
    assert is_datarobot_feature_flag_enabled("ENABLE_AGENTIC_MEMORY_API", str(tmp_path)) is False
