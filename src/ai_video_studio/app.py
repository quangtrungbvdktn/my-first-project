from PySide6.QtWidgets import QApplication


def build_app(argv: list[str]) -> QApplication:
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(argv)
    app.setApplicationName("AI Video Translator & Dubbing Studio")
    app.setOrganizationName("AI Video Studio")
    return app
