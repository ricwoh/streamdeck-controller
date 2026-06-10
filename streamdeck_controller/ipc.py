"""IPC zwischen Daemon, CLI und GUI über einen Unix-Socket (JSON pro Zeile)."""

import json
import logging
import socket
import threading

from .paths import SOCKET_PATH

log = logging.getLogger(__name__)


class IPCServer:
    def __init__(self, handler):
        """handler(request: dict) -> dict"""
        self._handler = handler
        self._sock: socket.socket | None = None
        self._running = False

    def start(self):
        SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
        SOCKET_PATH.unlink(missing_ok=True)
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(SOCKET_PATH))
        self._sock.listen(4)
        self._running = True
        thread = threading.Thread(target=self._serve, daemon=True, name="ipc-server")
        thread.start()

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        SOCKET_PATH.unlink(missing_ok=True)

    def _serve(self):
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket):
        try:
            conn.settimeout(5)
            data = b""
            while not data.endswith(b"\n"):
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            if not data:
                return
            request = json.loads(data.decode())
            response = self._handler(request) or {}
            conn.sendall((json.dumps(response) + "\n").encode())
        except Exception as e:
            log.debug("IPC-Fehler: %s", e)
        finally:
            conn.close()


def ipc_request(request: dict, timeout: float = 3.0) -> dict | None:
    """Anfrage an den laufenden Daemon. None, wenn keiner läuft."""
    if not SOCKET_PATH.exists():
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(SOCKET_PATH))
            sock.sendall((json.dumps(request) + "\n").encode())
            data = b""
            while not data.endswith(b"\n"):
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        return json.loads(data.decode()) if data else None
    except (OSError, json.JSONDecodeError):
        return None


def daemon_running() -> bool:
    response = ipc_request({"cmd": "ping"}, timeout=1.0)
    return bool(response and response.get("ok"))
