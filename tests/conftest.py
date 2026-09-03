import pytest
from api.main import clear_burst_rate_limits, get_resources


@pytest.fixture(autouse=True)
def reset_rate_limits_for_tests():
    clear_burst_rate_limits()
    get_resources(reload=True)
    yield
    clear_burst_rate_limits()
