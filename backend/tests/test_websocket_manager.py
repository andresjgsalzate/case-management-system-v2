import asyncio


def test_manager_connect_and_disconnect():
    """ConnectionManager registra y elimina conexiones correctamente."""
    from backend.src.core.websocket_manager import ConnectionManager
    from unittest.mock import AsyncMock, MagicMock

    manager = ConnectionManager()
    ws = MagicMock()
    ws.accept = AsyncMock()

    async def run():
        await manager.connect("case-1", "user-1", ws)
        assert "user-1" in manager.active_connections.get("case-1", {})

        manager.disconnect("case-1", "user-1")
        assert "user-1" not in manager.active_connections.get("case-1", {})

    asyncio.run(run())


def test_manager_broadcast_local_sends_to_all_in_case():
    """broadcast_local envía el mensaje a todas las conexiones del caso."""
    from backend.src.core.websocket_manager import ConnectionManager
    from unittest.mock import AsyncMock, MagicMock

    manager = ConnectionManager()

    ws1 = MagicMock()
    ws1.accept = AsyncMock()
    ws1.send_json = AsyncMock()

    ws2 = MagicMock()
    ws2.accept = AsyncMock()
    ws2.send_json = AsyncMock()

    async def run():
        await manager.connect("case-1", "user-1", ws1)
        await manager.connect("case-1", "user-2", ws2)

        await manager.broadcast_local("case-1", {"event": "test"})

        ws1.send_json.assert_called_once_with({"event": "test"})
        ws2.send_json.assert_called_once_with({"event": "test"})

    asyncio.run(run())


def test_manager_broadcast_local_ignores_other_cases():
    """broadcast_local no envía mensajes a conexiones de otros casos."""
    from backend.src.core.websocket_manager import ConnectionManager
    from unittest.mock import AsyncMock, MagicMock

    manager = ConnectionManager()

    ws_case1 = MagicMock()
    ws_case1.accept = AsyncMock()
    ws_case1.send_json = AsyncMock()

    ws_case2 = MagicMock()
    ws_case2.accept = AsyncMock()
    ws_case2.send_json = AsyncMock()

    async def run():
        await manager.connect("case-1", "user-1", ws_case1)
        await manager.connect("case-2", "user-2", ws_case2)

        await manager.broadcast_local("case-1", {"event": "only-case-1"})

        ws_case1.send_json.assert_called_once()
        ws_case2.send_json.assert_not_called()

    asyncio.run(run())


def test_manager_disconnect_nonexistent_does_not_raise():
    """Desconectar un usuario que no existe no debe lanzar excepción."""
    from backend.src.core.websocket_manager import ConnectionManager

    manager = ConnectionManager()
    # No debe lanzar KeyError ni AttributeError
    manager.disconnect("case-X", "user-X")
