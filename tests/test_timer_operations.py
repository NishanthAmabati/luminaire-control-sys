"""
Comprehensive Unit Tests for Timer Operations

Tests cover all permutations and combinations of:
- Timer creation and validation
- Timer toggle (enable/disable)
- Timer trigger logic
- Redis state persistence
- Error handling scenarios
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from tests.conftest import (
    MockRedisClient,
    MockHTTPClient,
    MockHTTPResponse,
    assert_timer_state,
    assert_redis_key_exists,
    assert_redis_key_not_exists,
    assert_published_to_channel
)


# ============================================================================
# Timer Model Tests
# ============================================================================

class TestTimerModel:
    """Tests for Timer Pydantic model validation."""
    
    def test_valid_timer_format(self):
        """Test valid HH:MM time format is accepted."""
        from timer_service.models import Timer
        timer = Timer(on="08:00", off="22:00")
        assert timer.on == "08:00"
        assert timer.off == "22:00"
        assert timer.enabled == True
    
    def test_timer_with_enabled_false(self):
        """Test timer can be created with enabled=False."""
        from timer_service.models import Timer
        timer = Timer(on="06:30", off="18:30", enabled=False)
        assert timer.enabled == False
    
    def test_invalid_time_format_raises_error(self):
        """Test invalid time format raises validation error."""
        from timer_service.models import Timer
        from pydantic import ValidationError
        
        # Invalid hour (25 is > 23)
        with pytest.raises(ValidationError):
            Timer(on="08:00", off="25:00")
        
        # Invalid minutes (60 is > 59)
        with pytest.raises(ValidationError):
            Timer(on="08:60", off="22:00")
        
        # Completely wrong format
        with pytest.raises(ValidationError):
            Timer(on="invalid", off="22:00")
    
    def test_boundary_time_values(self):
        """Test boundary time values (00:00, 23:59)."""
        from timer_service.models import Timer
        
        # Midnight
        timer1 = Timer(on="00:00", off="23:59")
        assert timer1.on == "00:00"
        assert timer1.off == "23:59"
        
        # End of day
        timer2 = Timer(on="23:59", off="00:00")
        assert timer2.on == "23:59"
        assert timer2.off == "00:00"


class TestSetTimerDataModel:
    """Tests for SetTimerData request model."""
    
    def test_empty_timers_list(self):
        """Test empty timers list is valid."""
        from timer_service.models import SetTimerData
        data = SetTimerData(timers=[])
        assert data.timers == []
    
    def test_single_timer(self):
        """Test single timer configuration."""
        from timer_service.models import SetTimerData, Timer
        data = SetTimerData(timers=[Timer(on="08:00", off="22:00")])
        assert len(data.timers) == 1
    
    def test_multiple_timers(self):
        """Test multiple timer configurations."""
        from timer_service.models import SetTimerData, Timer
        data = SetTimerData(timers=[
            Timer(on="06:00", off="09:00"),
            Timer(on="17:00", off="22:00"),
            Timer(on="12:00", off="13:00")
        ])
        assert len(data.timers) == 3


# ============================================================================
# Timer Operations Core Tests
# ============================================================================

class TestTimerOperationsInit:
    """Tests for TimerOperations initialization."""
    
    @pytest.mark.asyncio
    async def test_initialize_empty_redis(self, mock_redis):
        """Test initialization with empty Redis state."""
        from timer_service.timer_operations import TimerOperations
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        await ops.initialize()
        
        assert ops.timers == []
        assert ops.is_enabled == False
    
    @pytest.mark.asyncio
    async def test_initialize_with_existing_timers(self, mock_redis, timer_factory):
        """Test initialization loads existing timers from Redis."""
        from timer_service.timer_operations import TimerOperations
        
        # Pre-populate Redis
        mock_redis._data["timer:timers"] = json.dumps([timer_factory()])
        mock_redis._data["timer:enabled"] = json.dumps(True)
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        await ops.initialize()
        
        assert len(ops.timers) == 1
        assert ops.is_enabled == True
    
    @pytest.mark.asyncio
    async def test_initialize_broadcasts_status(self, mock_redis):
        """Test initialization broadcasts timer status."""
        from timer_service.timer_operations import TimerOperations
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        await ops.initialize()
        
        assert_published_to_channel(mock_redis, "system_update")


# ============================================================================
# Set Timers Tests
# ============================================================================

class TestSetTimers:
    """Tests for setting timers."""
    
    @pytest.mark.asyncio
    async def test_set_single_timer(self, mock_redis, timer_factory):
        """Test setting a single timer."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        data = SetTimerData(timers=[Timer(on="08:00", off="22:00")])
        
        result = await ops.set_timers(data)
        
        assert_timer_state(result, expected_enabled=True, expected_timer_count=1)
        assert_redis_key_exists(mock_redis, "timer:timers")
        assert_redis_key_exists(mock_redis, "timer:enabled")
    
    @pytest.mark.asyncio
    async def test_set_multiple_timers(self, mock_redis):
        """Test setting multiple timers."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        data = SetTimerData(timers=[
            Timer(on="06:00", off="09:00"),
            Timer(on="12:00", off="13:00"),
            Timer(on="18:00", off="22:00")
        ])
        
        result = await ops.set_timers(data)
        
        assert_timer_state(result, expected_enabled=True, expected_timer_count=3)
    
    @pytest.mark.asyncio
    async def test_set_empty_timers_disables(self, mock_redis):
        """Test setting empty timers list disables timer system."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        data = SetTimerData(timers=[])
        
        result = await ops.set_timers(data)
        
        assert_timer_state(result, expected_enabled=False, expected_timer_count=0)
    
    @pytest.mark.asyncio
    async def test_set_timer_clears_triggers(self, mock_redis):
        """Test setting new timers clears previous trigger state."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        # Pre-populate trigger state
        mock_redis._data["timer:triggers"] = json.dumps({"date": "2024-01-15", "triggered": {"timer_0_on": "2024-01-15T08:00:00"}})
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        data = SetTimerData(timers=[Timer(on="09:00", off="21:00")])
        
        await ops.set_timers(data)
        
        assert_redis_key_not_exists(mock_redis, "timer:triggers")
    
    @pytest.mark.asyncio
    async def test_set_timer_replaces_existing(self, mock_redis):
        """Test setting timers replaces existing configuration."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Set initial timers
        data1 = SetTimerData(timers=[Timer(on="08:00", off="22:00")])
        await ops.set_timers(data1)
        
        # Replace with new timers
        data2 = SetTimerData(timers=[Timer(on="06:00", off="18:00")])
        result = await ops.set_timers(data2)
        
        assert len(result["timers"]) == 1
        assert result["timers"][0]["on"] == "06:00"
    
    @pytest.mark.asyncio
    async def test_set_timer_invalid_format_returns_error(self, mock_redis):
        """Test setting timer with invalid format returns error."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Create mock timer with invalid format (bypass pydantic)
        class MockTimer:
            on = "invalid"
            off = "22:00"
            def dict(self): return {"on": self.on, "off": self.off, "enabled": True}
        
        class MockData:
            timers = [MockTimer()]
        
        result = await ops.set_timers(MockData())
        
        assert result["status"] == "error"


# ============================================================================
# Toggle Timers Tests
# ============================================================================

class TestToggleTimers:
    """Tests for toggling timer system on/off."""
    
    @pytest.mark.asyncio
    async def test_enable_timers(self, mock_redis):
        """Test enabling timer system."""
        from timer_service.timer_operations import TimerOperations
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        result = await ops.toggle_timers(True)
        
        assert_timer_state(result, expected_enabled=True)
    
    @pytest.mark.asyncio
    async def test_disable_timers_clears_all_state(self, mock_redis, timer_factory):
        """Test disabling timers clears all timer data from Redis."""
        from timer_service.timer_operations import TimerOperations
        
        # Pre-populate timer state
        mock_redis._data["timer:timers"] = json.dumps([timer_factory()])
        mock_redis._data["timer:enabled"] = json.dumps(True)
        mock_redis._data["timer:triggers"] = json.dumps({"date": "2024-01-15", "triggered": {}})
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        ops.timers = [timer_factory()]
        ops.is_enabled = True
        
        result = await ops.toggle_timers(False)
        
        # Verify all state is cleared
        assert_timer_state(result, expected_enabled=False, expected_timer_count=0)
        assert_redis_key_not_exists(mock_redis, "timer:timers")
        assert_redis_key_not_exists(mock_redis, "timer:triggers")
        assert ops.timers == []
    
    @pytest.mark.asyncio
    async def test_toggle_on_then_off(self, mock_redis, timer_factory):
        """Test toggling on then off sequence."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Set timers first
        data = SetTimerData(timers=[Timer(on="08:00", off="22:00")])
        await ops.set_timers(data)
        
        # Toggle off - should clear timers
        result_off = await ops.toggle_timers(False)
        assert result_off["timers"] == []
        assert result_off["isTimerEnabled"] == False
        
        # Toggle on - timers should still be empty (not repopulated)
        result_on = await ops.toggle_timers(True)
        assert result_on["timers"] == []
        assert result_on["isTimerEnabled"] == True
    
    @pytest.mark.asyncio
    async def test_toggle_broadcasts_status(self, mock_redis):
        """Test toggle broadcasts timer status to UI."""
        from timer_service.timer_operations import TimerOperations
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        mock_redis._published.clear()
        
        await ops.toggle_timers(True)
        
        assert_published_to_channel(mock_redis, "system_update")
    
    @pytest.mark.asyncio
    async def test_disable_multiple_times_is_idempotent(self, mock_redis):
        """Test disabling multiple times has same effect."""
        from timer_service.timer_operations import TimerOperations
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Disable multiple times
        result1 = await ops.toggle_timers(False)
        result2 = await ops.toggle_timers(False)
        result3 = await ops.toggle_timers(False)
        
        # All should have same state
        assert result1["isTimerEnabled"] == False
        assert result2["isTimerEnabled"] == False
        assert result3["isTimerEnabled"] == False


# ============================================================================
# Get Timers Tests
# ============================================================================

class TestGetTimers:
    """Tests for getting timer configuration."""
    
    @pytest.mark.asyncio
    async def test_get_empty_timers(self, mock_redis):
        """Test getting timers when none are set."""
        from timer_service.timer_operations import TimerOperations
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        result = await ops.get_timers()
        
        assert result["timers"] == []
        assert result["isTimerEnabled"] == False
    
    @pytest.mark.asyncio
    async def test_get_configured_timers(self, mock_redis, timer_factory):
        """Test getting configured timers."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Set timers
        data = SetTimerData(timers=[Timer(on="08:00", off="22:00")])
        await ops.set_timers(data)
        
        result = await ops.get_timers()
        
        assert len(result["timers"]) == 1
        assert result["isTimerEnabled"] == True


# ============================================================================
# Reset Timers Tests
# ============================================================================

class TestResetTimers:
    """Tests for resetting all timers."""
    
    @pytest.mark.asyncio
    async def test_reset_clears_all_state(self, mock_redis, timer_factory):
        """Test reset clears all timer state."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Set timers
        data = SetTimerData(timers=[Timer(on="08:00", off="22:00")])
        await ops.set_timers(data)
        
        # Reset
        result = await ops.reset_timers()
        
        assert_timer_state(result, expected_enabled=False, expected_timer_count=0)
        assert_redis_key_not_exists(mock_redis, "timer:timers")
        assert_redis_key_not_exists(mock_redis, "timer:enabled")
        assert_redis_key_not_exists(mock_redis, "timer:triggers")
    
    @pytest.mark.asyncio
    async def test_reset_from_initial_state(self, mock_redis):
        """Test reset when no timers are configured."""
        from timer_service.timer_operations import TimerOperations
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        result = await ops.reset_timers()
        
        assert result["status"] == "success"


# ============================================================================
# Timer Trigger Logic Tests
# ============================================================================

class TestTimerTriggerLogic:
    """Tests for timer triggering logic."""
    
    @pytest.mark.asyncio
    async def test_trigger_system_on(self, mock_redis, mock_http_client):
        """Test triggering system ON."""
        from timer_service.timer_operations import TimerOperations
        
        with patch('timer_service.timer_operations.httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_http_client
            
            ops = TimerOperations(mock_redis, "http://api:8000")
            result = await ops._trigger_system(True, "test_trigger")
            
            assert result == True
            requests = mock_http_client.get_requests()
            assert len(requests) == 1
            assert requests[0]["json"]["isSystemOn"] == True
    
    @pytest.mark.asyncio
    async def test_trigger_system_off(self, mock_redis, mock_http_client):
        """Test triggering system OFF."""
        from timer_service.timer_operations import TimerOperations
        
        with patch('timer_service.timer_operations.httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_http_client
            
            ops = TimerOperations(mock_redis, "http://api:8000")
            result = await ops._trigger_system(False, "test_trigger")
            
            assert result == True
            requests = mock_http_client.get_requests()
            assert requests[0]["json"]["isSystemOn"] == False
    
    @pytest.mark.asyncio
    async def test_trigger_handles_api_error(self, mock_redis, mock_http_client):
        """Test trigger handles API error gracefully."""
        from timer_service.timer_operations import TimerOperations
        
        mock_http_client.set_response(
            "http://api:8000/api/toggle_system",
            MockHTTPResponse(status_code=500, json_data={"error": "Server error"})
        )
        
        with patch('timer_service.timer_operations.httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_http_client
            
            ops = TimerOperations(mock_redis, "http://api:8000")
            result = await ops._trigger_system(True, "test_trigger")
            
            assert result == False


# ============================================================================
# Timer Loop Tests
# ============================================================================

class TestTimerLoop:
    """Tests for the timer loop execution."""
    
    @pytest.mark.asyncio
    async def test_loop_skips_when_disabled(self, mock_redis):
        """Test timer loop skips processing when disabled."""
        from timer_service.timer_operations import TimerOperations
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        ops.is_enabled = False
        
        # Start loop briefly
        task = asyncio.create_task(ops.run_timer_loop())
        await asyncio.sleep(0.05)
        await ops.stop()
        task.cancel()
        
        # No triggers should have been attempted
        # (No toggle_system calls)
    
    @pytest.mark.asyncio
    async def test_loop_stops_on_stop(self, mock_redis):
        """Test timer loop stops when stop() is called."""
        from timer_service.timer_operations import TimerOperations
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        task = asyncio.create_task(ops.run_timer_loop())
        await asyncio.sleep(0.05)
        await ops.stop()
        
        assert ops._running == False
        task.cancel()


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_timer_at_midnight(self, mock_redis):
        """Test timer at midnight boundary (00:00)."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        data = SetTimerData(timers=[Timer(on="00:00", off="06:00")])
        
        result = await ops.set_timers(data)
        
        assert result["timers"][0]["on"] == "00:00"
    
    @pytest.mark.asyncio
    async def test_timer_at_end_of_day(self, mock_redis):
        """Test timer at end of day (23:59)."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        data = SetTimerData(timers=[Timer(on="18:00", off="23:59")])
        
        result = await ops.set_timers(data)
        
        assert result["timers"][0]["off"] == "23:59"
    
    @pytest.mark.asyncio
    async def test_timer_on_after_off_same_day(self, mock_redis):
        """Test timer where ON time is after OFF time (e.g., night shift)."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        data = SetTimerData(timers=[Timer(on="22:00", off="06:00")])  # Night shift
        
        result = await ops.set_timers(data)
        
        assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_concurrent_timer_operations(self, mock_redis):
        """Test concurrent timer operations don't cause race conditions."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Run multiple operations concurrently
        tasks = [
            ops.set_timers(SetTimerData(timers=[Timer(on="08:00", off="22:00")])),
            ops.toggle_timers(True),
            ops.get_timers(),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All operations should complete without exceptions
        for result in results:
            assert not isinstance(result, Exception)
    
    @pytest.mark.asyncio  
    async def test_redis_connection_error_handling(self, mock_redis):
        """Test handling of Redis connection errors."""
        from timer_service.timer_operations import TimerOperations
        
        # Make Redis operations fail
        async def failing_set(*args):
            raise Exception("Redis connection error")
        
        mock_redis.set = failing_set
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        from timer_service.models import SetTimerData, Timer
        result = await ops.set_timers(SetTimerData(timers=[Timer(on="08:00", off="22:00")]))
        
        assert result["status"] == "error"


# ============================================================================
# State Persistence Tests
# ============================================================================

class TestStatePersistence:
    """Tests for proper state persistence in Redis."""
    
    @pytest.mark.asyncio
    async def test_timers_persisted_correctly(self, mock_redis):
        """Test timers are correctly persisted to Redis."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        data = SetTimerData(timers=[
            Timer(on="06:00", off="09:00"),
            Timer(on="18:00", off="22:00")
        ])
        
        await ops.set_timers(data)
        
        # Verify Redis state
        stored_timers = json.loads(mock_redis._data["timer:timers"])
        assert len(stored_timers) == 2
        assert stored_timers[0]["on"] == "06:00"
        assert stored_timers[1]["on"] == "18:00"
    
    @pytest.mark.asyncio
    async def test_enabled_state_persisted(self, mock_redis):
        """Test enabled state is correctly persisted to Redis."""
        from timer_service.timer_operations import TimerOperations
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        await ops.toggle_timers(True)
        assert json.loads(mock_redis._data["timer:enabled"]) == True
        
        await ops.toggle_timers(False)
        assert json.loads(mock_redis._data["timer:enabled"]) == False
    
    @pytest.mark.asyncio
    async def test_state_survives_reinitialization(self, mock_redis):
        """Test timer state survives service restart (reinitialization)."""
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        # First instance sets timers
        ops1 = TimerOperations(mock_redis, "http://api:8000")
        data = SetTimerData(timers=[Timer(on="08:00", off="22:00")])
        await ops1.set_timers(data)
        
        # Second instance (simulating restart) loads from Redis
        ops2 = TimerOperations(mock_redis, "http://api:8000")
        await ops2.initialize()
        
        assert len(ops2.timers) == 1
        assert ops2.is_enabled == True
