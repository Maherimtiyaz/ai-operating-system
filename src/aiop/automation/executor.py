"""System-side step execution for workflows.

The engine talks to the operating system through this narrow interface, so
tests can inject a recording fake instead of a real focused window.
"""

import os
import subprocess
import time

from ..core import exceptions
from .workflow import Step


def interpolate(template: str, context) -> str:
    """Replace {{name}} placeholders with their context value.

    Unknown placeholders are left untouched so verbatim braces in prompts
    survive; named braces like {{foo}} that are not populated are also kept.
    """
    out = []
    start = 0
    while True:
        open_brace = template.find("{{", start)
        if open_brace == -1:
            out.append(template[start:])
            break
        close_brace = template.find("}}", open_brace + 2)
        if close_brace == -1:
            out.append(template[start:])
            break
        key = template[open_brace + 2: close_brace].strip()
        out.append(template[start:open_brace])
        if key in context:
            out.append(str(context[key]))
        else:
            out.append(template[open_brace: close_brace + 2])
        start = close_brace + 2
    return "".join(out)


class StepExecutor:
    """Executes a validated step. Subclassed by system and test fakes."""

    def execute(self, step: Step, context) -> str:
        raise NotImplementedError


class SystemExecutor(StepExecutor):
    """Runs steps against the real Windows desktop."""

    def execute(self, step: Step, context) -> str:
        if step.type == "prompt":
            raise exceptions.AutomationError(
                "Prompt steps need an LLM client; run through WorkflowEngine instead"
            )
        if step.type == "shell":
            command = interpolate(str(step.params.get("command", "")), context)
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                errors="replace",
            )
            if completed.returncode != 0:
                raise exceptions.AutomationError(
                    f"Shell command failed ({completed.returncode}): "
                    f"{completed.stderr.strip() or completed.stdout.strip()}"
                )
            return completed.stdout.strip()
        if step.type == "type":
            self._type_text(interpolate(str(step.params.get("text", "")), context))
            return ""
        if step.type == "keys":
            self._send_keys(interpolate(str(step.params.get("combo", "")), context))
            return ""
        if step.type == "open":
            os.startfile(interpolate(str(step.params.get("app", "")), context))
            return ""
        if step.type == "wait":
            time.sleep(max(0.0, float(step.params.get("seconds", 0))))
            return ""
        raise exceptions.AutomationError(f"Unsupported step type: {step.type}")

    def _type_text(self, text: str) -> None:
        if not text:
            return
        from ..windows.actions import paste_into_foreground

        paste_into_foreground(text)

    def _send_keys(self, combo: str) -> None:
        from ..windows import get_win32_api

        mod, vk = _parse_single_combo(combo)
        get_win32_api().send_vk_combo(mod, vk)


def _parse_single_combo(combo: str):
    from ..core.utils import parse_hotkey

    mod, vk = parse_hotkey(combo)
    if vk is None or vk == 0:
        raise exceptions.AutomationError(f"Cannot parse key combo: {combo}")
    return mod, vk