"""PRISM Agent - Config Schema Validation"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from prism.logging import logger
import traceback


CONFIG_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "model": {
            "type": "object",
            "properties": {
                "default": {"type": "string"},
                "provider": {"type": "string"},
                "base_url": {"type": "string"},
                "api_key": {"type": "string"},
                "context_length": {"type": "integer", "minimum": 1},
                "max_tokens": {"type": "integer", "minimum": 1},
            },
            "required": ["provider", "base_url"],
        },
        "fallback": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "chain": {"type": "array", "items": {"type": "string"}},
            },
        },
        "agent": {
            "type": "object",
            "properties": {
                "max_turns": {"type": "integer", "minimum": 1, "maximum": 10000},
                "tool_use_enforcement": {"type": "string"},
                "parallel_tools": {"type": "boolean"},
            },
        },
        "terminal": {
            "type": "object",
            "properties": {
                "timeout": {"type": "integer", "minimum": 1, "maximum": 3600},
                "backend": {"type": "string"},
            },
        },
        "gateway": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "platforms": {"type": "array", "items": {"type": "string"}},
            },
        },
        "toolsets": {
            "type": "array",
            "items": {"type": "string"},
        },
        "mcp": {
            "type": "object",
            "properties": {
                "servers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "id": {"type": "string"},
                            "transport": {"type": "string"},
                            "command": {"type": "string"},
                            "url": {"type": "string"},
                            "args": {"type": "array", "items": {"type": "string"}},
                        },
                        "oneOf": [
                            {"required": ["command"]},
                            {"required": ["url"]},
                        ],
                    },
                }
            },
        },
    },
    "required": ["model"],
}


class ConfigValidationError(Exception):
    """配置校验失败"""


def validate_config(config: Dict[str, Any], schema: Optional[Dict[str, Any]] = None) -> None:
    """校验配置是否符合 schema"""
    if schema is None:
        schema = CONFIG_SCHEMA

    errors = _validate_against_schema(config, schema)
    if errors:
        raise ConfigValidationError(
            "config validation failed:\n" + "\n".join(f"- {e}" for e in errors)
        )


def _validate_against_schema(config: Any, schema: Dict[str, Any], path: str = "") -> List[str]:
    errors: List[str] = []

    if not isinstance(config, dict) and schema.get("type") == "object":
        if path:
            errors.append(f"{path}: expected object, got {type(config).__name__}")
        return errors

    if schema.get("type") == "object" and isinstance(config, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in config:
                errors.append(f"{path + '.' if path else ''}{key}: required field missing")

        properties = schema.get("properties", {})
        for key, value in config.items():
            sub_path = f"{path}.{key}" if path else key
            if key in properties:
                errors.extend(_validate_against_schema(value, properties[key], sub_path))

    elif schema.get("type") == "array" and isinstance(config, list):
        item_schema = schema.get("items")
        if item_schema:
            for idx, item in enumerate(config):
                errors.extend(_validate_against_schema(item, item_schema, f"{path}[{idx}]"))

    elif schema.get("type") == "string" and not isinstance(config, str):
        errors.append(f"{path}: expected string, got {type(config).__name__}")

    elif schema.get("type") == "integer" and not isinstance(config, int):
        errors.append(f"{path}: expected integer, got {type(config).__name__}")

    elif schema.get("type") == "boolean" and not isinstance(config, bool):
        errors.append(f"{path}: expected boolean, got {type(config).__name__}")

    if "minimum" in schema and isinstance(config, (int, float)):
        if config < schema["minimum"]:
            errors.append(f"{path}: value {config} < minimum {schema['minimum']}")

    if "maximum" in schema and isinstance(config, (int, float)):
        if config > schema["maximum"]:
            errors.append(f"{path}: value {config} > maximum {schema['maximum']}")

    return errors
