"""First-run dictation setup."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class OnboardingDialog(QDialog):
    """Short setup flow that gets a user to the first dictation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set up AIOP dictation")
        self.setMinimumWidth(430)

        layout = QVBoxLayout(self)
        title = QLabel("Speak anywhere you can type.")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #e8eaed;")
        subtitle = QLabel(
            "AIOP listens only after you activate it and uses the local Whisper model "
            "to turn your words into text. No account is required."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #9aa0a6; margin-bottom: 10px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        steps = QLabel(
            "1. Focus a text field\n"
            "2. Press and hold Ctrl+Shift+Space\n"
            "3. Speak naturally\n"
            "4. Release the shortcut to finish"
        )
        steps.setStyleSheet("color: #d9dde3; line-height: 1.4; margin-bottom: 8px;")
        layout.addWidget(steps)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Name (optional)")
        layout.addWidget(self.name_input)

        self.email_input = QLineEdit()
        self.email_input.setVisible(False)

        self.ready_check = QCheckBox("I have a microphone connected and want to try a test dictation")
        self.ready_check.setChecked(True)
        layout.addWidget(self.ready_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Start dictating")
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def accept(self) -> None:
        if self.ready_check.isChecked():
            super().accept()