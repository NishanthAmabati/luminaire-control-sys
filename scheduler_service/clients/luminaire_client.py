import logging
import httpx

logging.getLogger("httpx").setLevel(logging.WARNING)

log = logging.getLogger(__name__)


class LuminaireClient:
    def __init__(
        self,
        luminaire_service_url: str,
        timeout: float = 0.9,
    ):
        self.url = luminaire_service_url
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self):
        await self._client.aclose()
        log(f"httpx closed")

    async def send(self, cw: float, ww: float):
        payload = {
            "cw": cw,
            "ww": ww,
        }

        try:
            response = await self._client.post(self.url, json=payload)
            if response.status_code == 200:
                log.debug(f"successfully sent CW={cw}, WW={ww}")
            else:
                log.warning(f"luminaire service error: {response.status_code}")
        except httpx.RequestError as e:
            log.error(f"transport error communicating with luminaire service: {e}")
