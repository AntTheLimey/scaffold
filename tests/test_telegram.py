from unittest.mock import MagicMock, patch

import pytest

from orchestrator.telegram import TelegramBot


@pytest.fixture
def bot():
    return TelegramBot(token="fake-token", chat_id="12345")


@patch("orchestrator.telegram.httpx.Client.post")
def test_send_escalation(mock_post, bot):
    mock_post.return_value = MagicMock(
        json=lambda: {"ok": True, "result": {"message_id": 42}},
        raise_for_status=MagicMock(),
    )
    msg_id = bot.send_escalation(
        question="Should we use REST or GraphQL?",
        options=["REST", "GraphQL"],
        task_id="task-001",
    )
    assert msg_id == 42
    call_args = mock_post.call_args
    assert "inline_keyboard" in str(call_args)


@patch("orchestrator.telegram.httpx.Client.post")
def test_send_digest(mock_post, bot):
    mock_post.return_value = MagicMock(
        json=lambda: {"ok": True, "result": {"message_id": 43}},
        raise_for_status=MagicMock(),
    )
    bot.send_digest(done=5, in_progress=3, blocked=1, cost_today=2.50)
    mock_post.assert_called_once()


def test_bot_context_manager():
    bot = TelegramBot(token="fake-token", chat_id="12345")
    with bot:
        pass


def test_ping_no_token():
    bot = TelegramBot(token="", chat_id="12345")
    assert bot.ping() is False


@patch("orchestrator.telegram.httpx.Client.post")
@patch("orchestrator.telegram.httpx.Client.get")
def test_ping_success(mock_get, mock_post, bot):
    mock_get.return_value = MagicMock(
        json=lambda: {"ok": True, "result": {"username": "scaffold_bot"}},
        raise_for_status=MagicMock(),
    )
    mock_post.return_value = MagicMock(
        json=lambda: {"ok": True, "result": {"message_id": 99}},
        raise_for_status=MagicMock(),
    )
    assert bot.ping() is True
    mock_get.assert_called_once()
    mock_post.assert_called_once()


@patch("orchestrator.telegram.httpx.Client.get")
def test_ping_failure(mock_get, bot):
    import httpx

    mock_get.side_effect = httpx.HTTPError("connection failed")
    assert bot.ping() is False


@patch("orchestrator.telegram.httpx.Client.post")
def test_poll_tracks_offset(mock_post, bot):
    mock_post.return_value = MagicMock(
        json=lambda: {
            "ok": True,
            "result": [
                {
                    "update_id": 100,
                    "callback_query": {
                        "id": "cb1",
                        "data": '{"task": "t1", "choice": "Approve"}',
                    },
                }
            ],
        },
        raise_for_status=MagicMock(),
    )
    bot.poll_for_callback(timeout=1)
    assert bot._offset == 101
