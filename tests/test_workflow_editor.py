"""Workflow editor dialog tests (offscreen-safe, tmp stores only)."""

from pathlib import Path

import pytest

from PyQt6.QtWidgets import QApplication

from aiop.automation import Step, Workflow, WorkflowStore
from aiop.ui.workflow_editor import StepEditDialog, WorkflowEditorDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def make_store(tmp_path) -> WorkflowStore:
    return WorkflowStore(workflows_dir=Path(tmp_path))


def make_editor(qapp, store, **engine_kwargs):
    from aiop.automation import WorkflowEngine

    from aiop.automation.executor import StepExecutor

    class NoopExecutor(StepExecutor):
        def execute(self, step, context):
            return "noop"

    engine = WorkflowEngine(step_executor=NoopExecutor(), **engine_kwargs)
    dialog = WorkflowEditorDialog(store=store, engine=engine)
    return dialog


def test_editor_lists_stored_workflows(qapp, tmp_path):
    store = make_store(tmp_path)
    store.save_workflow(Workflow(name="alpha", trigger="a", steps=[Step(type="wait", params={"seconds": 1})]))
    store.save_workflow(Workflow(name="beta", trigger="b", steps=[Step(type="wait", params={"seconds": 2})], enabled=False))
    dialog = make_editor(qapp, store)
    assert dialog._workflow_list.count() == 2
    assert dialog._workflow_list.item(0).text().startswith("alpha")
    assert "off" in dialog._workflow_list.item(1).text()
    assert dialog._selected().name == "alpha"


def test_editor_loads_selected_workflow_into_form(qapp, tmp_path):
    store = make_store(tmp_path)
    wf = Workflow(
        name="compose",
        trigger="compose email",
        trigger_type="prefix",
        steps=[Step(type="prompt", name="draft", params={"prompt": "draft {{text}}"}),
               Step(type="type", params={"text": "{{draft}}"})],
    )
    store.save_workflow(wf)
    dialog = make_editor(qapp, store)
    assert dialog._name_input.text() == "compose"
    assert dialog._trigger_input.text() == "compose email"
    assert dialog._trigger_type_combo.currentText() == "prefix"
    assert dialog._steps_list.count() == 2


def test_editor_new_workflow_appears_in_store(qapp, tmp_path):
    store = make_store(tmp_path)
    dialog = make_editor(qapp, store)
    dialog._new_workflow()
    assert dialog._workflow_list.count() == 1
    created = store.list_workflows()[0]
    assert created.name == "New workflow"
    assert created.steps[0].type == "prompt"


def test_editor_duplicate_workflow(qapp, tmp_path):
    store = make_store(tmp_path)
    store.save_workflow(Workflow(name="orig", trigger="x", steps=[Step(type="wait", params={"seconds": 1})]))
    dialog = make_editor(qapp, store)
    dialog._duplicate_workflow()
    names = {wf.name for wf in store.list_workflows()}
    assert "orig copy" in names


def test_editor_delete_workflow(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    store = make_store(tmp_path)
    store.save_workflow(Workflow(name="gone", trigger="x", steps=[Step(type="wait", params={"seconds": 1})]))
    dialog = make_editor(qapp, store)
    monkeypatch.setattr(
        "aiop.ui.workflow_editor.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    dialog._delete_workflow()
    assert store.list_workflows() == []


def test_editor_save_persists_form_changes(qapp, tmp_path):
    store = make_store(tmp_path)
    wf = Workflow(name="n1", trigger="t", steps=[Step(type="wait", params={"seconds": 1})])
    store.save_workflow(wf)
    dialog = make_editor(qapp, store)
    dialog._name_input.setText("renamed")
    dialog._trigger_input.setText("new trigger")
    dialog._trigger_type_combo.setCurrentIndex(dialog._trigger_type_combo.findText("prefix"))
    saved = dialog._save_current()
    assert saved is not None
    reloaded = store.get_workflow(wf.id)
    assert reloaded.name == "renamed"
    assert reloaded.trigger == "new trigger"
    assert reloaded.trigger_type == "prefix"


def test_step_editor_creates_a_step(qapp):
    dialog = StepEditDialog()
    assert dialog.step() is None
    dialog._type_combo.setCurrentIndex(dialog._type_combo.findText("prompt"))
    dialog._prompt_edit.setPlainText("summarize {{text}}")
    dialog._model_input.setText("gpt-4o-mini")
    dialog._temperature_spin.setValue(0.0)
    dialog._on_accept()
    step = dialog.step()
    assert step is not None
    assert step.type == "prompt"
    assert step.params["prompt"] == "summarize {{text}}"
    assert step.params["temperature"] == 0.0


def test_step_editor_validates_missing_params(qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    warnings = []
    monkeypatch.setattr(
        "aiop.ui.workflow_editor.QMessageBox.warning",
        lambda *args, **kwargs: warnings.append(args),
    )
    dialog = StepEditDialog()
    dialog._type_combo.setCurrentIndex(dialog._type_combo.findText("shell"))
    dialog._command_input.setText("")
    dialog._on_accept()
    assert dialog.step() is None
    assert warnings
    assert QMessageBox is not None


def test_step_editor_loads_existing_step(qapp):
    step = Step(type="keys", name="shot", params={"combo": "Ctrl+Shift+Esc"})
    dialog = StepEditDialog(step=step)
    assert dialog._type_combo.currentText() == "keys"
    assert dialog._keys_input.text() == "Ctrl+Shift+Esc"
    assert dialog._name_input.text() == "shot"