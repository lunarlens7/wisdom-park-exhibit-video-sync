from tapo import ApiClient


async def discover_devices(email: str, password: str, timeout: float = 10.0) -> list[dict]:
    client = ApiClient(email, password)
    found = []
    try:
        discovery = await client.discover_devices("255.255.255.255", timeout_s=int(timeout))
        async for maybe in discovery:
            device = maybe.get()
            if device is None:
                continue
            found.append({
                "ip": device.ip,
                "model": device.model,
                "name": device.nickname,
            })
    except Exception as e:
        print(f"Discovery error: {e}")
    return found


def print_devices(devices: list[dict]) -> None:
    if not devices:
        print("No Tapo devices found on the local network.")
        return
    print(f"Found {len(devices)} device(s):\n")
    for d in devices:
        print(f"  {d['model']:<12} @ {d['ip']:<18}  (name: \"{d['name']}\")")
