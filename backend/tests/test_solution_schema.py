"""Solution schema and raw-output parsing tests."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.schemas.api import GenerationRequest
from app.schemas.solution import SolutionResponse
from app.services.solution_parser import (
    build_degraded_solution,
    extract_json_object,
    validate_raw_output,
    validate_solution_payload,
)


def _valid_payload(**overrides) -> dict:
    payload = {
        "title": "Lookup department",
        "summary": "XLOOKUP by employee id.",
        "platform": "excel",
        "task_type": "formula",
        "formula": '=XLOOKUP(A2,Employees!A:A,Employees!B:B,"Not found")',
        "explanation": "Looks up the department for the employee id in A2.",
        "implementation_steps": [
            {"title": "Enter formula", "instructions": "Type into C2 and fill down."}
        ],
        "assumptions": [],
        "prerequisites": [],
        "alternative_solutions": [],
        "common_errors": [],
        "troubleshooting": [],
        "warnings": [],
    }
    payload.update(overrides)
    return payload


class TestSolutionSchema:
    def test_valid_payload_passes(self):
        report = validate_solution_payload(_valid_payload())
        assert report.valid is True
        assert report.solution is not None

    def test_formula_task_requires_formula(self):
        report = validate_solution_payload(_valid_payload(formula=None))
        assert report.valid is False

    def test_code_requires_language(self):
        report = validate_solution_payload(_valid_payload(formula=None, code="Sub Main()\nEnd Sub"))
        assert report.valid is False
        assert any("code_language" in e for e in report.errors)

    def test_invalid_platform_literal(self):
        report = validate_solution_payload(_valid_payload(platform="libreoffice"))
        assert report.valid is False

    def test_language_is_normalized(self):
        report = validate_solution_payload(
            _valid_payload(formula=None, code="Sub Main()\nEnd Sub", code_language="VBA")
        )
        assert report.valid is True
        assert report.solution.code_language == "vba"

    def test_oversized_title_rejected(self):
        report = validate_solution_payload(_valid_payload(title="x" * 500))
        assert report.valid is False

    def test_control_chars_stripped(self):
        payload = _valid_payload(explanation="Hello\x00\x07 world")
        report = validate_solution_payload(payload)
        assert report.valid is True
        assert "\x00" not in report.solution.explanation


class TestJsonExtraction:
    def test_plain_json(self):
        payload, err = extract_json_object(json.dumps(_valid_payload()))
        assert err is None and payload is not None

    def test_fenced_json(self):
        text = "```json\n" + json.dumps(_valid_payload()) + "\n```"
        payload, err = extract_json_object(text)
        assert err is None and payload["title"] == "Lookup department"

    def test_json_with_prose_around(self):
        text = "Sure! Here's your solution:\n" + json.dumps(_valid_payload()) + "\nHope that helps!"
        payload, err = extract_json_object(text)
        assert err is None and payload is not None

    def test_no_json(self):
        payload, err = extract_json_object("no json here")
        assert payload is None and err is not None

    def test_empty(self):
        payload, _err = extract_json_object("")
        assert payload is None

    def test_broken_json_reports_error(self):
        payload, err = extract_json_object('{"title": "x", broken}')
        assert payload is None
        assert "invalid JSON" in (err or "")


class TestValidateRawOutput:
    def test_valid_end_to_end(self):
        report = validate_raw_output(json.dumps(_valid_payload()))
        assert report.valid is True

    def test_fenced_end_to_end(self):
        report = validate_raw_output("```json\n" + json.dumps(_valid_payload()) + "\n```")
        assert report.valid is True
        assert report.solution.formula.startswith("=")


class TestDegradedSolution:
    def test_degraded_wraps_raw_text(self):
        req = GenerationRequest(request="do something with my data")
        solution = build_degraded_solution("raw unvalidated output here", req)
        assert "raw unvalidated output here" in solution.explanation
        assert solution.code_language == "unvalidated_output"
        assert solution.warnings
        # Degraded solutions must still be serializable for the API layer.
        solution.model_dump()


class TestSolutionResponseRoundTrip:
    def test_json_round_trip(self):
        report = validate_solution_payload(_valid_payload())
        dumped = report.solution.model_dump()
        restored = SolutionResponse.model_validate(dumped)
        assert restored.title == report.solution.title

    def test_validation_error_is_pydantic(self):
        with pytest.raises(ValidationError):
            SolutionResponse.model_validate(_valid_payload(platform="sheets"))
