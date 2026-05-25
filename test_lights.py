"""Quick connectivity + control test for all Tapo lights."""
import asyncio
import os
from dotenv import load_dotenv
from tapo import ApiClient

load_dotenv()

DEVICES = [
    ("L630", "192.168.8.100", "spotlight 3"),
    ("L630", "192.168.8.102", "spotlight 2"),
    ("L630", "192.168.8.103", "spotlight 1"),
]


async def test_device(client: ApiClient, model: str, ip: str, name: str) -> None:
    print(f"\n--- {model} @ {ip}  ({name}) ---")
    try:
        device = await (client.l630(ip) if model == "L630" else client.l530(ip))
        info = await device.get_device_info()
        print(f"  Connected  |  on={info.device_on}  brightness={info.brightness}  "
              f"hue={getattr(info, 'hue', 'n/a')}  sat={getattr(info, 'saturation', 'n/a')}")

        print("  Setting brightness to 50% ...", end=" ", flush=True)
        await device.set().brightness(50).send(device)
        print("ok")

        await asyncio.sleep(1)

        print("  Turning off ...", end=" ", flush=True)
        await device.off()
        print("ok")

        await asyncio.sleep(3)

        print("  Restoring original state ...", end=" ", flush=True)
        builder = device.set().brightness(info.brightness)
        if info.device_on:
            builder = builder.on()
        await builder.send(device)
        print("ok")

    except Exception as e:
        print(f"  FAILED: {e}")


async def main() -> None:
    email = os.environ.get("TAPO_EMAIL")
    password = os.environ.get("TAPO_PASSWORD")
    if not email or not password:
        print("ERROR: Set TAPO_EMAIL and TAPO_PASSWORD in your .env file.")
        return

    client = ApiClient(email, password)
    print(f"Testing {len(DEVICES)} device(s)...\n")
    for model, ip, name in DEVICES:
        await test_device(client, model, ip, name)
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
