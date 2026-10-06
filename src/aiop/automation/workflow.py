"""Workflow data model for voice-triggered automation.

A workflow is a sequential list of steps. Each workflow can be activated by
speaking its trigger phrase; the successful transcript is seeded into the run
context as ``text`` and any step output can be referenced by later steps via
``{{step.name}}``.

The model is deliberately plain JSON-friendly data so users can hand-edit
workflows and share them: the open source architecture takes the user's own
OpenAI API key at runtime and never ships one.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core import exceptions

# Supported step types and the required params for each.
_REQUIRED_PARAMS = {
    "prompt": ("prompt",),
    "shell": ("command",),
    "type": ("text",),
    "keys": ("combo",),
    "open": ("app",),
    "wait": ("seconds",),
}

SUPPORTED_STEP_TYPES: List[str] = list(_REQUIRED_PARAMS)

TRIGGER_TYPES = ("exact", "prefix", "regex")


@dataclass
class Step:
    """A single workflow step."""

    type: str
    params: Dict[str, Any] = field(default_factory=dict)
    name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"type": self.type}
        if self.name:
            data["name"] = self.name
        if self.params:
            data["params"] = dict(self.params)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], index: int) -> "Step":
        step_type = str(data.get("type", "")).strip()
        if step_type not in SUPPORTED_STEP_TYPES:
            raise exceptions.AutomationError(
                f"Workflow fix: step {index + 1} has unknown type "
                f"{step_type!r} (supported: {', '.join(SUPPORTED_STEP_TYPES)})"
            )
        params = data.get("params") if isinstance(data.get("params"), dict) else {}
        name = str(data.get("name", "")).strip()
        return cls(type=step_type, params=dict(params), name=name)

    def validate(self, index: int) -> None:
        missing = [
            key for key in _REQUIRED_PARAMS[self.type] if not str(self.params.get(key, "")).strip()
        ]
        if missing:
            raise exceptions.AutomationError(
                f"Step {index + 1} ({self.type}) is missing params: {', '.join(missing)}"
            )
        if self.type == "wait":
            try:
                float(self.params.get("seconds"))
            except (TypeError, ValueError):
                raise exceptions.AutomationError(
                    f"Step {index + 1} (wait) needs a numeric 'seconds' param"
                )


@dataclass
class Workflow:
    """A voice-triggered sequence of steps."""

    name: str
    steps: List[Step]
    id: str = ""
    description: str = ""
    enabled: bool = True
    trigger: str = ""
    trigger_type: str = "exact"
    timeout_seconds: Optional[int] = None
    last_run_status: str = ""
    last_run_message: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            from ..core import utils

            self.id = utils.generate_id("wf")
        if self.trigger_type not in TRIGGER_TYPES:
            raise exceptions.AutomationError(
                f"Workflow '{self.name}': trigger_type must be one of {TRIGGER_TYPES}"
            )

    def validate(self) -> None:
        if not self.name.strip():
            raise exceptions.AutomationError("Workflow needs a name")
        if not self.steps:
            raise exceptions.AutomationError(f"Workflow '{self.name}' has no steps")
        for index, step in enumerate(self.steps):
            step.validate(index)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": bool(self.enabled),
            "trigger": self.trigger,
            "trigger_type": self.trigger_type,
            "timeout_seconds": self.timeout_seconds,
            "last_run_status": self.last_run_status,
            "last_run_message": self.last_run_message,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        name = str(data.get("name", "")).strip()
        if not name:
            raise exceptions.AutomationError("A workflow entry is missing its name")
        steps = [
            Step.from_dict(item, index)
            for index, item in enumerate(data.get("steps") or [])
        ]
        timeout = data.get("timeout_seconds")
        return cls(
            id=str(data.get("id", "")).strip(),
            name=name,
            description=str(data.get("description", "")).strip(),
            enabled=bool(data.get("enabled", True)),
            trigger=str(data.get("trigger", "")).strip(),
            trigger_type=str(data.get("trigger_type", "exact")),
            timeout_seconds=int(timeout) if timeout not in (None, "") else None,
            last_run_status=str(data.get("last_run_status", "")).strip(),
            last_run_message=str(data.get("last_run_message", "")).strip(),
            steps=steps,
        )

    def matches(self, text: str) -> bool:
        """Return True if the workflow can be activated by this transcript."""
        trigger = self.trigger.strip()
        if not trigger or not self.enabled:
            return False
        text = text.strip()
        if self.trigger_type == "exact":
            return text.lower() == trigger.lower()
        if self.trigger_type == "prefix":
            return text.lower().startswith(trigger.lower())
        if self.trigger_type == "regex":
            import re

            return re.search(trigger, text, re.IGNORECASE) is not None
        return False