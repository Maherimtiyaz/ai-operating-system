"""Workflow model, storage, engine, and command-router tests."""

import time
from pathlib import Path

import pytest

from aiop.automation import (
    RUN_STATUS_FAILED,
    RUN_STATUS_SUCCESS,
    Step,
    Workflow,
    WorkflowCommandRouter,
    WorkflowEngine,
    WorkflowStore,
    interpolate,
)
from aiop.core import exceptions


# ----------------------------------------------------------------- helpers
def make_workflow(steps=None, **overrides):
    defaults = {
        "name": "Test workflow",
        "trigger": "run test",
        "steps": steps if steps is not None else [
            Step(type="type", name="out", params={"text": "hi there"})
        ],
    }
    defaults.update(overrides)
    return Workflow(**defaults)


class RecordingExecutor:
    def __init__(self, results=None):
        self.results = dict(results or {})
        self.calls = []

    def execute(self, step, context):
        self.calls.append((step.type, dict(step.params), dict(context)))
        params = {key: interpolate(str(value), context) for key, value in step.params.items()}
        if step.type == "type":
            return f"typed:{params['text']}"
        if step.type == "open":
            return f"opened:{params['app']}"
        if step.type == "keys":
            return f"keys:{params['combo']}"
        if step.type == "shell":
            return f"shell:{params['command']}"
        if step.type == "wait":
            return f"waited:{params['seconds']}"
        return "?"


def build_engine(executor=None, llm=None, **kwargs):
    return WorkflowEngine(step_executor=executor or RecordingExecutor(), llm_client=llm, **kwargs)


class RecordingLLM:
    def __init__(self, response="llm answer"):
        self.response = response
        self.calls = []

    def complete(self, prompt, system=None, model=None, temperature=0.2, max_tokens=1024):
        self.calls.append(
            {"prompt": prompt, "system": system, "model": model, "temperature": temperature}
        )
        return self.response


# ------------------------------------------------------------------- model
def test_workflow_serialization_roundtrip():
    source = make_workflow(
        description="demo",
        enabled=True,
        trigger_type="prefix",
        steps=[
            Step(type="shell", name="s", params={"command": "scripts\\run.ps1 {{text}}"}),
            Step(type="type", params={"text": "{{s}}"}),
        ],
    )
    restored = Workflow.from_dict(source.to_dict())
    assert restored.to_dict() == source.to_dict()
    assert restored.id == source.id
    assert restored.steps[0].params["command"] == "scripts\\run.ps1 {{text}}"


def test_workflow_from_dict_defaults_apply():
    restored = Workflow.from_dict({"name": "X", "steps": [{"type": "wait", "params": {"seconds": 1}}]})
    assert restored.id
    assert restored.enabled is True
    assert restored.trigger == ""
    assert restored.trigger_type == "exact"
    assert restored.steps[0].type == "wait"


def test_workflow_rejects_unknown_step_type():
    with pytest.raises(exceptions.AutomationError):
        Workflow.from_dict({"name": "X", "steps": [{"type": "explode"}]})


def test_workflow_rejects_missing_required_params():
    workflow = make_workflow(steps=[Step(type="shell", params={})])
    with pytest.raises(exceptions.AutomationError):
        workflow.validate()


def test_workflow_requires_at_least_one_step():
    workflow = make_workflow(steps=[])
    with pytest.raises(exceptions.AutomationError):
        workflow.validate()


def test_workflow_rejects_bad_trigger_type():
    with pytest.raises(exceptions.AutomationError):
        make_workflow(trigger_type="fuzzy")


def test_trigger_match_modes():
    exact = make_workflow(name="exact", trigger="open notepad", trigger_type="exact")
    prefix = make_workflow(name="prefix", trigger="compose", trigger_type="prefix")
    regex = make_workflow(name="regex", trigger=r"\bemail\b", trigger_type="regex")

    assert exact.matches("Open Notepad") is True
    assert exact.matches("open notepad please") is False
    assert prefix.matches("Compose an email to bob") is True
    assert prefix.matches("compose") is True
    assert regex.matches("send an email to bob") is True
    assert regex.matches("emailing is fun") is False
    assert regex.matches("no match here") is False
    assert exact.matches("") is False
    assert prefix.matches("  compose later  ") is True
    assert regex.matches("EMAIL") is True


# --------------------------------------------------------------- interpolate
def test_interpolate_fills_known_and_keeps_unknown():
    context = {"text": "hello", "out": "world"}
    assert interpolate("say {{text}} then {{out}}", context) == "say hello then world"
    assert interpolate("keep {{missing}} as-is and {braces}", context) == (
        "keep {{missing}} as-is and {braces}"
    )
    assert interpolate("no braces", context) == "no braces"
    assert interpolate("unclosed {{text", context) == "unclosed {{text"


# ------------------------------------------------------------------- storage
def test_store_crud_roundtrip(tmp_path):
    store = WorkflowStore(workflows_dir=Path(tmp_path))
    wf = make_workflow()
    store.save_workflow(wf)
    assert store.list_workflows()[0].id == wf.id
    assert store.get_workflow(wf.id).name == wf.name

    store.delete_workflow(wf.id)
    assert store.get_workflow(wf.id) is None
    assert store.list_workflows() == []


def test_store_reloads_from_disk(tmp_path):
    store = WorkflowStore(workflows_dir=Path(tmp_path))
    wf = make_workflow(name="persisted")
    store.save_workflow(wf)
    second = WorkflowStore(workflows_dir=Path(tmp_path))
    assert [item.name for item in second.list_workflows()] == ["persisted"]


def test_store_skips_invalid_entries(tmp_path):
    directory = Path(tmp_path)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "workflows.json").write_text(
        '{"version": 1, "workflows": [{"name": "ok", "steps": [{"type": "wait", "params": {"seconds": 1}}]}, {"nope": true}]}',
        encoding="utf-8",
    )
    store = WorkflowStore(workflows_dir=directory)
    assert [item.name for item in store.list_workflows()] == ["ok"]


def test_store_handles_missing_file(tmp_path):
    store = WorkflowStore(workflows_dir=Path(tmp_path) / "nested" / "dir")
    assert store.list_workflows() == []
    store.save_workflow(make_workflow())
    assert store.list_workflows()


def test_save_writes_atomically(tmp_path):
    store = WorkflowStore(workflows_dir=Path(tmp_path))
    store.save_workflow(make_workflow())
    assert not (Path(tmp_path) / "workflows.json.tmp").exists()
    assert (Path(tmp_path) / "workflows.json").exists()


# -------------------------------------------------------------------- engine
def test_engine_runs_steps_in_order_and_passes_outputs():
    executor = RecordingExecutor()
    wf = make_workflow(
        steps=[
            Step(type="shell", name="greeting", params={"command": "hi"}),
            Step(type="type", name="final", params={"text": "{{greeting}} from {{text}}"}),
        ]
    )
    engine = build_engine(executor)
    run = engine.run(wf, {"text": "chain"})
    assert run.status == RUN_STATUS_SUCCESS
    assert [step.type for step in run.steps] == ["shell", "type"]
    assert run.output == "typed:shell:hi from chain"
    assert executor.calls[1][2]["greeting"] == "shell:hi"
    assert executor.calls[1][1]["text"] == "{{greeting}} from {{text}}"


def test_engine_prompt_step_feeds_llm_output_via_name():
    llm = RecordingLLM(response="drafted email")
    wf = make_workflow(
        steps=[
            Step(type="prompt", name="draft", params={"prompt": "draft re {{text}}", "model": "gpt-x"}),
            Step(type="type", name="send", params={"text": "{{draft}}"}),
        ]
    )
    engine = WorkflowEngine(step_executor=RecordingExecutor(), llm_client=llm)
    run = engine.run(wf, {"text": "boss"})
    assert run.status == RUN_STATUS_SUCCESS
    assert llm.calls[0]["prompt"] == "draft re boss"
    assert llm.calls[0]["model"] == "gpt-x"
    assert run.output == "typed:drafted email"


def test_engine_stops_and_labels_failure():
    class Boom:
        def execute(self, step, context):
            if step.type == "shell":
                raise exceptions.AutomationError("command not found")
            return "ok"

    wf = make_workflow(
        steps=[
            Step(type="shell", params={"command": "bad"}),
            Step(type="type", name="after", params={"text": "should not run"}),
        ]
    )
    engine = WorkflowEngine(step_executor=Boom())
    run = engine.run(wf, {"text": "x"})
    assert run.status == RUN_STATUS_FAILED
    assert run.steps[0].status == "failed"
    assert run.steps[0].message == "command not found"
    assert len(run.steps) == 1


def test_engine_times_out_a_slow_step():
    class Slow:
        def execute(self, step, context):
            time.sleep(5.0)
            return "late"

    wf = make_workflow(
        timeout_seconds=1,
        steps=[Step(type="shell", params={"command": "sleep"})],
    )
    engine = WorkflowEngine(step_executor=Slow(), timeout_seconds=1)
    started = time.monotonic()
    run = engine.run(wf)
    assert run.status == RUN_STATUS_FAILED
    assert run.steps[0].status == "timeout"
    assert run.steps[0].message == "Timed out"
    assert time.monotonic() - started < 1.5


def test_engine_keeps_unknown_placeholders_in_llm_prompt():
    llm = RecordingLLM()
    wf = make_workflow(
        steps=[Step(type="prompt", params={"prompt": "fix {{text}}, ignore {{todo}}"})]
    )
    engine = WorkflowEngine(step_executor=RecordingExecutor(), llm_client=llm)
    run = engine.run(wf, {"text": "hi"})
    assert run.status == RUN_STATUS_SUCCESS
    assert llm.calls[0]["prompt"] == "fix hi, ignore {{todo}}"


def test_engine_rejects_unvalidatable_workflow_gracefully():
    engine = build_engine()
    run = engine.run(make_workflow(steps=[]))
    assert run.status == RUN_STATUS_FAILED
    assert run.steps == []


def test_submit_runs_on_pool_and_calls_back():
    executor = RecordingExecutor()
    engine = build_engine(executor)
    wf = make_workflow(steps=[Step(type="type", name="x", params={"text": "ping"})])
    holder = {}

    def done(future):
        holder["run"] = future.result()

    engine.submit(wf, {"text": "seed"}, on_done=done)
    for _ in range(100):
        if "run" in holder:
            break
        time.sleep(0.01)
    assert holder["run"].status == RUN_STATUS_SUCCESS
    assert holder["run"].output == "typed:ping"
    engine.shutdown()


def test_engine_max_concurrent_does_not_deadlock_single_worker():
    executor = RecordingExecutor()
    engine = build_engine(executor, max_concurrent=1)
    run = engine.run(
        make_workflow(steps=[Step(type="type", params={"text": "hi"})]),
        {"text": "seed"},
    )
    assert run.status == RUN_STATUS_SUCCESS
    engine.shutdown()


# -------------------------------------------------------------- command router
def test_router_matches_enabled_workflow_only(tmp_path):
    store = WorkflowStore(workflows_dir=Path(tmp_path))
    engine = WorkflowEngine(step_executor=RecordingExecutor(), llm_client=RecordingLLM())
    router = WorkflowCommandRouter(store=store, engine=engine)
    store.save_workflow(make_workflow(name="a", trigger="start backup", enabled=True))
    disabled = make_workflow(name="b", trigger="hidden job", enabled=False)
    store.save_workflow(disabled)

    assert router.find_workflow("start backup") is not None
    assert router.find_workflow("START BACKUP") is not None
    assert router.find_workflow("hidden job") is None
    engine.shutdown()


def test_router_prefers_exact_over_prefix_and_longest(tmp_path):
    store = WorkflowStore(workflows_dir=Path(tmp_path))
    router = WorkflowCommandRouter(store=store, engine=WorkflowEngine())
    store.save_workflow(make_workflow(name="prefix-short", trigger="compose", trigger_type="prefix"))
    store.save_workflow(make_workflow(name="prefix-long", trigger="compose email", trigger_type="prefix"))
    store.save_workflow(make_workflow(name="exact", trigger="compose email", trigger_type="exact"))
    assert router.find_workflow("compose email").name == "exact"
    assert router.find_workflow("compose email now").name == "prefix-long"


def test_router_dispatch_returns_feedback_or_none(tmp_path):
    store = WorkflowStore(workflows_dir=Path(tmp_path))
    engine = WorkflowEngine(step_executor=RecordingExecutor())
    router = WorkflowCommandRouter(store=store, engine=engine)
    store.save_workflow(make_workflow(name="clean desktop", trigger="clean desktop"))
    result = router.dispatch("clean desktop", {"text": "clean desktop"})
    assert result is not None
    assert result["ok"] is True
    assert 'Running workflow "clean desktop"' in result["message"]

    assert router.dispatch("dictate this sentence", {}) is None
    engine.shutdown()


def test_router_persists_last_run_status(tmp_path):
    engine = WorkflowEngine(step_executor=RecordingExecutor())
    router = WorkflowCommandRouter(store=WorkflowStore(workflows_dir=Path(tmp_path)), engine=engine)
    store = router.store
    wf = make_workflow(name="d", trigger="do thing")
    store.save_workflow(wf)

    result = router.dispatch("do thing")
    assert result is not None
    for _ in range(200):
        stored = store.get_workflow(wf.id)
        if stored.last_run_status == RUN_STATUS_SUCCESS:
            break
        time.sleep(0.01)
    assert store.get_workflow(wf.id).last_run_status == RUN_STATUS_SUCCESS
    engine.shutdown()