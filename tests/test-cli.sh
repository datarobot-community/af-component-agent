#!/bin/bash

cd $1

echo "DATAROBOT_API_TOKEN = secret" >> .env
echo "DATAROBOT_ENDPOINT = https://test.com/api/v2" >> .env

# Start the server, colorize output. Wait for it to start
stdbuf -oL uvx --from go-task-bin task agent:dev | awk '{print "\033[34m" $0 "\033[0m"}' &
sleep 10

# Run the CLI command with a sample user prompt
echo "Initial execution"
uvx --from go-task-bin task agent:cli -- \
    execute \
    --show_output \
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
uvx --from go-task-bin task agent:cli -- \
    execute \
    --show_output \
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

# Run the CLI command with a sample user prompt
echo "Initial execution"
uvx --from go-task-bin task agent:cli -- \
    execute \
    --show_output \
    --user_prompt '{"topic": "Artificial Intelligence"}' \
    --stream \
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

# Check the streaming returned
if cat ./agent/output.log | grep -q '"content": "streaming success"' ; then
    echo "Test passed: cli.py returned streaming success"
    else
    echo "Test failed: cli.py did not return streaming success"
    exit 1
fi
