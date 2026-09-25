"""First-run profile setup."""

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout


class OnboardingDialog(QDialog):
    """Small local sign-up dialog shown only on first launch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to AIOP")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        title = QLabel("Your computer, with a voice.")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #e8eaed;")
        subtitle = QLabel("Create your local profile to get started. Your details stay on this device.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #9aa0a6; margin-bottom: 10px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Your name")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email address")
        layout.addWidget(self.name_input)
        layout.addWidget(self.email_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def accept(self) -> None:
        if self.name_input.text().strip() and self.email_input.text().strip():
            super().accept()