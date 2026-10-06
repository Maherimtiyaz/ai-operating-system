"""Route recognized speech to a matching workflow, else fall through."""

import logging
from typing import Any, Dict, Optional

from ..core import config
from .engine import WorkflowEngine
from .storage import WorkflowStore
from .workflow import Workflow

logger = logging.getLogger(__name__)

MATCH_PRIORITY = {"exact": 0, "prefix": 1, "regex": 2}


class WorkflowCommandRouter:
    """Matches a transcript against enabled workflows for voice activation."""

    def __init__(self, store: Optional[WorkflowStore] = None, engine: Optional[WorkflowEngine] = None):
        self.store = store if store is not None else WorkflowStore()
        self.engine = engine if engine is not None else WorkflowEngine()
        self._last_future = None

    def find_workflow(self, text: str) -> Optional[Workflow]:
        """Return the best-matching enabled workflow, or None."""
        normalized = text.strip()
        if not normalized:
            return None
        candidates = []
        for workflow in self.store.enabled_workflows():
            if workflow.matches(normalized):
                priority = MATCH_PRIORITY.get(workflow.trigger_type, 99)
                candidates.append((priority, -len(workflow.trigger), workflow))
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][2]

    def dispatch(self, text: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, str]]:
        """Activate a workflow from a transcript.

        Returns a feedback payload {'message': ..., 'ok': bool} when a
        workflow matched, or None to let dictation handle the text.
        """
        workflow = self.find_workflow(text)
        if workflow is None:
            return None
        variables = dict(context or {})
        variables.setdefault("text", text)
        self._last_future = self.engine.submit(workflow, variables, on_done=self._on_run_done)
        logger.info("Voice-activated workflow '%s' by: %s", workflow.name, text)
        return {"message": f"Running workflow \"{workflow.name}\"...", "ok": True}

    def _on_run_done(self, future) -> None:
        """Persist the last-run marker for the editor/status surfaces."""
        try:
            run = future.result()
            workflow = self.store.get_workflow(run.workflow_id)
            if workflow is None:
                return
            workflow.last_run_status = run.status
            workflow.last_run_message = run.error or run.output
            self.store.save_workflow(workflow)
        except Exception as error:  # the callback runs on a pool thread; never crash it
            logger.warning("Workflow completion tracking failed: %s", error)

    def record_success(self, workflow_id: str, message: str = "") -> None:
        workflow = self.store.get_workflow(workflow_id)
        if workflow is None:
            return
        workflow.last_run_status = "success"
        workflow.last_run_message = message
        self.store.save_workflow(workflow)

    def record_failure(self, workflow_id: str, message: str) -> None:
        workflow = self.store.get_workflow(workflow_id)
        if workflow is None:
            return
        workflow.last_run_status = "failed"
        workflow.last_run_message = message
        self.store.save_workflow(workflow)


def engine_from_config() -> WorkflowEngine:
    """Build an engine tuned to the current automation settings."""
    automation = config.get_config().automation
    return WorkflowEngine(
        timeout_seconds=automation.timeout_seconds,
        max_concurrent=automation.max_concurrent_workflows,
    )