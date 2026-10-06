"""Form-based editor for voice-triggered workflows."""

from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..automation import Step, Workflow, WorkflowEngine
from ..automation.commands import engine_from_config
from ..automation.storage import WorkflowStore
from ..core import exceptions, logging

logger = logging.get_logger(__name__)

_INPUT_STYLE = (
    "QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox { background-color: #252525; "
    "color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }"
)
_BUTTON_STYLE = (
    "QPushButton { background-color: #303030; color: #a0a0a0; border: 1px solid #404040; "
    "border-radius: 4px; padding: 6px 10px; }"
    "QPushButton:hover { background-color: #404040; }"
)
_PRIMARY_BUTTON_STYLE = (
    "QPushButton { background-color: #2a82e4; color: white; border: none; border-radius: 4px; "
    "padding: 6px 12px; font-weight: bold; }"
    "QPushButton:hover { background-color: #3d92f5; }"
)

STEP_TYPE_HINTS = {
    "prompt": "Ask the configured OpenAI-compatible model.",
    "shell": "Run an arbitrary command (PowerShell/cmd). Output feeds later steps.",
    "type": "Type text into the focused window.",
    "keys": "Send a hotkey combo, e.g. Ctrl+Shift+Esc.",
    "open": "Open an app path, file, folder, or URL.",
    "wait": "Pause for N seconds.",
}


# ------------------------------------------------------------------- singletons
_store: Optional[WorkflowStore] = None
_engine: Optional[WorkflowEngine] = None


def get_workflow_store() -> WorkflowStore:
    global _store
    if _store is None:
        _store = WorkflowStore()
    return _store


def get_workflow_engine() -> WorkflowEngine:
    global _engine
    if _engine is None:
        _engine = engine_from_config()
    return _engine


def open_workflows_dialog(parent=None) -> Optional[int]:
    """Open the workflow editor (also used by the Ctrl+Shift+W hotkey)."""
    dialog = WorkflowEditorDialog(store=get_workflow_store(), engine=get_workflow_engine(), parent=parent)
    return dialog.exec()


# ------------------------------------------------------------- step editor
class StepEditDialog(QDialog):
    """Small dialog to add/edit a single workflow step."""

    def __init__(self, step: Optional[Step] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Workflow Step")
        self._step = None
        self._build_ui()
        if step is not None:
            self._load(step)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._type_combo = QComboBox()
        self._type_combo.setStyleSheet(_INPUT_STYLE)
        self._type_combo.addItems(["prompt", "shell", "type", "keys", "open", "wait"])
        form.addRow("Type:", self._type_combo)

        self._name_input = QLineEdit()
        self._name_input.setStyleSheet(_INPUT_STYLE)
        self._name_input.setPlaceholderText("Output name (optional, referenced as {{name}})")
        form.addRow("Step name:", self._name_input)

        # prompt
        self._prompt_edit = QTextEdit()
        self._prompt_edit.setFixedHeight(80)
        self._prompt_edit.setStyleSheet(_INPUT_STYLE)
        form.addRow("Prompt:", self._prompt_edit)

        self._system_input = QLineEdit()
        self._system_input.setStyleSheet(_INPUT_STYLE)
        form.addRow("System prompt:", self._system_input)

        self._model_input = QLineEdit()
        self._model_input.setStyleSheet(_INPUT_STYLE)
        self._model_input.setPlaceholderText("Leave empty for the default model")
        form.addRow("Model:", self._model_input)

        self._temperature_spin = QDoubleSpinBox()
        self._temperature_spin.setRange(0.0, 2.0)
        self._temperature_spin.setSingleStep(0.1)
        self._temperature_spin.setValue(0.2)
        self._temperature_spin.setStyleSheet(_INPUT_STYLE)
        form.addRow("Temperature:", self._temperature_spin)

        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(1, 32768)
        self._max_tokens_spin.setValue(1024)
        self._max_tokens_spin.setStyleSheet(_INPUT_STYLE)
        form.addRow("Max tokens:", self._max_tokens_spin)

        # shell
        self._command_input = QLineEdit()
        self._command_input.setStyleSheet(_INPUT_STYLE)
        form.addRow("Command:", self._command_input)

        # type
        self._text_input = QLineEdit()
        self._text_input.setStyleSheet(_INPUT_STYLE)
        form.addRow("Text:", self._text_input)

        # keys
        self._keys_input = QLineEdit()
        self._keys_input.setStyleSheet(_INPUT_STYLE)
        form.addRow("Combo:", self._keys_input)

        # open
        self._open_input = QLineEdit()
        self._open_input.setStyleSheet(_INPUT_STYLE)
        form.addRow("App/Path/URL:", self._open_input)

        # wait
        self._wait_spin = QDoubleSpinBox()
        self._wait_spin.setRange(0.0, 3600.0)
        self._wait_spin.setSingleStep(0.5)
        self._wait_spin.setValue(1.0)
        self._wait_spin.setStyleSheet(_INPUT_STYLE)
        form.addRow("Seconds:", self._wait_spin)

        layout.addLayout(form)

        self._hint_label = QLabel()
        self._hint_label.setStyleSheet("color: #808080; font-size: 11px;")
        self._hint_label.setWordWrap(True)
        layout.addWidget(self._hint_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(_PRIMARY_BUTTON_STYLE)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setStyleSheet(_BUTTON_STYLE)
        layout.addWidget(buttons)

        self._type_combo.currentTextChanged.connect(self._update_hint)
        self._update_hint(self._type_combo.currentText())

    def _update_hint(self, step_type: str) -> None:
        self._hint_label.setText(STEP_TYPE_HINTS.get(step_type, ""))

    def _load(self, step: Step) -> None:
        index = max(0, self._type_combo.findText(step.type))
        self._type_combo.setCurrentIndex(index)
        self._name_input.setText(step.name)
        params = dict(step.params)
        self._prompt_edit.setPlainText(str(params.get("prompt", "")))
        self._system_input.setText(str(params.get("system", "")))
        self._model_input.setText(str(params.get("model", "")))
        try:
            self._temperature_spin.setValue(float(params.get("temperature", 0.2)))
        except ValueError:
            pass
        try:
            self._max_tokens_spin.setValue(int(params.get("max_tokens", 1024)))
        except ValueError:
            pass
        self._command_input.setText(str(params.get("command", "")))
        self._text_input.setText(str(params.get("text", "")))
        self._keys_input.setText(str(params.get("combo", "")))
        self._open_input.setText(str(params.get("app", "")))
        try:
            self._wait_spin.setValue(float(params.get("seconds", 1.0)))
        except ValueError:
            pass

    def _on_accept(self) -> None:
        step_type = self._type_combo.currentText()
        params: Dict[str, Any] = {}

        def put(key, value):
            if value:
                params[key] = value

        if step_type == "prompt":
            put("prompt", self._prompt_edit.toPlainText().strip())
            put("system", self._system_input.text().strip())
            put("model", self._model_input.text().strip())
            if self._temperature_spin.value() != 0.2:
                params["temperature"] = self._temperature_spin.value()
            if self._max_tokens_spin.value() != 1024:
                params["max_tokens"] = self._max_tokens_spin.value()
        elif step_type == "shell":
            put("command", self._command_input.text().strip())
        elif step_type == "type":
            put("text", self._text_input.text().strip())
        elif step_type == "keys":
            put("combo", self._keys_input.text().strip())
        elif step_type == "open":
            put("app", self._open_input.text().strip())
        elif step_type == "wait":
            params["seconds"] = self._wait_spin.value()

        step = Step(type=step_type, params=params, name=self._name_input.text().strip())
        try:
            step.validate(0)
        except exceptions.AutomationError as error:
            QMessageBox.warning(self, "Invalid step", str(error))
            return
        self._step = step
        self.accept()

    def step(self) -> Optional[Step]:
        return self._step


# --------------------------------------------------------------- editor
class WorkflowEditorDialog(QDialog):
    """Create, edit, and run workflows."""

    def __init__(self, store: WorkflowStore, engine: WorkflowEngine, parent=None):
        super().__init__(parent)
        self.store = store
        self.engine = engine
        self.setWindowTitle("Workflows")
        self.resize(860, 560)
        self._selected_id: Optional[str] = None
        self._run_timer: Optional[QTimer] = None
        self._build_ui()
        self._reload()

    # ------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setSpacing(12)

        # left column: list + actions
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._workflow_list = QListWidget()
        self._workflow_list.setStyleSheet(
            "QListWidget { background-color: #1f1f1f; color: #e0e0e0; border: 1px solid #404040; "
            "border-radius: 4px; }"
            "QListWidget::item { padding: 6px; }"
            "QListWidget::item:selected { background-color: #2a82e4; color: white; }"
        )
        self._workflow_list.currentRowChanged.connect(self._on_selected)
        left_layout.addWidget(self._workflow_list, stretch=1)

        list_buttons = QHBoxLayout()
        self._new_button = QPushButton("New")
        self._dup_button = QPushButton("Duplicate")
        self._del_button = QPushButton("Delete")
        for button in (self._new_button, self._dup_button, self._del_button):
            button.setStyleSheet(_BUTTON_STYLE)
        self._new_button.clicked.connect(self._new_workflow)
        self._dup_button.clicked.connect(self._duplicate_workflow)
        self._del_button.clicked.connect(self._delete_workflow)
        list_buttons.addWidget(self._new_button)
        list_buttons.addWidget(self._dup_button)
        list_buttons.addWidget(self._del_button)
        left_layout.addLayout(list_buttons)

        self._enable_button = QPushButton("Toggle Enabled")
        self._enable_button.setStyleSheet(_BUTTON_STYLE)
        self._enable_button.clicked.connect(self._toggle_enabled)
        left_layout.addWidget(self._enable_button)

        self._run_button = QPushButton("Run Now")
        self._run_button.setStyleSheet(_PRIMARY_BUTTON_STYLE)
        self._run_button.clicked.connect(self._run_now)
        left_layout.addWidget(self._run_button)

        left.setFixedWidth(280)
        root.addWidget(left)

        # right column: form
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setSpacing(8)

        self._name_input = QLineEdit()
        self._name_input.setStyleSheet(_INPUT_STYLE)
        form.addRow(QLabel("Name:"), self._name_input)

        self._description_input = QLineEdit()
        self._description_input.setStyleSheet(_INPUT_STYLE)
        form.addRow(QLabel("Description:"), self._description_input)

        trigger_row = QHBoxLayout()
        self._trigger_input = QLineEdit()
        self._trigger_input.setStyleSheet(_INPUT_STYLE)
        self._trigger_input.setPlaceholderText("Speak this to activate, e.g. compose email to bob")
        self._trigger_type_combo = QComboBox()
        self._trigger_type_combo.setStyleSheet(_INPUT_STYLE)
        self._trigger_type_combo.addItems(["exact", "prefix", "regex"])
        trigger_row.addWidget(self._trigger_input, stretch=1)
        trigger_row.addWidget(self._trigger_type_combo)
        form.addRow(QLabel("Trigger:"), trigger_row)

        self._enabled_box = QCheckBox("Enabled")
        self._enabled_box.setStyleSheet("color: #e0e0e0;")
        form.addRow(self._enabled_box)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        self._status_label.setWordWrap(True)
        form.addRow(self._status_label)

        steps_label = QLabel("Steps (run in order)")
        steps_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        form.addRow(steps_label)

        self._steps_list = QListWidget()
        self._steps_list.setStyleSheet(
            "QListWidget { background-color: #1f1f1f; color: #e0e0e0; border: 1px solid #404040; "
            "border-radius: 4px; }"
        )
        form.addRow(self._steps_list)

        step_buttons = QHBoxLayout()
        self._step_add = QPushButton("Add")
        self._step_edit = QPushButton("Edit")
        self._step_remove = QPushButton("Remove")
        self._step_up = QPushButton("Up")
        self._step_down = QPushButton("Down")
        for button in (self._step_add, self._step_edit, self._step_remove, self._step_up, self._step_down):
            button.setStyleSheet(_BUTTON_STYLE)
        self._step_add.clicked.connect(lambda: self._add_or_edit_step(None))
        self._step_edit.clicked.connect(self._edit_selected_step)
        self._step_remove.clicked.connect(self._remove_selected_step)
        self._step_up.clicked.connect(lambda: self._move_selected_step(-1))
        self._step_down.clicked.connect(lambda: self._move_selected_step(1))
        step_buttons.addWidget(self._step_add)
        step_buttons.addWidget(self._step_edit)
        step_buttons.addWidget(self._step_remove)
        step_buttons.addStretch()
        step_buttons.addWidget(self._step_up)
        step_buttons.addWidget(self._step_down)
        form.addRow(step_buttons)

        right_layout.addLayout(form)
        right_layout.addStretch()

        bottom = QHBoxLayout()
        self._save_button = QPushButton("Save Workflow")
        self._save_button.setStyleSheet(_PRIMARY_BUTTON_STYLE)
        self._save_button.clicked.connect(self._save_current)
        bottom.addWidget(self._save_button)
        self._close_button = QPushButton("Close")
        self._close_button.setStyleSheet(_BUTTON_STYLE)
        self._close_button.clicked.connect(self.accept)
        bottom.addWidget(self._close_button)
        bottom.addStretch()
        right_layout.addLayout(bottom)

        root.addWidget(right, stretch=1)

    # --------------------------------------------------------- list ops
    def _reload(self) -> None:
        selected_before = self._selected_id
        self._workflow_list.clear()
        workflow = None
        for item in self.store.list_workflows():
            marker = "on" if item.enabled else "off"
            status = item.last_run_status or "never"
            text = f"{item.name}  [{marker}]  last: {status}"
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.ItemDataRole.UserRole, item.id)
            self._workflow_list.addItem(list_item)
            if item.id == selected_before:
                workflow = item
        if workflow is None and self._workflow_list.count():
            self._workflow_list.setCurrentRow(0)
        self._load_workflow(workflow if workflow else self._selected())

    def _selected(self) -> Optional[Workflow]:
        item = self._workflow_list.currentItem()
        if item is None:
            return None
        workflow_id = item.data(Qt.ItemDataRole.UserRole)
        return self.store.get_workflow(workflow_id)

    def _load_workflow(self, workflow: Optional[Workflow]) -> None:
        if workflow is None:
            self._selected_id = None
            self._name_input.clear()
            self._description_input.clear()
            self._trigger_input.clear()
            self._trigger_type_combo.setCurrentIndex(0)
            self._enabled_box.setChecked(True)
            self._status_label.setText("")
            self._steps_list.clear()
            return
        self._selected_id = workflow.id
        self._name_input.setText(workflow.name)
        self._description_input.setText(workflow.description)
        self._trigger_input.setText(workflow.trigger)
        self._trigger_type_combo.setCurrentIndex(
            max(0, self._trigger_type_combo.findText(workflow.trigger_type))
        )
        self._enabled_box.setChecked(workflow.enabled)
        status = workflow.last_run_status
        if status:
            self._status_label.setText(f"Last run: {status} — {workflow.last_run_message or ''}")
        else:
            self._status_label.setText("Never run.")
        self._refresh_steps(workflow.steps)

    def _refresh_steps(self, steps: List[Step]) -> None:
        self._steps_list.clear()
        for step in steps:
            summary = step.name or step.type
            params_preview = _step_summary(step)
            self._steps_list.addItem(f"{summary}  ({step.type}) — {params_preview}")

    # --------------------------------------------------------------- on save
    def _collect_form(self, existing: Workflow) -> Optional[Workflow]:
        existing.name = self._name_input.text().strip()
        existing.description = self._description_input.text().strip()
        existing.trigger = self._trigger_input.text().strip()
        existing.trigger_type = self._trigger_type_combo.currentText()
        existing.enabled = self._enabled_box.isChecked()
        try:
            existing.validate()
        except exceptions.AutomationError as error:
            QMessageBox.warning(self, "Invalid workflow", str(error))
            return None
        return existing

    def _save_current(self) -> Optional[Workflow]:
        current = self._selected()
        if current is None:
            QMessageBox.information(
                self, "No workflow", "Create a workflow with the New button first."
            )
            return None
        if self._collect_form(current) is None:
            return None
        self.store.save_workflow(current)
        self._reload()
        return current

    # ------------------------------------------------------------ actions
    def _new_workflow(self) -> None:
        workflow = Workflow(
            name="New workflow",
            trigger="",
            steps=[Step(type="prompt", name="output", params={"prompt": "Summarize {{text}} in one sentence."})],
        )
        self.store.save_workflow(workflow)
        self._reload()
        for row in range(self._workflow_list.count()):
            item = self._workflow_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == workflow.id:
                self._workflow_list.setCurrentRow(row)
                break

    def _duplicate_workflow(self) -> None:
        current = self._selected()
        if current is None:
            return
        import copy

        clone = Workflow.from_dict(copy.deepcopy(current.to_dict()))
        clone.id = ""
        clone.name = f"{clone.name} copy"
        self.store.save_workflow(clone)
        self._reload()

    def _delete_workflow(self) -> None:
        current = self._selected()
        if current is None:
            return
        reply = QMessageBox.question(
            self,
            "Delete workflow",
            f"Delete '{current.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.store.delete_workflow(current.id)
            self._selected_id = None
            self._reload()

    def _toggle_enabled(self) -> None:
        current = self._selected()
        if current is None:
            return
        current.enabled = not current.enabled
        self.store.save_workflow(current)
        self._reload()

    def _run_now(self) -> None:
        saved = self._save_current()
        if saved is None:
            return
        self._status_label.setText(f"Running '{saved.name}'...")
        future = self.engine.submit(saved, {"text": ""})
        self._start_run_poll(future)

    def _start_run_poll(self, future) -> None:
        if self._run_timer is not None:
            self._run_timer.stop()

        def poll():
            if not future.done():
                return
            self._run_timer.stop()
            run = future.result()
            current = self._selected()
            if current is not None:
                current.last_run_status = run.status
                current.last_run_message = run.error or run.output
                self.store.save_workflow(current)
            self._reload()
            self._status_label.setText(
                f"Run finished: {run.status} — {run.error or run.output or ''}"
            )

        self._run_timer = QTimer(self)
        self._run_timer.setInterval(200)
        self._run_timer.timeout.connect(poll)
        self._run_timer.start()

    # ------------------------------------------------------------- steps
    def _steps(self) -> List[Step]:
        current = self._selected()
        return list(current.steps) if current else []

    def _add_or_edit_step(self, step: Optional[Step]) -> None:
        current = self._selected()
        if current is None:
            return
        dialog = StepEditDialog(step=step, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        edited = dialog.step()
        if edited is None:
            return
        if step is None:
            current.steps.append(edited)
        else:
            for index, existing in enumerate(current.steps):
                if existing is step:
                    current.steps[index] = edited
                    break
        self.store.save_workflow(current)
        self._reload()

    def _edit_selected_step(self) -> None:
        current = self._selected()
        if current is None:
            return
        row = self._steps_list.currentRow()
        if row < 0 or row >= len(current.steps):
            return
        self._add_or_edit_step(current.steps[row])

    def _remove_selected_step(self) -> None:
        current = self._selected()
        if current is None:
            return
        row = self._steps_list.currentRow()
        if row < 0 or row >= len(current.steps):
            return
        del current.steps[row]
        self.store.save_workflow(current)
        self._reload()

    def _move_selected_step(self, delta: int) -> None:
        current = self._selected()
        if current is None:
            return
        row = self._steps_list.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= len(current.steps):
            return
        current.steps[row], current.steps[target] = current.steps[target], current.steps[row]
        self.store.save_workflow(current)
        self._reload()
        self._steps_list.setCurrentRow(target)

    def _on_selected(self, _row: int) -> None:
        self._load_workflow(self._selected())


def _step_summary(step: Step) -> str:
    if step.type == "prompt":
        return str(step.params.get("prompt", ""))[:60]
    if step.type == "shell":
        return str(step.params.get("command", ""))
    if step.type == "type":
        return str(step.params.get("text", ""))[:60]
    if step.type == "keys":
        return str(step.params.get("combo", ""))
    if step.type == "open":
        return str(step.params.get("app", ""))
    if step.type == "wait":
        return f"{step.params.get('seconds', 0)}s"
    return ""