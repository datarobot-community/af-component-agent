# MCP Server Configuration

The agent template supports connecting to MCP (Model Context Protocol) servers to provide additional tools to your agents. You can configure MCP servers in two ways:

## Option 1: External MCP Server

For external MCP servers (like DuckDuckGo, custom servers, etc.):

```bash
export EXTERNAL_MCP_URL="http://localhost:8080/mcp"
```

## Option 2: DataRobot MCP Server

For DataRobot-deployed MCP servers using deployment ID:

```bash
export MCP_DEPLOYMENT_ID="68f6e8bfd2ad90a760d9823f"
export DATAROBOT_API_TOKEN="your-api-token"
export DATAROBOT_ENDPOINT="https://app.datarobot.com/api/v2"
```

## Runtime Parameters

When deploying to DataRobot, you can also configure MCP servers using runtime parameters:

- `EXTERNAL_MCP_URL` - For external MCP servers
- `MCP_DEPLOYMENT_ID` - For DataRobot MCP servers

## How It Works

1. **External MCP URL**: Direct connection to any MCP-compatible server
2. **DataRobot Deployment ID**: Automatically constructs the MCP URL using your DataRobot credentials
3. **Authentication**: DataRobot servers use Bearer token authentication
4. **Tool Discovery**: All available tools from the MCP server are automatically loaded into your agents

## Example Usage

```python
# The agent will automatically connect to MCP servers based on environment variables
agent = MyAgent(api_key="your-key", api_base="https://app.datarobot.com")

# MCP tools are automatically available to all agents
response = agent.invoke({
    "messages": [{"role": "user", "content": "Search for recent AI news"}]
})
```

## Configuration Details

### External MCP Server
- **Environment Variable**: `EXTERNAL_MCP_URL`
- **Format**: Full URL to MCP server endpoint
- **Authentication**: Depends on server configuration
- **Example**: `http://localhost:8080/mcp`

### DataRobot MCP Server
- **Environment Variables**: 
  - `MCP_DEPLOYMENT_ID` - The deployment ID of your DataRobot MCP server
  - `DATAROBOT_API_TOKEN` - Your DataRobot API token
  - `DATAROBOT_ENDPOINT` - Your DataRobot endpoint (e.g., `https://app.datarobot.com/api/v2`)
- **URL Construction**: Automatically builds `{DATAROBOT_ENDPOINT}/deployments/{MCP_DEPLOYMENT_ID}/directAccess/mcp`
- **Authentication**: Uses Bearer token from `DATAROBOT_API_TOKEN`

## Agent Integration

When MCP servers are configured, the tools are automatically:
- Loaded during agent initialization
- Made available to all agent roles (planner, writer, editor)
- Used transparently by the agents during execution

The agents will automatically discover and use the available MCP tools based on the context and requirements of the task.
