import logging
import httpx
import datetime
import pytz

# suppressing noisy httpx logs for cleaner loki dashboards
logging.getLogger("httpx").setLevel(logging.WARNING)

# using a specific name for easier filtering in grafana
log = logging.getLogger("clients.state_client")

class StateClient:
    def __init__(
        self,
        state_service_url: str,
        timeout: float = 2.0,
        timezone: str = "Asia/Kolkata" # defaulting to your local tz
    ):
        self.url = state_service_url
        self.timeout = timeout
        self.tz = pytz.timezone(timezone)
        self._client = httpx.AsyncClient(timeout=self.timeout)
        log.debug(f"state client initialized for url {self.url}")

    async def close(self):
        try:
            await self._client.aclose()
            log.info("httpx client connection closed")
        except Exception:
            log.exception("failed to close httpx client")

    async def send_toggle_system(self, enabled: bool):
        payload = {"on": enabled}
        
        # formatting time for the log message: 17:43 (ist)
        now = datetime.datetime.now(self.tz)
        readable_time = now.strftime("%H:%M")
        tz_name = now.strftime("%Z").lower()

        try:
            log.debug(f"sending power toggle {enabled} to state service")
            response = await self._client.post(self.url, json=payload)
            
            if response.status_code == 200:
                log.info(f"toggled system power to {enabled} at {readable_time} ({tz_name})")
            else:
                log.warning(f"state service returned error status {response.status_code}")
                
        except httpx.ConnectError:
            log.error(f"failed to connect to state service at {self.url}")
        except httpx.TimeoutException:
            log.warning(f"request to state service timed out after {self.timeout}s")
        except Exception:
            log.exception("unexpected error communicating with state service")