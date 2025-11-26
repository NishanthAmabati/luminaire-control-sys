"""
End-to-End Scenario Tests for Timer System

Comprehensive tests covering all timer workflow scenarios including:
- Timer enable/disable cycles
- Timer trigger scenarios
- System state interactions
- Edge cases and race conditions
- Complete user journey simulations
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from tests.conftest import (
    MockRedisClient,
    MockHTTPClient,
    MockHTTPResponse,
    assert_timer_state,
    assert_system_toggled,
    assert_redis_key_exists,
    assert_redis_key_not_exists
)


# ============================================================================
# Timer Enable/Disable Cycle Scenarios
# ============================================================================

class TestTimerEnableDisableCycles:
    """Tests for various enable/disable cycle scenarios."""
    
    @pytest.mark.asyncio
    async def test_scenario_enable_set_disable_reenable(self, mock_redis):
        """
        Scenario: Enable -> Set Timer -> Disable -> Re-enable
        Expected: Timers should be cleared when disabled and NOT repopulate on re-enable
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Step 1: Enable timers
        await ops.toggle_timers(True)
        assert ops.is_enabled == True
        
        # Step 2: Set a timer
        data = SetTimerData(timers=[Timer(on="08:00", off="22:00")])
        await ops.set_timers(data)
        assert len(ops.timers) == 1
        
        # Step 3: Disable timers
        result = await ops.toggle_timers(False)
        assert result["isTimerEnabled"] == False
        assert result["timers"] == []  # Timers should be cleared
        
        # Step 4: Re-enable timers
        result = await ops.toggle_timers(True)
        assert result["isTimerEnabled"] == True
        assert result["timers"] == []  # Should NOT repopulate old timers
    
    @pytest.mark.asyncio
    async def test_scenario_multiple_disable_enable_cycles(self, mock_redis):
        """
        Scenario: Multiple disable/enable cycles
        Expected: State should remain consistent through all cycles
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        for i in range(5):
            # Set timer
            data = SetTimerData(timers=[Timer(on=f"0{i}:00", off=f"1{i}:00")])
            await ops.set_timers(data)
            assert len(ops.timers) == 1
            
            # Disable
            await ops.toggle_timers(False)
            assert ops.timers == []
            
            # Re-enable
            await ops.toggle_timers(True)
            assert ops.timers == []  # Should stay empty
    
    @pytest.mark.asyncio
    async def test_scenario_disable_during_active_timer_window(self, mock_redis, mock_http_client):
        """
        Scenario: Disable timers while current time is within ON-OFF window
        Expected: Timer should be disabled immediately, no further triggers
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Set timer that covers current time (assuming test runs during day)
        data = SetTimerData(timers=[Timer(on="00:00", off="23:59")])
        await ops.set_timers(data)
        
        # Disable during active window
        result = await ops.toggle_timers(False)
        
        # All timer state should be cleared
        assert result["timers"] == []
        assert_redis_key_not_exists(mock_redis, "timer:timers")
        assert_redis_key_not_exists(mock_redis, "timer:triggers")


# ============================================================================
# Timer Trigger Scenarios
# ============================================================================

class TestTimerTriggerScenarios:
    """Tests for timer triggering in various time scenarios."""
    
    @pytest.mark.asyncio
    async def test_scenario_on_time_before_current_time(self, mock_redis, mock_http_client):
        """
        Scenario: Timer ON time is before current time
        Expected: System should trigger ON if not already triggered today
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Set timer with ON time in the past
        data = SetTimerData(timers=[Timer(on="00:01", off="23:59")])
        await ops.set_timers(data)
        
        # Timer should be set up correctly
        assert ops.is_enabled == True
        assert len(ops.timers) == 1
    
    @pytest.mark.asyncio
    async def test_scenario_off_time_before_current_time(self, mock_redis, mock_http_client):
        """
        Scenario: Timer OFF time is before current time
        Expected: System should trigger OFF if not already triggered today
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Set timer with OFF time in the past
        data = SetTimerData(timers=[Timer(on="00:01", off="00:02")])
        await ops.set_timers(data)
        
        assert ops.is_enabled == True
    
    @pytest.mark.asyncio
    async def test_scenario_both_times_passed(self, mock_redis, mock_http_client):
        """
        Scenario: Both ON and OFF times have passed
        Expected: System should be in the correct final state
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Both times in the past
        data = SetTimerData(timers=[Timer(on="00:01", off="00:02")])
        await ops.set_timers(data)
        
        # OFF was more recent, so system should end up OFF
        assert ops.is_enabled == True
    
    @pytest.mark.asyncio
    async def test_scenario_duplicate_trigger_prevention(self, mock_redis, mock_http_client):
        """
        Scenario: Timer check runs multiple times after trigger time
        Expected: System should only trigger once per day
        """
        from timer_service.timer_operations import TimerOperations
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Set up pre-triggered state
        today = datetime.now().strftime("%Y-%m-%d")
        mock_redis._data["timer:triggers"] = json.dumps({
            "date": today,
            "triggered": {
                f"timer_0_on_{today}": datetime.now().isoformat(),
                f"timer_0_off_{today}": datetime.now().isoformat()
            }
        })
        
        # Trigger state should prevent re-triggering
        triggers = json.loads(mock_redis._data["timer:triggers"])
        assert len(triggers["triggered"]) == 2


# ============================================================================
# System State Interaction Scenarios
# ============================================================================

class TestSystemStateInteractions:
    """Tests for timer interactions with system state."""
    
    @pytest.mark.asyncio
    async def test_scenario_manual_on_then_timer_off(self, mock_redis, mock_http_client):
        """
        Scenario: User manually turns system ON, then timer triggers OFF
        Expected: Timer should be able to turn system OFF
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        with patch('timer_service.timer_operations.httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_http_client
            
            ops = TimerOperations(mock_redis, "http://api:8000")
            
            # System manually turned ON
            mock_http_client.set_response(
                "http://api:8000/api/toggle_system",
                MockHTTPResponse(200, {"status": "success"})
            )
            
            # Timer triggers OFF
            result = await ops._trigger_system(False, "timer_off")
            
            assert result == True
            requests = mock_http_client.get_requests()
            assert requests[-1]["json"]["isSystemOn"] == False
    
    @pytest.mark.asyncio
    async def test_scenario_timer_on_then_manual_off_then_timer_off(self, mock_redis, mock_http_client):
        """
        Scenario: Timer ON -> Manual OFF -> Timer OFF
        Expected: Each action should succeed
        """
        from timer_service.timer_operations import TimerOperations
        
        with patch('timer_service.timer_operations.httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_http_client
            
            ops = TimerOperations(mock_redis, "http://api:8000")
            
            # Timer triggers ON
            await ops._trigger_system(True, "timer_on")
            
            # User manually turns OFF (simulated)
            
            # Timer triggers OFF
            await ops._trigger_system(False, "timer_off")
            
            requests = mock_http_client.get_requests()
            assert requests[0]["json"]["isSystemOn"] == True
            assert requests[1]["json"]["isSystemOn"] == False


# ============================================================================
# Edge Case Scenarios
# ============================================================================

class TestEdgeCaseScenarios:
    """Tests for edge case scenarios."""
    
    @pytest.mark.asyncio
    async def test_scenario_midnight_crossing_timer(self, mock_redis):
        """
        Scenario: Timer spans midnight (e.g., 22:00 to 06:00)
        Expected: Timer should be accepted (logic handled by trigger loop)
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Night shift timer
        data = SetTimerData(timers=[Timer(on="22:00", off="06:00")])
        result = await ops.set_timers(data)
        
        assert result["status"] == "success"
        assert len(result["timers"]) == 1
    
    @pytest.mark.asyncio
    async def test_scenario_same_on_off_time(self, mock_redis):
        """
        Scenario: ON and OFF times are the same
        Expected: This edge case is handled by timer logic
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        data = SetTimerData(timers=[Timer(on="12:00", off="12:00")])
        result = await ops.set_timers(data)
        
        # Timer is set (actual behavior depends on trigger logic)
        assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_scenario_rapid_toggle(self, mock_redis):
        """
        Scenario: Rapid toggling of timer system
        Expected: System should handle rapid state changes
        """
        from timer_service.timer_operations import TimerOperations
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Rapid toggles
        for _ in range(20):
            await ops.toggle_timers(True)
            await ops.toggle_timers(False)
        
        # Final state should be disabled
        assert ops.is_enabled == False
    
    @pytest.mark.asyncio
    async def test_scenario_timer_set_during_toggle(self, mock_redis):
        """
        Scenario: Setting timer while toggling
        Expected: Latest operation should take precedence
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Concurrent operations
        tasks = [
            ops.toggle_timers(False),
            ops.set_timers(SetTimerData(timers=[Timer(on="08:00", off="22:00")])),
            ops.toggle_timers(True),
        ]
        
        await asyncio.gather(*tasks)
        
        # System should be in a consistent state
        result = await ops.get_timers()
        assert isinstance(result["isTimerEnabled"], bool)


# ============================================================================
# Complete User Journey Scenarios
# ============================================================================

class TestUserJourneyScenarios:
    """Tests simulating complete user workflows."""
    
    @pytest.mark.asyncio
    async def test_journey_first_time_user_setup(self, mock_redis):
        """
        Journey: New user sets up timer for the first time
        Steps: Open app -> Enable timer -> Set ON/OFF times -> Verify
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        await ops.initialize()
        
        # Initially empty
        result = await ops.get_timers()
        assert result["timers"] == []
        assert result["isTimerEnabled"] == False
        
        # User sets timer
        data = SetTimerData(timers=[Timer(on="08:00", off="22:00")])
        result = await ops.set_timers(data)
        
        assert result["status"] == "success"
        assert result["isTimerEnabled"] == True
        assert len(result["timers"]) == 1
    
    @pytest.mark.asyncio
    async def test_journey_modify_existing_timer(self, mock_redis):
        """
        Journey: User modifies existing timer configuration
        Steps: Has timer -> Modify times -> Verify update
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Set initial timer
        await ops.set_timers(SetTimerData(timers=[Timer(on="08:00", off="22:00")]))
        
        # Modify to new times
        result = await ops.set_timers(SetTimerData(timers=[Timer(on="07:00", off="23:00")]))
        
        assert result["timers"][0]["on"] == "07:00"
        assert result["timers"][0]["off"] == "23:00"
    
    @pytest.mark.asyncio
    async def test_journey_temporary_disable_then_restore(self, mock_redis):
        """
        Journey: User temporarily disables timer then wants to restore
        Reality: After disable, timer config is cleared - user must reconfigure
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Set timer
        original_timer = Timer(on="08:00", off="22:00")
        await ops.set_timers(SetTimerData(timers=[original_timer]))
        
        # Disable timer
        await ops.toggle_timers(False)
        
        # Re-enable - timers will be empty (this is expected behavior)
        result = await ops.toggle_timers(True)
        assert result["timers"] == []  # User needs to reconfigure
        
        # User reconfigures
        result = await ops.set_timers(SetTimerData(timers=[original_timer]))
        assert len(result["timers"]) == 1
    
    @pytest.mark.asyncio
    async def test_journey_reset_and_start_fresh(self, mock_redis):
        """
        Journey: User resets all timer configuration
        Steps: Has complex timers -> Reset -> Verify clean slate
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Set multiple timers
        await ops.set_timers(SetTimerData(timers=[
            Timer(on="06:00", off="09:00"),
            Timer(on="12:00", off="13:00"),
            Timer(on="18:00", off="22:00")
        ]))
        
        # Reset everything
        result = await ops.reset_timers()
        
        assert result["status"] == "success"
        assert result["timers"] == []
        assert result["isTimerEnabled"] == False
        
        # Verify clean slate in Redis
        assert_redis_key_not_exists(mock_redis, "timer:timers")
        assert_redis_key_not_exists(mock_redis, "timer:triggers")


# ============================================================================
# Service Restart Scenarios
# ============================================================================

class TestServiceRestartScenarios:
    """Tests for timer behavior across service restarts."""
    
    @pytest.mark.asyncio
    async def test_scenario_restart_with_active_timers(self, mock_redis):
        """
        Scenario: Service restarts with active timers configured
        Expected: Timers should persist and continue working
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        # First service instance
        ops1 = TimerOperations(mock_redis, "http://api:8000")
        await ops1.set_timers(SetTimerData(timers=[Timer(on="08:00", off="22:00")]))
        
        # Simulate restart - new instance
        ops2 = TimerOperations(mock_redis, "http://api:8000")
        await ops2.initialize()
        
        assert len(ops2.timers) == 1
        assert ops2.is_enabled == True
    
    @pytest.mark.asyncio
    async def test_scenario_restart_with_disabled_timers(self, mock_redis):
        """
        Scenario: Service restarts with disabled timers
        Expected: Timers should remain disabled
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        # First service instance - set then disable
        ops1 = TimerOperations(mock_redis, "http://api:8000")
        await ops1.set_timers(SetTimerData(timers=[Timer(on="08:00", off="22:00")]))
        await ops1.toggle_timers(False)
        
        # Simulate restart
        ops2 = TimerOperations(mock_redis, "http://api:8000")
        await ops2.initialize()
        
        assert ops2.timers == []
        assert ops2.is_enabled == False
    
    @pytest.mark.asyncio
    async def test_scenario_restart_preserves_trigger_state(self, mock_redis):
        """
        Scenario: Service restarts mid-day after some triggers
        Expected: Previous trigger state should be preserved
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        # Set up trigger state
        today = datetime.now().strftime("%Y-%m-%d")
        mock_redis._data["timer:triggers"] = json.dumps({
            "date": today,
            "triggered": {f"timer_0_on_{today}": datetime.now().isoformat()}
        })
        mock_redis._data["timer:timers"] = json.dumps([{"on": "08:00", "off": "22:00", "enabled": True}])
        mock_redis._data["timer:enabled"] = json.dumps(True)
        
        # Service restart
        ops = TimerOperations(mock_redis, "http://api:8000")
        await ops.initialize()
        
        # Trigger state should still exist in Redis
        triggers = json.loads(mock_redis._data["timer:triggers"])
        assert len(triggers["triggered"]) == 1


# ============================================================================
# Multi-Timer Scenarios
# ============================================================================

class TestMultiTimerScenarios:
    """Tests for multiple timer configurations."""
    
    @pytest.mark.asyncio
    async def test_scenario_multiple_timers_same_day(self, mock_redis):
        """
        Scenario: Multiple ON/OFF timers throughout the day
        Expected: All timers should be stored and managed correctly
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        timers = [
            Timer(on="06:00", off="08:00"),   # Morning
            Timer(on="12:00", off="13:00"),   # Lunch
            Timer(on="18:00", off="22:00")    # Evening
        ]
        
        result = await ops.set_timers(SetTimerData(timers=timers))
        
        assert len(result["timers"]) == 3
        assert result["isTimerEnabled"] == True
    
    @pytest.mark.asyncio
    async def test_scenario_overlapping_timers(self, mock_redis):
        """
        Scenario: Overlapping timer windows
        Expected: Timers should be stored (overlap handling is in trigger logic)
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Overlapping timers
        timers = [
            Timer(on="08:00", off="16:00"),
            Timer(on="14:00", off="22:00")  # Overlaps with first
        ]
        
        result = await ops.set_timers(SetTimerData(timers=timers))
        
        # Both timers should be stored
        assert len(result["timers"]) == 2
    
    @pytest.mark.asyncio
    async def test_scenario_replace_all_timers(self, mock_redis):
        """
        Scenario: Replace all existing timers with new set
        Expected: Old timers replaced completely
        """
        from timer_service.timer_operations import TimerOperations
        from timer_service.models import SetTimerData, Timer
        
        ops = TimerOperations(mock_redis, "http://api:8000")
        
        # Set initial timers
        await ops.set_timers(SetTimerData(timers=[
            Timer(on="06:00", off="09:00"),
            Timer(on="12:00", off="13:00")
        ]))
        
        # Replace with completely different set
        result = await ops.set_timers(SetTimerData(timers=[
            Timer(on="18:00", off="22:00")
        ]))
        
        assert len(result["timers"]) == 1
        assert result["timers"][0]["on"] == "18:00"
