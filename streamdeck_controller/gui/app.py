"""GUI-Einstieg mit Einzelinstanz-Schutz."""

import sys

from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .style import APP_STYLESHEET

INSTANCE_KEY = "streamdeck-controller-gui"


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Stream Deck Controller")
    app.setStyleSheet(APP_STYLESHEET)

    # Läuft schon eine GUI? Dann deren Fenster nach vorn holen.
    probe = QLocalSocket()
    probe.connectToServer(INSTANCE_KEY)
    if probe.waitForConnected(300):
        probe.write(b"show")
        probe.flush()
        probe.waitForBytesWritten(300)
        probe.disconnectFromServer()
        return 0

    QLocalServer.removeServer(INSTANCE_KEY)
    server = QLocalServer()
    server.listen(INSTANCE_KEY)

    window = MainWindow()

    def on_new_connection():
        conn = server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(200)
        window.show()
        window.raise_()
        window.activateWindow()

    server.newConnection.connect(on_new_connection)
    window.show()
    return app.exec()
