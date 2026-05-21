import asyncio
from typing import Any
from tapo import ApiClient


class DeviceController:
    def __init__(self, email: str, password: str):
        self._client = ApiClient(email, password)
        self._state: dict[str, dict[str, Any]] = {}

    def get_state(self, ip: str) -> dict[str, Any]:
        return self._state.get(ip, {})

    def set_state(self, ip: str, **kwargs: Any) -> None:
        if ip not in self._state:
            self._state[ip] = {}
        self._state[ip].update(kwargs)

    async def _get_l530(self, ip: str):
        return await self._client.l530(ip)

    async def _get_p100(self, ip: str):
        return await self._client.p100(ip)

    async def set_switch(self, ip: str, on: bool) -> None:
        try:
            device = await self._get_p100(ip)
            if on:
                await device.on()
            else:
                await device.off()
            self.set_state(ip, on=on)
        except Exception as e:
            print(f"WARNING: Could not reach switch {ip}: {e}")

    async def set_light(
        self,
        ip: str,
        brightness: int | None = None,
        hue: int | None = None,
        saturation: int | None = None,
        on: bool | None = None,
    ) -> None:
        try:
            device = await self._get_l530(ip)
            if on is not None:
                if on:
                    await device.on()
                else:
                    await device.off()
            if brightness is not None or hue is not None or saturation is not None:
                current = self.get_state(ip)
                b = brightness if brightness is not None else current.get("brightness", 100)
                h = hue if hue is not None else current.get("hue", 0)
                s = saturation if saturation is not None else current.get("saturation", 100)
                await device.set_hue_saturation(h, s)
                await device.set_brightness(b)
            self.set_state(
                ip,
                **({} if brightness is None else {"brightness": brightness}),
                **({} if hue is None else {"hue": hue}),
                **({} if saturation is None else {"saturation": saturation}),
                **({} if on is None else {"on": on}),
            )
        except Exception as e:
            print(f"WARNING: Could not reach light {ip}: {e}")

    async def apply_initial_state(self, ip: str, device_type: str, state: dict[str, Any]) -> None:
        on = state.get("on", True)
        if device_type == "p100":
            await self.set_switch(ip, on)
        elif device_type == "l530":
            await self.set_light(
                ip,
                brightness=state.get("brightness"),
                hue=state.get("hue"),
                saturation=state.get("saturation"),
                on=on,
            )

    async def fade(
        self,
        ip: str,
        duration: float,
        to_brightness: int | None = None,
        to_hue: int | None = None,
        to_saturation: int | None = None,
        steps: int = 20,
    ) -> None:
        current = self.get_state(ip)
        from_b = current.get("brightness", 100)
        from_h = current.get("hue", 0)
        from_s = current.get("saturation", 100)

        target_b = to_brightness if to_brightness is not None else from_b
        target_h = to_hue if to_hue is not None else from_h
        target_s = to_saturation if to_saturation is not None else from_s

        interval = duration / steps
        for i in range(1, steps + 1):
            t = i / steps
            b = round(from_b + (target_b - from_b) * t) if to_brightness is not None else None
            h = round(from_h + (target_h - from_h) * t) if to_hue is not None else None
            s = round(from_s + (target_s - from_s) * t) if to_saturation is not None else None
            await self.set_light(ip, brightness=b, hue=h, saturation=s)
            await asyncio.sleep(interval)
