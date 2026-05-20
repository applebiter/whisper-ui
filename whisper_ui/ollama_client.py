"""Ollama REST client and QThread worker for streamed text generation."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal


# ── Pure-Python helpers (no Qt) ───────────────────────────────────────────────

def test_connection(host: str) -> tuple[bool, str]:
    """Return (ok, message).  Tries GET {host}/api/version."""
    import requests
    try:
        r = requests.get(f"{host.rstrip('/')}/api/version", timeout=5)
        r.raise_for_status()
        version = r.json().get("version", "?")
        return True, f"Connected  —  Ollama {version}"
    except requests.exceptions.ConnectionError:
        return False, "Connection refused. Is Ollama running?"
    except requests.exceptions.Timeout:
        return False, "Timed out. Check the host address."
    except Exception as exc:
        return False, str(exc)


def list_models(host: str) -> list[str]:
    """Return model names available on the Ollama server."""
    import requests
    r = requests.get(f"{host.rstrip('/')}/api/tags", timeout=10)
    r.raise_for_status()
    return [m["name"] for m in r.json().get("models", [])]


# ── Streaming worker ──────────────────────────────────────────────────────────

class OllamaWorker(QThread):
    """Streams a generation request and forwards tokens to the GUI thread."""

    chunk_received = Signal(str)   # each streamed token / partial response
    finished = Signal(str)         # complete accumulated text when done
    error = Signal(str)

    def __init__(
        self,
        host: str,
        model: str,
        prompt: str,
        parent=None,
    ):
        super().__init__(parent)
        self.host = host.rstrip("/")
        self.model = model
        self.prompt = prompt

    def run(self):
        import json
        import requests

        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": self.prompt,
            "stream": True,
        }

        try:
            with requests.post(url, json=payload, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                accumulated = []
                for raw_line in resp.iter_lines():
                    if not raw_line:
                        continue
                    try:
                        obj = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    token = obj.get("response", "")
                    if token:
                        accumulated.append(token)
                        self.chunk_received.emit(token)
                    if obj.get("done"):
                        break
                self.finished.emit("".join(accumulated))

        except Exception as exc:
            self.error.emit(str(exc))
