"""First-run speech model download.

The packaged app ships no weights, so the default model is fetched on first
launch. The download runs on a worker thread, reports progress through Qt
signals and writes to a `.part` file until the checksum verifies.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ..core import logging, utils
from .model_download_worker import ModelDownloadWorker

logger = logging.get_logger(__name__)


class ModelDownloadDialog(QDialog):
    """Modal progress dialog that blocks startup until a model is ready."""

    def __init__(self, model_name: str, file_size: int = 0, parent=None):
        super().__init__(parent)
        self._model_name = model_name
        self._size_hint = file_size
        self._user_cancelled = False
        self._worker = None

        self.setWindowTitle("Getting your speech model ready")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        self._status = QLabel(self._heading())
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.clicked.connect(self._on_cancel)
        buttons.addWidget(self._cancel_button)
        layout.addLayout(buttons)

        self._start()

    def _heading(self) -> str:
        size = utils.format_bytes(self._size_hint) if self._size_hint else ""
        return f"Downloading the \"{self._model_name}\" speech model{(' (' + size + ')') if size else ''}…"

    def _start(self) -> None:
        from ..speech.model_manager import get_model_manager

        self._worker = ModelDownloadWorker(get_model_manager(), self._model_name)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self._progress.setMaximum(total)
            self._progress.setValue(downloaded)
            percent = int(100.0 * downloaded / total)
            self._status.setText(f"Downloading \"{self._model_name}\"… {utils.format_bytes(downloaded)} / {utils.format_bytes(total)} ({percent}%)")
        else:
            self._status.setText(f"Downloading \"{self._model_name}\"… {utils.format_bytes(downloaded)}")

    def _on_finished(self, ok: bool, message: str) -> None:
        if self._user_cancelled:
            return
        if ok:
            self._status.setText(f"\"{self._model_name}\" is ready. Starting up…")
            self.accept()
            return
        self._status.setText(message or "The download failed.")
        self._cancel_button.setText("Close")
        self._progress.setValue(self._progress.maximum())
        self._reset_worker()

    def _reset_worker(self) -> None:
        self._worker = None

    def _on_cancel(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._user_cancelled = True
            self._worker.cancel()
        self.reject()


def ensure_model_ready(parent=None) -> bool:
    """Ensure the configured default model exists before the UI starts.

    Returns immediately when a model file already resolves (bundled, existing
    install, or already downloaded), downloads it with a progress dialog on
    first run, and never raises.
    """
    from ..core import config
    from ..speech.model_manager import get_model_manager, resolve_model_path

    manager = get_model_manager()
    configured = getattr(getattr(config.get_config(), "speech", None), "model_path", None)
    if resolve_model_path(configured):
        return True

    name = default_model_name()
    if not manager.get_model(name):
        name = "base.en"
    if not manager.get_model(name):
        logger.warning("No downloadable model named '%s'", name)
        return True
    if manager.is_model_downloaded(name):
        return True

    model = manager.get_model(name)
    dialog = ModelDownloadDialog(model_name=name, file_size=model.file_size, parent=parent)
    return dialog.exec() == QDialog.DialogCode.Accepted


def default_model_name() -> str:
    """Map the configured speech.model_path to a downloadable model name."""
    from ..core import config

    value = config.get_config().speech.model_path or "base.en"
    name = str(value).replace("\\", "/").rsplit("/", 1)[-1]
    if name.endswith(".bin"):
        name = name[:-4]
    if name.startswith("ggml-"):
        name = name[5:]
    return name or "base.en"