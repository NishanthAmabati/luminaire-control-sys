import logging
import httpx

logging.getLogger("httpx").setLevel(logging.WARNING)

log = logging.getLogger(__name__)

class StateClient:
    def __init__(
        self,
        state_service_url: str,
        timeout: float = 1
    ):
        self.url = state_service_url
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self):
        await self._client.aclose()
        log("httpx closed")

    async def send_toggle_system(self, enabled):
        payload = {
            "on": enabled
        }
        try:
            response = await self._client.post(self.url, json=payload)
            if response.status_code == 200:
                log.info(f"toggled system power: {enabled}, at #time.time need to print timein readable format like 17 : 43 (tz)")
            else:
                log.warning(f"state servie error: {response.status_code}")
        except httpx.RequestError as e:
            log.error(f"transport error communicating with state service: {e}")
