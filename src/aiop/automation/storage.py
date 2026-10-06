"""JSON persistence for workflows."""

import json
import os
from pathlib import Path
from typing import List, Optional

from ..core import exceptions, logging
from .workflow import Workflow

logger = logging.get_logger(__name__)

STORE_SCHEMA_VERSION = 1
STORE_FILE_NAME = "workflows.json"


class WorkflowStore:
    """Basic JSON file store in the app-data workflows directory."""

    def __init__(self, workflows_dir: Optional[Path] = None):
        from ..core import utils

        self.directory = Path(workflows_dir) if workflows_dir else utils.get_workflows_dir()
        self.path = self.directory / STORE_FILE_NAME
        self._workflows: List[Workflow] = []
        self.load()

    def load(self) -> None:
        """Reload workflows from disk, tolerating a missing or damaged file."""
        if not self.path.exists():
            self._workflows = []
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            entries = raw.get("workflows") if isinstance(raw, dict) else raw
            workflows: List[Workflow] = []
            for entry in entries:
                try:
                    workflows.append(Workflow.from_dict(entry))
                except exceptions.AutomationError as error:
                    logger.warning("Skipping unreadable workflow entry: %s", error)
            self._workflows = workflows
        except (json.JSONDecodeError, OSError, ValueError) as error:
            logger.warning("Could not read workflow store %s: %s", self.path, error)
            self._workflows = []

    def list_workflows(self) -> List[Workflow]:
        return list(self._workflows)

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        for workflow in self._workflows:
            if workflow.id == workflow_id:
                return workflow
        return None

    def save_workflow(self, workflow: Workflow) -> None:
        """Insert or update a workflow and persist the store atomically."""
        workflow.validate()
        self._workflows = [
            existing for existing in self._workflows if existing.id != workflow.id
        ]
        self._workflows.append(workflow)
        self._persist()

    def delete_workflow(self, workflow_id: str) -> bool:
        before = len(self._workflows)
        self._workflows = [item for item in self._workflows if item.id != workflow_id]
        if len(self._workflows) == before:
            return False
        self._persist()
        return True

    def enabled_workflows(self) -> List[Workflow]:
        return [item for item in self._workflows if item.enabled]

    def _persist(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": STORE_SCHEMA_VERSION,
            "workflows": [workflow.to_dict() for workflow in self._workflows],
        }
        temp_path = self.path.with_suffix(".json.tmp")
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        # os.replace is atomic on Windows across the same volume.
        os.replace(temp_path, self.path)