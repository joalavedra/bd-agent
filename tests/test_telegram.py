from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_bot import handle_message, send_briefing, _split_message, TELEGRAM_MAX_LENGTH


def _make_message(chat_id: int, text: str = "hello") -> MagicMock:
    msg = AsyncMock()
    msg.chat = MagicMock()
    msg.chat.id = chat_id
    msg.text = text
    msg.answer = AsyncMock()
    return msg


async def test_unauthorized_chat_rejected(env_vars):
    msg = _make_message(chat_id=999999)
    await handle_message(msg)
    msg.answer.assert_called_once_with("Unauthorized.")


async def test_authorized_message_routed_to_agent(env_vars):
    msg = _make_message(chat_id=123456789, text="research Fireblocks")

    mock_result = MagicMock()
    mock_result.output = "Fireblocks is a custody platform."

    with patch("src.telegram_bot.bd_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_result)
        await handle_message(msg)

    msg.answer.assert_called_once_with("Fireblocks is a custody platform.")


async def test_long_response_split(env_vars):
    long_text = "A" * 5000
    msg = _make_message(chat_id=123456789, text="test")

    mock_result = MagicMock()
    mock_result.output = long_text

    with patch("src.telegram_bot.bd_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_result)
        await handle_message(msg)

    assert msg.answer.call_count == 2
    chunks = [call.args[0] for call in msg.answer.call_args_list]
    assert all(len(c) <= TELEGRAM_MAX_LENGTH for c in chunks)
    assert "".join(chunks) == long_text


async def test_agent_error_sent_to_user(env_vars):
    msg = _make_message(chat_id=123456789, text="crash")

    with patch("src.telegram_bot.bd_agent") as mock_agent:
        mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        await handle_message(msg)

    msg.answer.assert_called_once()
    response = msg.answer.call_args[0][0]
    assert "Agent error" in response
    assert "LLM unavailable" in response


def test_split_message_short():
    assert _split_message("short") == ["short"]


def test_split_message_at_newline():
    part1 = "A" * 4000
    part2 = "B" * 200
    text = part1 + "\n" + part2
    chunks = _split_message(text)
    assert len(chunks) == 2
    assert chunks[0] == part1
    assert chunks[1] == part2


def test_split_message_no_newline():
    text = "X" * 5000
    chunks = _split_message(text)
    assert len(chunks) == 2
    assert len(chunks[0]) == TELEGRAM_MAX_LENGTH
    assert chunks[0] + chunks[1] == text


async def test_send_briefing_sends_to_owner(env_vars):
    mock_bot = AsyncMock()
    with patch("src.telegram_bot.get_bot", return_value=mock_bot):
        await send_briefing("Daily update here")
    mock_bot.send_message.assert_called_once_with(chat_id=123456789, text="Daily update here")


async def test_send_briefing_splits_long_messages(env_vars):
    mock_bot = AsyncMock()
    long_text = "Z" * 5000
    with patch("src.telegram_bot.get_bot", return_value=mock_bot):
        await send_briefing(long_text)
    assert mock_bot.send_message.call_count == 2
