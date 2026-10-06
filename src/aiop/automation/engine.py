"""Sequential workflow execution engine."""

import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as _FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core import config, exceptions
from .executor import SystemExecutor, interpolate
from .workflow import Step, Workflow

STEP_STATUS_OK = "success"
STEP_STATUS_FAILED = "failed"
STEP_STATUS_TIMEOUT = "timeout"

RUN_STATUS_RUNNING = "running"
RUN_STATUS_SUCCESS = "success"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_TIMEOUT = "timeout"


@dataclass
class StepRun:
    """Outcome of a single workflow step."""

    name: str
    type: str
    status: str
    seconds: float = 0.0
    message: str = ""


@dataclass
class WorkflowRun:
    """Outcome of a workflow execution."""

    workflow_id: str
    workflow_name: str
    status: str = RUN_STATUS_RUNNING
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    steps: List[StepRun] = field(default_factory=list)
    output: str = ""
    error: str = ""

    def finalize(self, status: str, error: str = "") -> "WorkflowRun":
        self.status = status
        self.error = error
        self.finished_at = time.time()
        return self


class _StepTimedOut(exceptions.AutomationError):
    pass


class WorkflowEngine:
    """Runs workflows, each on its own thread, bounded by a pool."""

    def __init__(
        self,
        timeout_seconds: Optional[int] = None,
        max_concurrent: int = 5,
        step_executor: Optional[Any] = None,
        llm_client: Optional[Any] = None,
    ):
        self.timeout_seconds = timeout_seconds
        if self.timeout_seconds is None:
            self.timeout_seconds = config.get_config().automation.timeout_seconds
        self.max_concurrent = max(1, max_concurrent)
        self._step_executor = step_executor if step_executor is not None else SystemExecutor()
        self._llm_client = llm_client
        self._pool = ThreadPoolExecutor(
            max_workers=self.max_concurrent,
            thread_name_prefix="workflow",
        )

    # ------------------------------------------------------------------ run
    def run(self, workflow: Workflow, context: Optional[Dict[str, Any]] = None) -> WorkflowRun:
        """Execute a workflow synchronously. Never raises; results in the run."""
        run = WorkflowRun(workflow_id=workflow.id, workflow_name=workflow.name)
        try:
            workflow.validate()
        except exceptions.AutomationError as error:
            return run.finalize(RUN_STATUS_FAILED, str(error))

        variables: Dict[str, Any] = dict(context or {})
        variables.setdefault("output", "")

        for index, step in enumerate(workflow.steps):
            step_run = self._execute_step(workflow, step, index, variables)
            run.steps.append(step_run)
            if step_run.status != STEP_STATUS_OK:
                message = step_run.message or f"Step failed ({step_run.name or step.type})"
                return run.finalize(RUN_STATUS_FAILED, message)
            variables[str(index)] = step_run.message
            key = step.name or "output"
            variables[key] = step_run.message
            run.output = step_run.message

        return run.finalize(RUN_STATUS_SUCCESS)

    def _execute_step(
        self,
        workflow: Workflow,
        step: Step,
        index: int,
        variables: Dict[str, Any],
    ) -> StepRun:
        started = time.time()
        step_run = StepRun(name=step.name, type=step.type, status=STEP_STATUS_OK)
        timeout = self._step_timeout(workflow)
        try:
            if step.type == "prompt":
                message = self._llm_step(step, variables)
            else:
                message = self._timed(self._step_executor.execute, step, variables, timeout=timeout)
            step_run.message = message or ""
        except _StepTimedOut:
            step_run.status = STEP_STATUS_TIMEOUT
            step_run.message = "Timed out"
        except exceptions.AutomationError as error:
            step_run.status = STEP_STATUS_FAILED
            step_run.message = str(error)
        except Exception as error:  # defensive: executor bugs become failed steps
            step_run.status = STEP_STATUS_FAILED
            step_run.message = f"{type(error).__name__}: {error}"
        step_run.seconds = round(time.time() - started, 3)
        return step_run

    def _step_timeout(self, workflow: Workflow) -> float:
        override = workflow.timeout_seconds
        return float(override if override else self.timeout_seconds or 120)

    def _timed(self, callable_, *args, timeout: float):
        """Run a blocking call with a hard timeout on a helper thread."""
        if timeout is None or timeout <= 0:
            return callable_(*args)
        single = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wstep")
        future = single.submit(callable_, *args)
        try:
            result = future.result(timeout=timeout)
        except _FutureTimeout:
            # Do not block on shutdown() here: the late task is abandoned and
            # its worker thread exits on its own once it finishes.
            future.cancel()
            raise _StepTimedOut(f"Step timed out after {timeout}s")
        single.shutdown(wait=True)
        return result

    def _llm_step(self, step: Step, variables: Dict[str, Any]) -> str:
        params = step.params
        prompt = interpolate(str(params.get("prompt", "")), variables)
        system = None
        if params.get("system"):
            system = interpolate(str(params["system"]), variables)
        client = self._llm_client if self._llm_client is not None else _default_llm_client()
        temperature = float(params.get("temperature", 0.2))
        max_tokens = int(params.get("max_tokens", 1024))
        model = str(params.get("model", "")).strip() or None
        return client.complete(
            prompt=prompt,
            system=system,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # ---------------------------------------------------------------- submit
    def submit(
        self,
        workflow: Workflow,
        context: Optional[Dict[str, Any]] = None,
        on_done: Optional[Any] = None,
    ) -> Future:
        """Queue a workflow on the shared pool; on_done(future) runs when finished."""
        future = self._pool.submit(self.run, workflow, context)
        if on_done is not None:
            future.add_done_callback(on_done)
        return future

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


_llm_client_cache: Optional[Any] = None


def _default_llm_client() -> Any:
    """Shared OpenAI-compatible client built from the current settings."""
    global _llm_client_cache
    if _llm_client_cache is None:
        from .llm import OpenAICompatibleClient

        settings = config.get_config().ai
        _llm_client_cache = OpenAICompatibleClient(
            base_url=settings.base_url,
            api_key=settings.api_key,
        )
    return _llm_client_cache


def reset_llm_client_cache() -> None:
    """Drop the cached client (used when settings change)."""
    global _llm_client_cache
    _llm_client_cache = None