"""Background thread that downloads a whisper model with progress reporting."""

from PyQt6.QtCore import QThread, pyqtSignal

from ..core import exceptions, logging

logger = logging.get_logger(__name__)


class ModelDownloadWorker(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(bool, str)

    def __init__(self, manager, model_name: str):
        super().__init__()
        self._manager = manager
        self._model_name = model_name
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        ok = False
        message = ""
        try:
            def on_progress(downloaded: int, total: int) -> None:
                # Raising unwinds download_model(), which discards the .part
                # file, so a cancelled run cannot leave a partial model behind.
                if self._cancelled:
                    raise exceptions.SpeechError("Download cancelled")
                self.progress.emit(downloaded, total)

            ok = self._manager.download_model(self._model_name, on_progress)
            if not ok:
                message = f'"{self._model_name}" could not be downloaded. Check your connection and try again.'
        except Exception as error:
            logger.debug("Model download failed: %s", error)
            message = f'Could not download "{self._model_name}": {error}'
        self.finished.emit(ok, message)