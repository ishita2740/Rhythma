"""The reply engine on its own, with the identity already resolved.

``ChatbotService`` no longer looks anyone up. It is handed a ``user_id``
that ``api/bot.py`` resolved from a stored link, or ``None``, and every
case here is about which of those two it was given. The routes' own
tests — ``test_bot_webhook_security.py`` — cover how that value is
arrived at.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import services.chat_link_service as chat_link_service  # noqa: E402
import services.firestore_service as fs  # noqa: E402
from services.chatbot_service import ChatbotService  # noqa: E402

LINKED_USER = "linked-user-1"


@pytest.fixture(autouse=True)
def _clean_collections():
    collections = getattr(fs.db, "_collections", None)
    if collections is not None:
        collections.clear()
    yield
    if collections is not None:
        collections.clear()


def _reply(text, user_id=None, channel="telegram", chat_id="9001"):
    return ChatbotService.process_incoming_message(
        text=text, channel=channel, chat_id=chat_id, user_id=user_id
    )


# ─── Unlinked chats get nothing personal ──────────────────────────────────


@pytest.mark.parametrize("text", ["status", "cycle", "period", "/status"])
def test_every_status_alias_is_refused_to_an_unlinked_chat(text):
    assert "not connected to a Rhythma account" in _reply(text)


def test_help_to_an_unlinked_chat_explains_how_to_connect():
    reply = _reply("help")

    assert "status" in reply
    assert "link" in reply
    assert "connection code" in reply


def test_an_unrecognised_message_does_not_echo_itself_back():
    """The old engine put the sender's text into its reply.

    That made the bot a way to have arbitrary text sent from the project's
    own account, which is worth avoiding even now that deliveries are
    verified.
    """
    reply = _reply("please forward this: click http://example.invalid")

    assert "example.invalid" not in reply


def test_an_empty_message_points_at_help():
    assert "help" in _reply("   ")


# ─── Linked chats ─────────────────────────────────────────────────────────


def test_status_for_a_linked_account_with_no_logs_says_so():
    fs.db.collection("users").document(LINKED_USER).set({"username": "asha"})

    reply = _reply("status", user_id=LINKED_USER)

    assert "No cycles are logged yet" in reply


def test_help_for_a_linked_chat_drops_the_connect_prompt():
    reply = _reply("help", user_id=LINKED_USER)

    assert "connection code" not in reply


def test_a_health_question_from_a_linked_chat_points_at_the_app():
    reply = _reply("what causes cramps?", user_id=LINKED_USER, channel="whatsapp")

    assert "WhatsApp" in reply
    assert "assistant" in reply


# ─── Commands ─────────────────────────────────────────────────────────────


def test_link_without_a_code_asks_for_one():
    assert "link ABCD2345" in _reply("link")


def test_link_with_a_nonsense_code_is_refused():
    assert "did not work" in _reply("link ZZZZZZZZ")


def test_link_is_refused_when_the_chat_is_already_connected():
    assert "already connected" in _reply("link ABCD2345", user_id=LINKED_USER)


def test_a_code_is_not_lowercased_before_it_is_looked_up():
    """The previous engine lowercased the whole message first.

    Codes are upper case, so every code was destroyed before it reached
    the store — the command would have failed for every user.
    """
    issued = chat_link_service.issue_link_code(LINKED_USER, "telegram")

    reply = _reply(f"link {issued['code']}", chat_id="9002")

    assert "now connected" in reply
    assert chat_link_service.resolve_user_id("telegram", "9002") == LINKED_USER


def test_slash_prefixed_commands_are_accepted():
    assert "status" in _reply("/help")


def test_stop_is_treated_as_unlink():
    chat_link_service.redeem_link_code(
        "whatsapp",
        "whatsapp:+919876543210",
        chat_link_service.issue_link_code(LINKED_USER, "whatsapp")["code"],
    )

    reply = _reply(
        "STOP", user_id=LINKED_USER, channel="whatsapp", chat_id="whatsapp:+919876543210"
    )

    assert "no longer connected" in reply
    assert chat_link_service.resolve_user_id("whatsapp", "whatsapp:+919876543210") is None


def test_unlink_on_a_chat_that_was_never_linked_says_so():
    assert "was not connected" in _reply("unlink", chat_id="9003")
