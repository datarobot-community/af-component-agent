import os
import sys

import pytest


@pytest.fixture
def tests_path():
    path = os.path.split(os.path.abspath(__file__))[0]
    return path


@pytest.fixture
def root_path(tests_path):
    path = os.path.split(tests_path)[0]
    return path


@pytest.fixture(autouse=True)
def custom_model_environment(root_path):
    sys.path.append(os.path.join(root_path, "custom_model"))
