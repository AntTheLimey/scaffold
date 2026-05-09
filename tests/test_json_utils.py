import pytest
from orchestrator.json_utils import extract_json


def test_parses_plain_json():
    raw = '{"children": [{"title": "Auth"}]}'
    result = extract_json(raw)
    assert result["children"][0]["title"] == "Auth"


def test_parses_json_in_code_fence():
    raw = 'Here is the result:\n```json\n{"verdict": "approve"}\n```'
    result = extract_json(raw)
    assert result["verdict"] == "approve"


def test_parses_json_in_bare_code_fence():
    raw = '```\n{"verdict": "revise", "feedback": "missing tests"}\n```'
    result = extract_json(raw)
    assert result["verdict"] == "revise"


def test_extracts_first_json_object_from_prose():
    raw = 'Sure! Here you go:\n{"position": "Use REST", "concedes": false}\nHope that helps!'
    result = extract_json(raw)
    assert result["position"] == "Use REST"


def test_returns_empty_dict_on_no_json():
    raw = "I couldn't produce valid JSON for this request."
    result = extract_json(raw)
    assert result == {}


def test_handles_nested_braces():
    raw = '{"children": [{"acceptance": ["test {edge} case"]}]}'
    result = extract_json(raw)
    assert result["children"][0]["acceptance"] == ["test {edge} case"]
