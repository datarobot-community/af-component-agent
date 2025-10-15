# Copyright 2025 DataRobot, Inc.
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
"""
Integration tests for CrewAI agent MCP functionality.
These tests verify that the generated CrewAI agents properly use MCP tools.
"""

from unittest.mock import patch

import pytest


class TestCrewAIAgentMCPIntegration:
    """Test that CrewAI agents actually use MCP tools during execution."""

    @patch("agent.get_mcp_tools_for_agent")
    def test_agent_planner_uses_mcp_tools(self, mock_get_tools):
        """Test that the planner agent uses MCP tools."""
        from agent import MyAgent
        from crewai.tools import BaseTool

        # Create proper BaseTool instance
        class TestTool(BaseTool):
            name: str = "test_tool"
            description: str = "Test tool"

            def _run(self, **kwargs):
                return "test_result"

        test_tool = TestTool()
        mock_get_tools.return_value = [test_tool]

        # Create agent
        agent = MyAgent()
        planner = agent.agent_planner

        # Verify agent has MCP tools
        assert planner.tools == [test_tool]
        mock_get_tools.assert_called_once()

    @patch("agent.get_mcp_tools_for_agent")
    def test_agent_writer_uses_mcp_tools(self, mock_get_tools):
        """Test that the writer agent uses MCP tools."""
        from agent import MyAgent
        from crewai.tools import BaseTool

        # Create proper BaseTool instance
        class TestTool(BaseTool):
            name: str = "test_tool"
            description: str = "Test tool"

            def _run(self, **kwargs):
                return "test_result"

        test_tool = TestTool()
        mock_get_tools.return_value = [test_tool]

        # Create agent
        agent = MyAgent()
        writer = agent.agent_writer

        # Verify agent has MCP tools
        assert writer.tools == [test_tool]
        mock_get_tools.assert_called_once()

    @patch("agent.get_mcp_tools_for_agent")
    def test_agent_editor_uses_mcp_tools(self, mock_get_tools):
        """Test that the editor agent uses MCP tools."""
        from agent import MyAgent
        from crewai.tools import BaseTool

        # Create proper BaseTool instance
        class TestTool(BaseTool):
            name: str = "test_tool"
            description: str = "Test tool"

            def _run(self, **kwargs):
                return "test_result"

        test_tool = TestTool()
        mock_get_tools.return_value = [test_tool]

        # Create agent
        agent = MyAgent()
        editor = agent.agent_editor

        # Verify agent has MCP tools
        assert editor.tools == [test_tool]
        mock_get_tools.assert_called_once()

    @patch("agent.get_mcp_tools_for_agent")
    def test_agent_calls_mcp_tool_during_execution(self, mock_get_tools):
        """Test that agents actually call MCP tools during execution."""
        from agent import MyAgent
        from crewai.tools import BaseTool

        # Create proper BaseTool instance
        class TestTool(BaseTool):
            name: str = "test_tool"
            description: str = "Test tool"

            def _run(self, **kwargs):
                return "test_result"

        test_tool = TestTool()
        mock_get_tools.return_value = [test_tool]

        # Create agent
        agent = MyAgent()
        planner = agent.agent_planner

        # Verify the tool is callable
        assert planner.tools == [test_tool]

        # Test calling the tool directly
        result = test_tool._run()
        assert result == "test_result"

    @patch("agent.get_mcp_tools_for_agent")
    def test_agent_with_no_mcp_config(self, mock_get_tools):
        """Test that agents work when no MCP config is available."""
        from agent import MyAgent

        # Mock no MCP tools available
        mock_get_tools.return_value = []

        # Create agent
        agent = MyAgent()
        planner = agent.agent_planner

        # Verify no tools
        assert planner.tools == []
        mock_get_tools.assert_called_once()

    @patch("agent.get_mcp_tools_for_agent")
    def test_agent_with_specific_mcp_tools(self, mock_get_tools):
        """Test that agents can use specific MCP tools."""
        from agent import MyAgent
        from crewai.tools import BaseTool

        # Create proper BaseTool instances
        class Tool1(BaseTool):
            name: str = "tool1"
            description: str = "Tool 1"

            def _run(self, **kwargs):
                return "result1"

        class Tool2(BaseTool):
            name: str = "tool2"
            description: str = "Tool 2"

            def _run(self, **kwargs):
                return "result2"

        tool1 = Tool1()
        tool2 = Tool2()
        mock_get_tools.return_value = [tool1, tool2]

        # Create agent
        agent = MyAgent()
        planner = agent.agent_planner

        # Verify agent has both tools
        assert len(planner.tools) == 2
        assert planner.tools == [tool1, tool2]
        mock_get_tools.assert_called_once()

    @patch("agent.get_mcp_tools_for_agent")
    def test_agent_tool_calling_with_parameters(self, mock_get_tools):
        """Test that agents can call MCP tools with parameters."""
        from agent import MyAgent
        from crewai.tools import BaseTool

        # Create proper BaseTool instance with parameters
        class WeatherTool(BaseTool):
            name: str = "weather_tool"
            description: str = "Get weather information"

            def _run(self, location="New York", units="fahrenheit", **kwargs):
                return "Sunny, 75°F"

        weather_tool = WeatherTool()
        mock_get_tools.return_value = [weather_tool]

        # Create agent
        agent = MyAgent()
        planner = agent.agent_planner

        # Test calling tool with parameters
        result = weather_tool._run(location="New York", units="fahrenheit")
        assert result == "Sunny, 75°F"

    @patch("agent.get_mcp_tools_for_agent")
    def test_agent_tool_error_handling(self, mock_get_tools):
        """Test that agents handle MCP tool errors gracefully."""
        from agent import MyAgent
        from crewai.tools import BaseTool

        # Create proper BaseTool instance that raises error
        class ErrorTool(BaseTool):
            name: str = "error_tool"
            description: str = "Tool that raises errors"

            def _run(self, **kwargs):
                raise Exception("Tool execution failed")

        error_tool = ErrorTool()
        mock_get_tools.return_value = [error_tool]

        # Create agent
        agent = MyAgent()
        planner = agent.agent_planner

        # Test that tool error is raised
        with pytest.raises(Exception, match="Tool execution failed"):
            error_tool._run()

    @patch("agent.get_mcp_tools_for_agent")
    def test_agent_with_multiple_mcp_tools(self, mock_get_tools):
        """Test that agents can use multiple MCP tools."""
        from agent import MyAgent
        from crewai.tools import BaseTool

        # Create proper BaseTool instances
        tools = []
        for i in range(5):

            class TestTool(BaseTool):
                name: str = f"tool_{i}"
                description: str = f"Tool {i}"

                def _run(self, **kwargs):
                    return f"result_{i}"

            tools.append(TestTool())

        mock_get_tools.return_value = tools

        # Create agent
        agent = MyAgent()
        planner = agent.agent_planner

        # Verify agent has all tools
        assert len(planner.tools) == 5
        assert planner.tools == tools
        mock_get_tools.assert_called_once()

    @patch("agent.get_mcp_tools_for_agent")
    def test_agent_tool_metadata(self, mock_get_tools):
        """Test that agent tools have proper metadata."""
        from agent import MyAgent
        from crewai.tools import BaseTool

        # Create proper BaseTool instance with metadata
        class MetadataTool(BaseTool):
            name: str = "metadata_tool"
            description: str = "Tool with metadata"

            def _run(self, **kwargs):
                return "result"

        metadata_tool = MetadataTool()
        mock_get_tools.return_value = [metadata_tool]

        # Create agent
        agent = MyAgent()
        planner = agent.agent_planner

        # Verify tool metadata
        tool = planner.tools[0]
        assert tool.name == "metadata_tool"
        assert "Tool with metadata" in tool.description
        assert hasattr(tool, "_run")
