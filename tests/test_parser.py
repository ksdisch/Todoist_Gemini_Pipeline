import pytest
from app.core.parser import extract_first_json, validate_schema, parse_and_validate_response

def test_extract_first_json_plain():
    text = '{"foo": "bar"}'
    assert extract_first_json(text) == {"foo": "bar"}

def test_extract_first_json_markdown():
    text = 'Here is the json:\n```json\n{"foo": "bar"}\n```'
    assert extract_first_json(text) == {"foo": "bar"}

def test_extract_first_json_nested():
    text = 'Prefix {"actions": [{"type": "test"}]} Suffix'
    assert extract_first_json(text) == {"actions": [{"type": "test"}]}

def test_extract_first_json_invalid():
    text = 'No json here'
    assert extract_first_json(text) is None

def test_validate_schema_valid():
    data = {
        "thought": "Testing",
        "actions": []
    }
    assert validate_schema(data) is True

def test_validate_schema_invalid_types():
    data = {
        "thought": 123,
        "actions": []
    }
    assert validate_schema(data) is False

def test_validate_schema_missing_thought():
    data = {
        "actions": []
    }
    assert validate_schema(data) is False

def test_validate_schema_missing_actions():
    data = {
        "thought": "Testing"
    }
    assert validate_schema(data) is False

def test_parse_and_validate_success():
    text = '```json\n{"thought": "Plan", "actions": []}\n```'
    result = parse_and_validate_response(text)
    assert result == {"thought": "Plan", "actions": []}

def test_parse_and_validate_fail():
    text = 'Bad content'
    assert parse_and_validate_response(text) is None
