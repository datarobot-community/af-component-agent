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

from datarobot_drum.drum.common import setup_otel
from datarobot_drum.drum.root_predictors.prediction_server import PredictionServer
from datarobot_drum.runtime_parameters.runtime_parameters import RuntimeParameters

from agent import Config

parser = argparse.ArgumentParser(description="Run the development server")
parser.add_argument("--autoreload", action="store_true", help="Enable autoreload")

if __name__ == "__main__":
    args = parser.parse_args()
    args.max_workers = 1

    trace_provider, metric_provider, log_provider = setup_otel(RuntimeParameters, args)

    os.environ["TARGET_NAME"] = "response"
    if args.autoreload:
        os.environ["FLASK_DEBUG"] = "1"

    config = Config()
    port = config.local_dev_port

    # Use absolute path to ensure moderation_config.yaml is found regardless of CWD
    model_path = os.path.dirname(os.path.abspath(__file__))

    print(f"Running development server on http://localhost:{port}")
    PredictionServer(
        {
            "run_language": "python",
            "target_type": "agenticworkflow",
            "deployment_config": None,
            "__custom_model_path__": model_path,
            "port": port,
        }
    ).materialize()

    if trace_provider is not None:
        trace_provider.shutdown()
    if metric_provider is not None:
        metric_provider.shutdown()
    if log_provider is not None:
        log_provider.shutdown()
