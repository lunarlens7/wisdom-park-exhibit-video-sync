import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from vlc_poller import VlcPoller


@pytest.mark.asyncio
async def test_returns_playback_position():
    poller = VlcPoller(host="localhost", port=8080, password="secret")

    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value={"time": 42.5, "state": "playing"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("vlc_poller.aiohttp.ClientSession") as mock_session_cls:
        mock_session_cls.return_value = mock_session
        position = await poller.get_position()

    assert position == 42.5


@pytest.mark.asyncio
async def test_returns_none_when_vlc_unreachable():
    poller = VlcPoller(host="localhost", port=8080, password="secret")

    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=Exception("Connection refused"))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("vlc_poller.aiohttp.ClientSession") as mock_session_cls:
        mock_session_cls.return_value = mock_session
        position = await poller.get_position()

    assert position is None
