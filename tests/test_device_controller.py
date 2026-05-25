import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from device_controller import DeviceController

def make_controller():
    return DeviceController(email="test@x.com", password="secret")

def make_mock_light():
    """Returns (device_mock, builder_mock). The builder chains sync methods and has async .send()."""
    builder = MagicMock()
    builder.on.return_value = builder
    builder.off.return_value = builder
    builder.brightness.return_value = builder
    builder.hue_saturation.return_value = builder
    builder.send = AsyncMock()
    device = MagicMock()
    device.set.return_value = builder
    return device, builder

@pytest.mark.asyncio
async def test_set_switch_on(monkeypatch):
    ctrl = make_controller()
    mock_device = AsyncMock()
    monkeypatch.setattr(ctrl, "_get_p100", AsyncMock(return_value=mock_device))
    await ctrl.set_switch("192.168.1.1", True)
    mock_device.on.assert_awaited_once()

@pytest.mark.asyncio
async def test_set_switch_off(monkeypatch):
    ctrl = make_controller()
    mock_device = AsyncMock()
    monkeypatch.setattr(ctrl, "_get_p100", AsyncMock(return_value=mock_device))
    await ctrl.set_switch("192.168.1.1", False)
    mock_device.off.assert_awaited_once()

@pytest.mark.asyncio
async def test_set_light_updates_tracked_state(monkeypatch):
    ctrl = make_controller()
    device, builder = make_mock_light()
    monkeypatch.setattr(ctrl, "_get_l530", AsyncMock(return_value=device))
    await ctrl.set_light("192.168.1.2", brightness=80)
    state = ctrl.get_state("192.168.1.2")
    assert state["brightness"] == 80
    builder.brightness.assert_called_once_with(80)

@pytest.mark.asyncio
async def test_set_light_partial_update_preserves_existing_state(monkeypatch):
    ctrl = make_controller()
    ctrl._state["192.168.1.2"] = {"brightness": 50, "on": True}
    device, builder = make_mock_light()
    monkeypatch.setattr(ctrl, "_get_l530", AsyncMock(return_value=device))
    await ctrl.set_light("192.168.1.2", brightness=90)
    state = ctrl.get_state("192.168.1.2")
    assert state["brightness"] == 90
    assert state["on"] == True  # unchanged

@pytest.mark.asyncio
async def test_set_light_warns_on_device_error(monkeypatch, capsys):
    ctrl = make_controller()
    monkeypatch.setattr(ctrl, "_get_l530", AsyncMock(side_effect=Exception("unreachable")))
    await ctrl.set_light("192.168.1.2", brightness=50)
    captured = capsys.readouterr()
    assert "WARNING" in captured.out or "warning" in captured.out.lower()

@pytest.mark.asyncio
async def test_fade_interpolates_brightness(monkeypatch):
    ctrl = make_controller()
    ctrl._state["192.168.1.2"] = {"brightness": 100, "on": True}
    calls = []
    async def fake_set_light(ip, brightness=None):
        calls.append(brightness)
    monkeypatch.setattr(ctrl, "set_light", fake_set_light)
    await ctrl.fade("192.168.1.2", to_brightness=0, duration=0.1, steps=5)
    assert len(calls) >= 2
    assert calls[-1] == 0
    assert calls[0] > calls[-1]
