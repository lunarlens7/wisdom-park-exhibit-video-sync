from plugp100.common.credentials import AuthCredential
from plugp100.discovery.tapo_discovery import TapoDiscovery


async def discover_devices(email: str, password: str, timeout: float = 5.0) -> list[dict]:
    credentials = AuthCredential(email, password)
    found = []
    try:
        discovered = await TapoDiscovery.scan(timeout=timeout)
        for d in discovered:
            try:
                device = await d.get_tapo_device(credentials)
                await device.update()
                found.append({
                    "ip": d.ip,
                    "type": type(device).__name__,
                    "name": getattr(device, "nickname", "unknown"),
                })
                await device.client.close()
            except Exception:
                found.append({"ip": d.ip, "type": d.device_type, "name": "unknown"})
    except Exception as e:
        print(f"Discovery error: {e}")
    return found


def print_devices(devices: list[dict]) -> None:
    if not devices:
        print("No Tapo devices found on the local network.")
        return
    print(f"Found {len(devices)} device(s):\n")
    for d in devices:
        print(f"  {d['type']:<12} @ {d['ip']:<18}  (name: \"{d['name']}\")")
