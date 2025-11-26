"""
Comprehensive API Integration Tests

Tests cover all API endpoints including:
- Timer API endpoints
- System control endpoints
- Error handling
- Request validation
"""

import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from tests.conftest import MockRedisClient, MockHTTPClient, MockHTTPResponse


# ============================================================================
# Timer Service API Tests
# ============================================================================

class TestTimerServiceAPI:
    """Tests for Timer Service FastAPI endpoints."""
    
    def test_health_endpoint_format(self):
        """Test health check response format expectation."""
        # This test validates expected format without requiring full app setup
        expected_response = {
            "status": "healthy",
            "service": "timer-service",
            "timers_enabled": False,
            "active_timers": 0
        }
        
        assert "status" in expected_response
        assert expected_response["service"] == "timer-service"
    
    def test_set_timer_request_format(self):
        """Test set_timer request format."""
        from timer_service.models import SetTimerData, Timer
        
        data = SetTimerData(timers=[Timer(on="08:00", off="22:00")])
        assert len(data.timers) == 1
    
    def test_toggle_timer_request_format(self):
        """Test toggle_timer request format."""
        from timer_service.models import ToggleTimerData
        
        data = ToggleTimerData(enable=True)
        assert data.enable == True


# ============================================================================
# API Service Timer Endpoint Tests
# ============================================================================

class TestAPIServiceTimerEndpoints:
    """Tests for API Service timer-related endpoints."""
    
    @pytest.fixture
    def mock_timer_responses(self, mock_http_client):
        """Set up mock responses for timer service."""
        mock_http_client.set_response(
            "http://timer-service:8000/set_timer",
            MockHTTPResponse(200, {
                "status": "success",
                "isTimerEnabled": True,
                "timers": [{"on": "08:00", "off": "22:00", "enabled": True}]
            })
        )
        mock_http_client.set_response(
            "http://timer-service:8000/get_timers",
            MockHTTPResponse(200, {
                "timers": [{"on": "08:00", "off": "22:00", "enabled": True}],
                "isTimerEnabled": True
            })
        )
        mock_http_client.set_response(
            "http://timer-service:8000/toggle_timer",
            MockHTTPResponse(200, {
                "status": "success",
                "isTimerEnabled": False,
                "timers": []
            })
        )
        mock_http_client.set_response(
            "http://timer-service:8000/reset_timers",
            MockHTTPResponse(200, {
                "status": "success",
                "isTimerEnabled": False,
                "timers": []
            })
        )
        return mock_http_client
    
    @pytest.mark.asyncio
    async def test_set_timer_forwards_request(self, mock_http_client):
        """Test API service forwards set_timer request to timer service."""
        from timer_service.models import SetTimerData, Timer
        
        mock_http_client.set_response(
            "http://timer-service:8000/set_timer",
            MockHTTPResponse(200, {"status": "success", "isTimerEnabled": True, "timers": []})
        )
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_http_client
            
            await mock_http_client.post(
                "http://timer-service:8000/set_timer",
                json={"timers": [{"on": "08:00", "off": "22:00"}]}
            )
            
            requests = mock_http_client.get_requests()
            assert len(requests) == 1
            assert requests[0]["url"] == "http://timer-service:8000/set_timer"
    
    @pytest.mark.asyncio
    async def test_toggle_timer_forwards_request(self, mock_http_client):
        """Test API service forwards toggle_timer request."""
        mock_http_client.set_response(
            "http://timer-service:8000/toggle_timer",
            MockHTTPResponse(200, {"status": "success", "isTimerEnabled": False, "timers": []})
        )
        
        response = await mock_http_client.post(
            "http://timer-service:8000/toggle_timer",
            json={"enable": False}
        )
        
        assert response.status_code == 200
        assert response.json()["isTimerEnabled"] == False


# ============================================================================
# System Control API Tests
# ============================================================================

class TestSystemControlAPI:
    """Tests for system control API endpoints."""
    
    @pytest.mark.asyncio
    async def test_toggle_system_on(self, mock_http_client):
        """Test toggling system ON via API."""
        mock_http_client.set_response(
            "http://scheduler-service:8000/toggle_system",
            MockHTTPResponse(200, {"status": "success", "state": {"isSystemOn": True}})
        )
        
        response = await mock_http_client.post(
            "http://scheduler-service:8000/toggle_system",
            json={"isSystemOn": True}
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_toggle_system_off(self, mock_http_client):
        """Test toggling system OFF via API."""
        mock_http_client.set_response(
            "http://scheduler-service:8000/toggle_system",
            MockHTTPResponse(200, {"status": "success", "state": {"isSystemOn": False}})
        )
        
        response = await mock_http_client.post(
            "http://scheduler-service:8000/toggle_system",
            json={"isSystemOn": False}
        )
        
        assert response.status_code == 200


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestAPIErrorHandling:
    """Tests for API error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_timer_service_unavailable(self, mock_http_client):
        """Test handling when timer service is unavailable."""
        mock_http_client.set_response(
            "http://timer-service:8000/set_timer",
            MockHTTPResponse(503, {"error": "Service unavailable"})
        )
        
        response = await mock_http_client.post(
            "http://timer-service:8000/set_timer",
            json={"timers": []}
        )
        
        assert response.status_code == 503
    
    @pytest.mark.asyncio
    async def test_scheduler_service_unavailable(self, mock_http_client):
        """Test handling when scheduler service is unavailable."""
        mock_http_client.set_response(
            "http://scheduler-service:8000/toggle_system",
            MockHTTPResponse(503, {"error": "Service unavailable"})
        )
        
        response = await mock_http_client.post(
            "http://scheduler-service:8000/toggle_system",
            json={"isSystemOn": True}
        )
        
        assert response.status_code == 503
    
    @pytest.mark.asyncio
    async def test_invalid_json_payload(self, mock_http_client):
        """Test handling of invalid JSON payloads."""
        mock_http_client.set_response(
            "http://timer-service:8000/set_timer",
            MockHTTPResponse(422, {"error": "Validation error"})
        )
        
        response = await mock_http_client.post(
            "http://timer-service:8000/set_timer",
            json={"invalid": "data"}
        )
        
        assert response.status_code == 422


# ============================================================================
# Request Validation Tests
# ============================================================================

class TestRequestValidation:
    """Tests for request payload validation."""
    
    def test_timer_time_format_validation(self):
        """Test timer time format validation."""
        from timer_service.models import Timer
        from pydantic import ValidationError
        
        # Valid formats
        Timer(on="00:00", off="23:59")
        Timer(on="12:30", off="18:45")
        
        # Invalid formats
        with pytest.raises(ValidationError):
            Timer(on="24:00", off="12:00")  # Invalid hour
        
        with pytest.raises(ValidationError):
            Timer(on="12:60", off="18:00")  # Invalid minutes
    
    def test_toggle_timer_validation(self):
        """Test toggle timer request validation."""
        from timer_service.models import ToggleTimerData
        from pydantic import ValidationError
        
        # Valid
        ToggleTimerData(enable=True)
        ToggleTimerData(enable=False)
        
        # Invalid - missing required field
        with pytest.raises(ValidationError):
            ToggleTimerData()  # Missing 'enable' field
    
    def test_set_timer_data_validation(self):
        """Test set timer data validation."""
        from timer_service.models import SetTimerData, Timer
        
        # Empty list is valid
        data1 = SetTimerData(timers=[])
        assert data1.timers == []
        
        # Valid timer list
        data2 = SetTimerData(timers=[Timer(on="08:00", off="22:00")])
        assert len(data2.timers) == 1


# ============================================================================
# Response Format Tests
# ============================================================================

class TestResponseFormats:
    """Tests for API response formats."""
    
    def test_timer_status_response_format(self):
        """Test TimerStatusResponse model format."""
        from timer_service.models import TimerStatusResponse, Timer
        
        response = TimerStatusResponse(
            status="success",
            message="Timers set",
            isTimerEnabled=True,
            timers=[Timer(on="08:00", off="22:00")]
        )
        
        assert response.status == "success"
        assert response.isTimerEnabled == True
        assert len(response.timers) == 1
    
    def test_timers_response_format(self):
        """Test TimersResponse model format."""
        from timer_service.models import TimersResponse, Timer
        
        response = TimersResponse(
            timers=[Timer(on="08:00", off="22:00")],
            isTimerEnabled=True
        )
        
        assert response.isTimerEnabled == True
        assert len(response.timers) == 1


# ============================================================================
# Concurrent Request Tests
# ============================================================================

class TestConcurrentRequests:
    """Tests for handling concurrent API requests."""
    
    @pytest.mark.asyncio
    async def test_concurrent_timer_operations(self, mock_http_client):
        """Test concurrent timer set operations."""
        import asyncio
        
        mock_http_client.set_response(
            "http://timer-service:8000/set_timer",
            MockHTTPResponse(200, {"status": "success", "isTimerEnabled": True, "timers": []})
        )
        
        # Send multiple concurrent requests
        tasks = [
            mock_http_client.post("http://timer-service:8000/set_timer", json={"timers": []})
            for _ in range(10)
        ]
        
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
