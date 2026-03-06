"""Tests for intake bot conversation state machine."""

from legal.intake_bot.conversation_flow import IntakeConversation


def test_initial_state_greeting():
    conv = IntakeConversation()
    assert conv.get_state() == "GREETING"


def test_greeting_to_collect_name():
    conv = IntakeConversation()
    response = conv.process_message("Hello")
    assert conv.get_state() == "COLLECT_NAME"
    assert "name" in response.lower()


def test_full_flow():
    conv = IntakeConversation()

    conv.process_message("Hi")
    assert conv.get_state() == "COLLECT_NAME"

    conv.process_message("Chan Tai Man / 陳大文")
    assert conv.get_state() == "COLLECT_CONTACT"

    conv.process_message("91234567")
    assert conv.get_state() == "COLLECT_CONTACT"
    assert conv.get_collected_data().get("phone") is not None

    conv.process_message("test@example.com")
    assert conv.get_state() == "COLLECT_MATTER"

    conv.process_message("1")
    assert conv.get_state() == "COLLECT_MATTER"

    conv.process_message("Landlord hasn't returned deposit")
    assert conv.get_state() == "COLLECT_MATTER"

    conv.process_message("2")
    assert conv.get_state() == "COLLECT_ADVERSE_PARTY"

    conv.process_message("Wong Siu Ming")
    assert conv.get_state() == "CONFIRM"

    conv.process_message("yes")
    assert conv.get_state() == "COMPLETE"


def test_human_escalation():
    conv = IntakeConversation()
    conv.process_message("Hello")
    assert conv.get_state() == "COLLECT_NAME"

    response = conv.process_message("I'd like to speak to human please")
    assert conv.get_state() == "HUMAN_ESCALATION"
    assert "transfer" in response.lower()


def test_get_collected_data():
    conv = IntakeConversation()

    conv.process_message("Hi")
    conv.process_message("Chan Tai Man / 陳大文")
    conv.process_message("91234567")
    conv.process_message("test@example.com")
    conv.process_message("1")
    conv.process_message("Landlord hasn't returned deposit")
    conv.process_message("2")
    conv.process_message("Wong Siu Ming")
    conv.process_message("yes")

    data = conv.get_collected_data()
    assert data.get("name_en") == "Chan Tai Man"
    assert data.get("name_tc") == "陳大文"
    assert data.get("phone") is not None
    assert data.get("matter_type") is not None
    assert data.get("adverse_party_name") == "Wong Siu Ming"
