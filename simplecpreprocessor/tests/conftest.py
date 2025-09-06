import os
import cProfile

import pytest

profiler = None


@pytest.fixture(scope="session", autouse=True)
def maybe_profile():
    if os.environ.get("PROFILE"):
        profiler = cProfile.Profile()
        profiler.enable()
        yield  # run all tests
        profiler.disable()
        profiler.dump_stats("profile.stats")
    else:
        yield
