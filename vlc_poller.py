import aiohttp
from base64 import b64encode


class VlcPoller:
    def __init__(self, host: str, port: int, password: str):
        self._url = f"http://{host}:{port}/requests/status.json"
        token = b64encode(f":{password}".encode()).decode()
        self._headers = {"Authorization": f"Basic {token}"}

    async def get_position(self) -> float | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self._url, headers=self._headers, timeout=aiohttp.ClientTimeout(total=1.0)) as resp:
                    data = await resp.json(content_type=None)
                    return float(data["time"])
        except Exception:
            return None
