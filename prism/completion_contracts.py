"""
PRISM completion contracts — lightweight output self-validation.
Verifies agent output against simple contracts and returns pass/fail with reasons.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence


@dataclass
class CompletionContract:
    """Single completion contract rule."""
    name: str
    rule: str  # contains | json | min_length | regex | schema
    value: Any = None
    required: bool = True


@dataclass
class ContractResult:
    passed: bool
    contract_name: str
    detail: str = ""


def evaluate(output: str, contracts: Sequence[CompletionContract]) -> Dict[str, Any]:
    """Evaluate output against contracts and return verification result."""
    results: List[ContractResult] = []
    failures = 0
    for c in contracts:
        detail = ""
        passed = True
        try:
            if c.rule == "contains":
                detail = f"contains '{c.value}'"
                passed = str(c.value) in output
            elif c.rule == "not_contains":
                detail = f"not_contains '{c.value}'"
                passed = str(c.value) not in output
            elif c.rule == "min_length":
                detail = f"length>={c.value}"
                passed = len(output) >= int(c.value)
            elif c.rule == "max_length":
                detail = f"length<={c.value}"
                passed = len(output) <= int(c.value)
            elif c.rule == "regex":
                detail = f"matches /{c.value}/"
                passed = bool(re.search(str(c.value), output))
            elif c.rule == "json":
                detail = "valid_json"
                json.loads(output)
            elif c.rule == "schema":
                detail = "schema_check"
                schema = c.value or {}
                if not isinstance(schema, dict):
                    passed = False
                else:
                    try:
                        data = json.loads(output)
                        for key, expected_type in schema.items():
                            if key not in data:
                                passed = False
                                break
                            if expected_type == "str" and not isinstance(data[key], str):
                                passed = False
                                break
                            if expected_type == "int" and not isinstance(data[key], int):
                                passed = False
                                break
                            if expected_type == "list" and not isinstance(data[key], list):
                                passed = False
                                break
                    except Exception:  # noqa: BLE001
                        passed = False
            elif c.rule == "custom":
                checker: Callable[[str], bool] = c.value
                detail = "custom"
                passed = bool(checker(output))
            else:
                detail = f"unknown_rule:{c.rule}"
                passed = not c.required
        except Exception as exc:  # noqa: BLE001
            passed = False
            detail = f"error:{exc}"
        if not passed:
            failures += 1
        results.append(ContractResult(passed=passed, contract_name=c.name, detail=detail))
    return {
        "passed": failures == 0,
        "failures": failures,
        "total": len(contracts),
        "results": [
            {"name": r.contract_name, "passed": r.passed, "detail": r.detail}
            for r in results
        ],
    }


def validate_and_retry(
    run_fn: Callable[[], str],
    contracts: Sequence[CompletionContract],
    max_rounds: int = 2,
    feedback_fn: Optional[Callable[[Dict[str, Any]], str]] = None,
) -> Dict[str, Any]:
    """Run `run_fn`, validate output, optionally retry with feedback."""
    last_output = ""
    last_result = {}
    for attempt in range(max(1, max_rounds)):
        output = run_fn()
        last_output = output
        result = evaluate(output, contracts)
        last_result = result
        if result.get("passed"):
            return {
                "passed": True,
                "output": output,
                "attempts": attempt + 1,
                "contracts": result,
            }
        if attempt + 1 < max_rounds:
            feedback = ""
            if feedback_fn:
                try:
                    feedback = feedback_fn(result) or ""
                except Exception:  # noqa: BLE001
                    feedback = ""
            # NOTE: This does not inject feedback back into run_fn; the caller
            # must build a feedback-aware run_fn if retry should change input.
    return {
        "passed": False,
        "output": last_output,
        "attempts": max_rounds,
        "contracts": last_result,
    }
