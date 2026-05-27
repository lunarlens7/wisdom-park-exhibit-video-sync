import asyncio
from typing import Any
from tapo import ApiClient


class DeviceController:
    def __init__(self, email: str, password: str):
        self._client = ApiClient(email, password)
        self._state: dict[str, dict[str, Any]] = {}
        self._device_cache: dict[str, Any] = {}
        self._fade_gen: dict[str, int] = {}

    def get_state(self, ip: str) -> dict[str, Any]:
        return self._state.get(ip, {})

    def set_state(self, ip: str, **kwargs: Any) -> None:
        if ip not in self._state:
            self._state[ip] = {}
        self._state[ip].update(kwargs)

    async def _get_l530(self, ip: str):
        if ip not in self._device_cache:
            self._device_cache[ip] = await self._client.l530(ip)
        return self._device_cache[ip]

    async def _get_l630(self, ip: str):
        if ip not in self._device_cache:
            self._device_cache[ip] = await self._client.l630(ip)
        return self._device_cache[ip]

    async def _get_light(self, ip: str, device_type: str):
        if device_type == "l630":
            return await self._get_l630(ip)
        return await self._get_l530(ip)

    async def _get_p100(self, ip: str):
        if ip not in self._device_cache:
            self._device_cache[ip] = await self._client.p100(ip)
        return self._device_cache[ip]

    def _bump_gen(self, ip: str) -> None:
        self._fade_gen[ip] = self._fade_gen.get(ip, 0) + 1

    async def set_switch(self, ip: str, on: bool) -> None:
        self._bump_gen(ip)
        for attempt in range(2):
            try:
                device = await self._get_p100(ip)
                if on:
                    await device.on()
                else:
                    await device.off()
                self.set_state(ip, on=on)
                return
            except Exception as e:
                self._device_cache.pop(ip, None)
                if attempt == 0:
                    continue
                print(f"WARNING: Could not reach switch {ip}: {e}")

    async def set_light(
        self,
        ip: str,
        device_type: str = "l530",
        brightness: int | None = None,
        on: bool | None = None,
    ) -> None:
        if on is not None:
            self._bump_gen(ip)
        for attempt in range(2):
            try:
                device = await self._get_light(ip, device_type)
                if on is False and brightness is None:
                    await device.off()
                elif on is True and brightness is None:
                    await device.on()
                else:
                    builder = device.set()
                    if brightness is not None:
                        builder = builder.brightness(brightness)
                    if on is True:
                        builder = builder.on()
                    elif on is False:
                        builder = builder.off()
                    await builder.send(device)
                self.set_state(
                    ip,
                    **({} if brightness is None else {"brightness": brightness}),
                    **({} if on is None else {"on": on}),
                )
                return
            except Exception as e:
                self._device_cache.pop(ip, None)
                if attempt == 0:
                    continue
                print(f"WARNING: Could not reach light {ip}: {e}")

    async def apply_initial_state(self, ip: str, device_type: str, state: dict[str, Any]) -> None:
        on = state.get("on", True)
        if device_type == "p100":
            print(f"    → switch {ip} {'on' if on else 'off'}")
            await self.set_switch(ip, on)
        elif device_type in ("l530", "l630"):
            configured_brightness = state.get("brightness")
            if configured_brightness is not None:
                self.set_state(ip, brightness=configured_brightness)
                await self.set_light(ip, device_type=device_type, brightness=configured_brightness, on=on)
            else:
                device = await self._get_light(ip, device_type)
                info = await device.get_device_info()
                self.set_state(ip, brightness=info.brightness)
                await self.set_light(ip, device_type=device_type, on=on)

    async def fade(
        self,
        ip: str,
        device_type: str = "l530",
        duration: float = 0,
        to_brightness: int | None = None,
        steps: int = 20,
    ) -> None:
        self._bump_gen(ip)
        gen = self._fade_gen[ip]

        current = self.get_state(ip)
        from_b = current.get("brightness", 100)
        target_b = to_brightness if to_brightness is not None else from_b

        interval = duration / steps
        for i in range(1, steps + 1):
            if self._fade_gen.get(ip) != gen:
                return
            t = i / steps
            b = round(from_b + (target_b - from_b) * t)
            await self.set_light(ip, device_type=device_type, brightness=b)
            await asyncio.sleep(interval)
