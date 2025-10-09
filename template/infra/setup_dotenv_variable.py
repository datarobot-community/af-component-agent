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
import argparse
import os
import sys
from pathlib import Path
from typing import Optional

if sys.version_info[0] < 3 or (sys.version_info[0] >= 3 and sys.version_info[1] < 10):
    print("Must be using Python version 3.10 or higher")
    exit(1)

work_dir = Path(os.path.dirname(__file__))
dot_env_file = work_dir / ".env"


def read_env_file_lines() -> list[str]:
    """Read the .env file and return all lines as a list."""
    if dot_env_file.exists():
        with open(dot_env_file) as f:
            return f.readlines()
    return []


def get_env_var_from_lines(lines: list[str], var_name: str) -> Optional[str]:
    """Extract environment variable value from the lines."""
    for line in lines:
        line = line.strip()
        if line.startswith(f"{var_name}="):
            return line.partition("=")[-1].strip()
    return None


def update_env_var_in_lines(
    lines: list[str], var_name: str, new_value: str
) -> list[str]:
    """Update or add environment variable in the lines, preserving file structure."""
    updated_lines = []
    var_found = False

    for line in lines:
        new_line = line
        if line.strip().startswith(f"{var_name}="):
            # Replace existing variable line
            new_line = f"{var_name}={new_value}\n"
            var_found = True
        updated_lines.append(new_line)

    # If variable wasn't found, append it at the end
    if not var_found:
        updated_lines.append(f"{var_name}={new_value}\n")

    return updated_lines


def write_env_file_lines(lines: list[str]) -> None:
    """Write the lines back to the .env file."""
    with open(dot_env_file, "w") as f:
        f.writelines(lines)


def prompt_for_value(prompt_message: str, default_value: Optional[str] = None) -> str:
    """Prompt the user for a value."""
    while True:
        if default_value is not None:
            print(f"{prompt_message} (default: {default_value}): ")
            value = input().strip()
            if not value:
                return default_value
            return value
        else:
            print(prompt_message)
            value = input().strip()
            if value:
                return value
            print("Value cannot be empty. Please try again.")


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Ensure an environment variable is present and non-empty in .env file"
    )
    parser.add_argument(
        "--var-name",
        help="Name of the environment variable to check/set (e.g., PULUMI_STACK)",
    )
    parser.add_argument(
        "--prompt-message", help="Message to display when prompting user for input"
    )
    parser.add_argument(
        "--default",
        default=None,
        help="Default value to use if user provides empty input",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Exit with code 1 if the .env file was updated (prompting a restart is needed)",
    )
    return parser.parse_args()


def main():
    """Main function to ensure environment variable is present and non-empty in .env file."""
    args = parse_arguments()

    lines = read_env_file_lines()
    current_value = get_env_var_from_lines(lines, args.var_name)

    if not current_value:
        new_value = prompt_for_value(args.prompt_message, args.default)
        updated_lines = update_env_var_in_lines(lines, args.var_name, new_value)
        write_env_file_lines(updated_lines)

        if args.restart:
            print(
                "Environment file was updated based on your input, "
                "please restart the command for the changes to take effect."
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
