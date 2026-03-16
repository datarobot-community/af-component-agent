# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli import build_dragent_payload, cli, execute_dragent_stream, is_dragent_mode


class TestIsDRAgentMode:
    def test_default_is_false(self):
        with patch.dict(os.environ, {}, clear=True):
            assert is_dragent_mode() is False

    def test_explicit_false(self):
        with patch.dict(os.environ, {"ENABLE_DRAGENT_SERVER": "false"}):
            assert is_dragent_mode() is False

    def test_explicit_true(self):
        with patch.dict(os.environ, {"ENABLE_DRAGENT_SERVER": "true"}):
            assert is_dragent_mode() is True

    def test_case_insensitive(self):
        with patch.dict(os.environ, {"ENABLE_DRAGENT_SERVER": "True"}):
            assert is_dragent_mode() is True
        with patch.dict(os.environ, {"ENABLE_DRAGENT_SERVER": "TRUE"}):
            assert is_dragent_mode() is True


class TestBuildDRAgentPayload:
    def test_payload_structure(self):
        payload = build_dragent_payload("test prompt")
        assert "threadId" in payload
        assert "runId" in payload
        assert "messages" in payload
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][0]["content"] == "test prompt"
        assert payload["state"] == []
        assert payload["tools"] == []

    def test_unique_ids(self):
        p1 = build_dragent_payload("a")
        p2 = build_dragent_payload("b")
        assert p1["threadId"] != p2["threadId"]
        assert p1["runId"] != p2["runId"]


class TestExecuteDRAgentStream:
    @staticmethod
    def _sse_lines(payloads):
        """Convert a list of dicts into SSE-formatted lines for iter_lines()."""
        lines = []
        for p in payloads:
            lines.append(f"data: {json.dumps(p)}")
        return iter(lines)

    @staticmethod
    def _mock_stream(mock_stream, sse_lines):
        """Wire up mock httpx.stream with iter_lines returning SSE data."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_lines.return_value = sse_lines
        mock_stream.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_stream.return_value.__exit__ = MagicMock(return_value=False)

    @patch("httpx.stream")
    def test_text_message_content(self, mock_stream, capsys):
        payloads = [
            {"events": [{"type": "TEXT_MESSAGE_CONTENT", "delta": "Hello "}]},
            {"events": [{"type": "TEXT_MESSAGE_CONTENT", "delta": "world"}]},
            {"events": [{"type": "TEXT_MESSAGE_END"}]},
        ]
        self._mock_stream(mock_stream, self._sse_lines(payloads))
        execute_dragent_stream("test", "http://localhost:8842/generate/stream")
        captured = capsys.readouterr()
        assert "Hello " in captured.out
        assert "world" in captured.out

    @patch("httpx.stream")
    def test_text_message_chunk(self, mock_stream, capsys):
        payloads = [
            {"events": [{"type": "TEXT_MESSAGE_CHUNK", "delta": "chunk1"}]},
            {"events": [{"type": "TEXT_MESSAGE_CHUNK", "delta": "chunk2"}]},
            {"events": [{"type": "TEXT_MESSAGE_END"}]},
        ]
        self._mock_stream(mock_stream, self._sse_lines(payloads))
        execute_dragent_stream("test", "http://localhost:8842/generate/stream")
        captured = capsys.readouterr()
        assert "chunk1" in captured.out
        assert "chunk2" in captured.out

    @patch("httpx.stream")
    def test_run_finished(self, mock_stream, capsys):
        payloads = [{"events": [{"type": "RUN_FINISHED"}]}]
        self._mock_stream(mock_stream, self._sse_lines(payloads))
        execute_dragent_stream("test", "http://localhost:8842/generate/stream")
        captured = capsys.readouterr()
        assert "Run finished." in captured.out

    @patch("httpx.stream")
    def test_malformed_json_skipped(self, mock_stream, capsys):
        lines = iter(
            [
                "data: not-json",
                f"data: {json.dumps({'events': [{'type': 'RUN_FINISHED'}]})}",
            ]
        )
        self._mock_stream(mock_stream, lines)
        execute_dragent_stream("test", "http://localhost:8842/generate/stream")
        captured = capsys.readouterr()
        assert "Run finished." in captured.out

    @patch("httpx.stream")
    def test_non_data_lines_skipped(self, mock_stream, capsys):
        lines = iter(
            [
                "event: message",
                ": comment",
                "",
                f"data: {json.dumps({'events': [{'type': 'RUN_FINISHED'}]})}",
            ]
        )
        self._mock_stream(mock_stream, lines)
        execute_dragent_stream("test", "http://localhost:8842/generate/stream")
        captured = capsys.readouterr()
        assert "Run finished." in captured.out

    @patch("httpx.stream")
    def test_connection_error(self, mock_stream):
        import httpx  # noqa: PLC0415

        mock_stream.return_value.__enter__ = MagicMock(
            side_effect=httpx.ConnectError("refused")
        )
        mock_stream.return_value.__exit__ = MagicMock(return_value=False)
        with pytest.raises(Exception, match="Could not connect"):
            execute_dragent_stream("test", "http://localhost:8842/generate/stream")

    @patch("httpx.stream")
    def test_http_error(self, mock_stream):
        import httpx  # noqa: PLC0415

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error",
            request=MagicMock(),
            response=MagicMock(),
        )
        mock_stream.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_stream.return_value.__exit__ = MagicMock(return_value=False)
        with pytest.raises(Exception, match="HTTP error from dragent server"):
            execute_dragent_stream("test", "http://localhost:8842/generate/stream")

    @patch("httpx.stream")
    def test_sends_correct_payload(self, mock_stream):
        self._mock_stream(mock_stream, iter([]))

        execute_dragent_stream(
            "my prompt",
            "http://localhost:8842/generate/stream",
            headers={"Authorization": "Bearer tok"},
        )

        mock_stream.assert_called_once()
        call_kwargs = mock_stream.call_args
        assert call_kwargs.kwargs["json"]["messages"][0]["content"] == "my prompt"
        assert "Authorization" in call_kwargs.kwargs["headers"]


@patch.dict(
    os.environ,
    {
        "DATAROBOT_API_TOKEN": "env-api-key",
        "DATAROBOT_ENDPOINT": "https://env-api-base.com",
    },
)
class TestCliDRAgentIntegration:
    """Integration tests for CLI commands in dragent mode."""

    @patch("cli.execute_dragent_stream")
    @patch("cli.is_dragent_mode", return_value=True)
    def test_execute_dragent_mode(self, _mock_dragent, mock_stream):
        runner = CliRunner()
        result = runner.invoke(cli, ["execute", "--user_prompt", "test"])
        assert result.exit_code == 0
        mock_stream.assert_called_once()

    @patch("cli.is_dragent_mode", return_value=True)
    def test_execute_custom_model_blocked_in_dragent(self, _mock_dragent):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "execute-custom-model",
                "--user_prompt",
                "test",
                "--custom_model_id",
                "abc",
            ],
        )
        assert result.exit_code != 0
        assert "not supported in dragent mode" in result.output

    @patch("cli.execute_dragent_stream")
    @patch("cli.is_dragent_mode", return_value=True)
    def test_execute_deployment_dragent_mode(self, _mock_dragent, mock_stream):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--api_token",
                "tok123",
                "--base_url",
                "https://app.datarobot.com",
                "execute-deployment",
                "--user_prompt",
                "test",
                "--deployment_id",
                "abc123",
            ],
        )
        assert result.exit_code == 0
        mock_stream.assert_called_once()

    @patch.dict(os.environ, {"DATAROBOT_API_TOKEN": ""}, clear=False)
    @patch("cli.is_dragent_mode", return_value=True)
    def test_execute_deployment_dragent_missing_api_token(self, _mock_dragent):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--base_url",
                "https://app.datarobot.com",
                "execute-deployment",
                "--user_prompt",
                "test",
                "--deployment_id",
                "abc123",
            ],
        )
        assert result.exit_code != 0

    @patch("cli.is_dragent_mode", return_value=True)
    def test_execute_dragent_requires_prompt(self, _mock_dragent):
        runner = CliRunner()
        result = runner.invoke(cli, ["execute", "--completion_json", "some.json"])
        assert result.exit_code != 0
        assert "requires --user_prompt" in result.output
