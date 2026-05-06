import asyncio
import logging
import httpx
import structlog
from datetime import datetime

logging.getLogger("httpx").setLevel(logging.WARNING)

log = structlog.get_logger()

class StateClient:
    def __init__(
        self,
        state_service_url: str,
        timeout: float = 1.0,
        max_retries: int = 20
    ):
        self.url = state_service_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self):
        await self._client.aclose()
        log.info("state_client_closed")

    async def send_toggle_system(self, enabled: bool):
        payload = {
            "on": enabled
        }
        
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self._client.post(self.url, json=payload)
                
                if response.status_code == 200:
                    readable_time = datetime.now().strftime("%H:%M")
                    log.info("state_service_system_toggled", system_on=enabled, readable_time=readable_time, attempt=attempt)
                    return 
                
                if response.status_code >= 500:
                    log.warning("state_service_server_error", status_code=response.status_code, attempt=attempt)
                else:
                    log.warning("state_service_client_error", status_code=response.status_code, system_on=enabled)
                    return
                    
            except httpx.RequestError as e:
                log.warning("state_service_transport_error", error=str(e), attempt=attempt)
            
            if attempt < self.max_retries:
                backoff_seconds = 2 ** (attempt - 1)
                log.info("state_service_retrying", backoff_seconds=backoff_seconds, next_attempt=attempt + 1)
                await asyncio.sleep(backoff_seconds)
            else:
                log.error("state_service_failed_all_retries", system_on=enabled, total_attempts=self.max_retries)