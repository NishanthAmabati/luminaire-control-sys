"""
Pytest configuration and shared fixtures for Luminaire Control System tests.

This module provides:
- Mock Redis client fixtures
- Mock HTTP client fixtures  
- Common test data factories
- Async test support configuration
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, List, Any


# ============================================================================
# Mock Redis Client
# ============================================================================

class MockRedisClient:
    """Mock Redis client for testing without actual Redis connection."""
    
    def __init__(self):
        self._data: Dict[str, str] = {}
        self._published: List[tuple] = []
        
    async def get(self, key: str) -> str:
        return self._data.get(key)
    
    async def set(self, key: str, value: str) -> bool:
        self._data[key] = value
        return True
    
    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                deleted += 1
        return deleted
    
    async def publish(self, channel: str, message: str) -> int:
        self._published.append((channel, message))
        return 1
    
    async def ping(self) -> bool:
        return True
    
    async def close(self):
        pass
    
    def clear(self):
        """Clear all mock data."""
        self._data.clear()
        self._published.clear()
    
    def get_published_messages(self, channel: str = None) -> List[tuple]:
        """Get published messages, optionally filtered by channel."""
        if channel:
            return [(ch, msg) for ch, msg in self._published if ch == channel]
        return self._published.copy()


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client for testing."""
    return MockRedisClient()


# ============================================================================
# Mock HTTP Client
# ============================================================================

class MockHTTPResponse:
    """Mock HTTP response for testing."""
    
    def __init__(self, status_code: int = 200, json_data: Dict = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text or json.dumps(self._json_data)
    
    def json(self) -> Dict:
        return self._json_data


class MockHTTPClient:
    """Mock HTTP client for testing API calls."""
    
    def __init__(self):
        self._responses: Dict[str, MockHTTPResponse] = {}
        self._requests: List[Dict] = []
    
    def set_response(self, url: str, response: MockHTTPResponse):
        """Set a mock response for a URL."""
        self._responses[url] = response
    
    async def post(self, url: str, json: Dict = None) -> MockHTTPResponse:
        self._requests.append({"method": "POST", "url": url, "json": json})
        return self._responses.get(url, MockHTTPResponse(200, {"status": "success"}))
    
    async def get(self, url: str) -> MockHTTPResponse:
        self._requests.append({"method": "GET", "url": url})
        return self._responses.get(url, MockHTTPResponse(200, {}))
    
    def get_requests(self) -> List[Dict]:
        """Get all recorded requests."""
        return self._requests.copy()
    
    def clear(self):
        """Clear all mock data."""
        self._responses.clear()
        self._requests.clear()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_http_client():
    """Provide a mock HTTP client for testing."""
    return MockHTTPClient()


# ============================================================================
# Test Data Factories
# ============================================================================

@pytest.fixture
def timer_factory():
    """Factory for creating timer test data."""
    
    def _create_timer(on_time: str = "08:00", off_time: str = "22:00", enabled: bool = True) -> Dict:
        return {
            "on": on_time,
            "off": off_time,
            "enabled": enabled
        }
    
    return _create_timer


@pytest.fixture
def system_state_factory():
    """Factory for creating system state test data."""
    
    def _create_state(
        is_system_on: bool = True,
        auto_mode: bool = False,
        current_cct: int = 3500,
        current_intensity: int = 250,
        cw: float = 50.0,
        ww: float = 50.0
    ) -> Dict:
        return {
            "isSystemOn": is_system_on,
            "auto_mode": auto_mode,
            "current_cct": current_cct,
            "current_intensity": current_intensity,
            "cw": cw,
            "ww": ww,
            "available_scenes": [],
            "current_scene": None,
            "loaded_scene": None,
            "scheduler": {
                "status": "idle",
                "current_interval": 0,
                "total_intervals": 8640,
                "interval_progress": 0
            },
            "scene_data": {"cct": [], "intensity": []},
            "system_timers": [],
            "isTimerEnabled": False
        }
    
    return _create_state


# ============================================================================
# Time Mocking Utilities
# ============================================================================

@pytest.fixture
def mock_datetime():
    """Fixture for mocking datetime in tests."""
    
    class MockDatetime:
        def __init__(self, year=2024, month=1, day=15, hour=12, minute=0, second=0):
            self._now = datetime(year, month, day, hour, minute, second)
        
        def set_time(self, hour: int, minute: int, second: int = 0):
            """Set the mock current time."""
            self._now = self._now.replace(hour=hour, minute=minute, second=second)
        
        def set_date(self, year: int, month: int, day: int):
            """Set the mock current date."""
            self._now = self._now.replace(year=year, month=month, day=day)
        
        def now(self):
            return self._now
        
        def strftime(self, fmt: str) -> str:
            return self._now.strftime(fmt)
    
    return MockDatetime


# ============================================================================
# Assertion Helpers
# ============================================================================

def assert_timer_state(
    result: Dict,
    expected_enabled: bool,
    expected_timer_count: int = None,
    expected_status: str = "success"
):
    """Assert timer operation result matches expected state."""
    assert result.get("status") == expected_status
    assert result.get("isTimerEnabled") == expected_enabled
    if expected_timer_count is not None:
        assert len(result.get("timers", [])) == expected_timer_count


def assert_system_toggled(mock_http: MockHTTPClient, expected_state: bool):
    """Assert that system was toggled to expected state."""
    requests = mock_http.get_requests()
    toggle_requests = [r for r in requests if "toggle_system" in r["url"]]
    assert len(toggle_requests) > 0
    last_toggle = toggle_requests[-1]
    assert last_toggle["json"]["isSystemOn"] == expected_state


def assert_redis_key_exists(mock_redis: MockRedisClient, key: str):
    """Assert a Redis key exists."""
    assert key in mock_redis._data


def assert_redis_key_not_exists(mock_redis: MockRedisClient, key: str):
    """Assert a Redis key does not exist."""
    assert key not in mock_redis._data


def assert_published_to_channel(mock_redis: MockRedisClient, channel: str):
    """Assert a message was published to a channel."""
    messages = mock_redis.get_published_messages(channel)
    assert len(messages) > 0


# Export assertion helpers
__all__ = [
    'MockRedisClient',
    'MockHTTPClient', 
    'MockHTTPResponse',
    'assert_timer_state',
    'assert_system_toggled',
    'assert_redis_key_exists',
    'assert_redis_key_not_exists',
    'assert_published_to_channel'
]
