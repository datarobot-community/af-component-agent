#!/bin/bash

BASE_RENDER_DIR=".rendered/agent_base"
# Always smoke-test the CLI against the base agent:
# - LangGraph calls ChatLiteLLM, which would try to reach a real endpoint.
# - This script only verifies the CLI plumbing (dev server + CLI command), which is identical for all agents.
#   Rendering the base template keeps the test self-contained and deterministic.

cleanup() {
    if [ -n "${SERVER_PID:-}" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        pkill -TERM -P "$SERVER_PID" >/dev/null 2>&1 || true
        kill -TERM "$SERVER_PID" >/dev/null 2>&1 || true
        sleep 1
        pkill -KILL -P "$SERVER_PID" >/dev/null 2>&1 || true
        kill -KILL "$SERVER_PID" >/dev/null 2>&1 || true
        wait "$SERVER_PID" >/dev/null 2>&1 || true
    fi
}

wait_for_port() {
    local host="$1"
    local port="$2"
    local retries="${3:-60}"
    local delay="${4:-1}"

    for ((i = 1; i <= retries; i++)); do
        python - <<'PY' "$host" "$port" >/dev/null 2>&1 && return 0
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

s = socket.socket()
s.settimeout(1.0)
try:
    s.connect((host, port))
except OSError:
    sys.exit(1)
else:
    s.close()
PY
        sleep "$delay"
    done

    return 1
}

trap cleanup EXIT

if [ ! -d "${BASE_RENDER_DIR}/agent" ]; then
    echo "Rendering base agent for CLI smoke test"
    uvx --from go-task-bin task render-template AGENT=base
fi

if [ -n "$1" ] && [ "$1" != "$BASE_RENDER_DIR" ]; then
    echo "⚠️  tests/test-cli.sh always runs against ${BASE_RENDER_DIR}; ignoring '$1'"
fi

cd "${BASE_RENDER_DIR}"

echo "DATAROBOT_API_TOKEN = secret" >> .env
echo "DATAROBOT_ENDPOINT = https://test.com/api/v2" >> .env

# Run the CLI command with a sample user prompt
echo "Initial execution"
uvx --from go-task-bin task agent_test:agent:cli -- \
    execute \
    --user_prompt '{"topic": "Artificial Intelligence"}' \
    > ./agent/output.log 2>&1
cat ./agent/output.log

# Check if the log file was created
if [ $(wc -l < ./agent/output.log) -ge 13 ] ; then
    echo "Log file created successfully and file not empty."
    echo ""
    echo "Contents of output.log:"
    cat ./agent/output.log
    else
    echo "Log file was not created."
    exit 1
fi

echo "-------------------------------"
echo "Printing log file for debugging:"
cat ./agent/output.log
echo "-------------------------------"

# Check the logger showed the first command
if cat ./agent/output.log | grep -q 'Running CLI execute' ; then
    echo "Test passed: cli.py returned log for starting cli"
    else
    echo "Test failed: cli.py did not return log for starting cli"
    exit 1
fi

# Check the execution result
if cat ./agent/output.log | grep -q 'Execution result:' ; then
    echo "Test passed: cli.py returned log containing execution result"
    else
    echo "Test failed: cli.py did not return log containing execution result"
    exit 1
fi

# Check the chat completion returned
if cat ./agent/output.log | grep -q '"model": "datarobot-deployed-llm"' ; then
    echo "Test passed: cli.py returned log containing chat completion"
    else
    echo "Test failed: cli.py did not return log containing chat completion"
    exit 1
fi

# Check the chat completion returned
if cat ./agent/output.log | grep -q '"content": "success"' ; then
    echo "Test passed: cli.py returned chat completion success"
    else
    echo "Test failed: cli.py did not return chat completion success"
    exit 1
fi

# Run the CLI command with a sample user prompt
echo "Initial execution"
uvx --from go-task-bin task agent_test:agent:cli -- \
    execute \
    --completion_json "example-completion.json" \
    > ./agent/output.log 2>&1
cat ./agent/output.log

# Check if the log file was created
if [ $(wc -l < ./agent/output.log) -ge 13 ] ; then
    echo "Log file created successfully and file not empty."
    echo ""
    echo "Contents of output.log:"
    cat ./agent/output.log
    else
    echo "Log file was not created."
    exit 1
fi

# Check the chat completion returned
if cat ./agent/output.log | grep -q '"content": "success"' ; then
    echo "Test passed: cli.py returned chat completion success"
    else
    echo "Test failed: cli.py did not return chat completion success"
    exit 1
fi
