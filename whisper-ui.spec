# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for WhisperUI.

Build (full, CUDA-capable):
    source .venv/bin/activate
    pyinstaller whisper-ui.spec --clean --noconfirm

Build (slim, CPU-only — much smaller):
    WHISPER_UI_SLIM=1 pyinstaller whisper-ui.spec --clean --noconfirm

Output: dist/whisper-ui/          (self-contained directory)
        dist/whisper-ui/whisper-ui (the launcher executable)
"""
import os
import site
import subprocess
from PyInstaller.utils.hooks import collect_data_files

SLIM = os.environ.get("WHISPER_UI_SLIM", "0") == "1"

# ── Data files ───────────────────────────────────────────────────────────────

datas = []

# Whisper runtime assets: mel filter banks, BPE tokeniser vocab, English normaliser
datas += collect_data_files("whisper")

# soundfile ships its own libsndfile — include the whole data directory
_sp = site.getsitepackages()[0]
_sfd = os.path.join(_sp, "_soundfile_data")
if os.path.isdir(_sfd):
    datas.append((_sfd, "_soundfile_data"))

# ── Binaries ─────────────────────────────────────────────────────────────────

binaries = []

# sounddevice uses PortAudio via ctypes.find_library; PyInstaller won't trace that
# automatically, so we locate it ourselves and add it explicitly.
try:
    _ldc = subprocess.run(["ldconfig", "-p"], capture_output=True, text=True)
    for _line in _ldc.stdout.splitlines():
        if "libportaudio.so" in _line and "=>" in _line:
            _pa = _line.split("=>")[1].strip()
            if os.path.isfile(_pa):
                binaries.append((_pa, "."))
                break
except Exception:
    pass  # PortAudio not found; recording will fail gracefully at runtime

# ── Hidden imports ────────────────────────────────────────────────────────────
# PyInstaller's static analysis misses imports that happen inside conditional
# blocks, string-based __import__ calls, and ctypes loads.

hiddenimports = [
    # whisper
    "whisper", "whisper.audio", "whisper.decoding", "whisper.model",
    "whisper.tokenizer", "whisper.transcribe", "whisper.utils",
    # tiktoken (used by whisper for tokenisation)
    "tiktoken", "tiktoken_ext", "tiktoken_ext.openai_public",
    "tiktoken.core", "tiktoken.load", "tiktoken.model", "tiktoken.registry",
    # regex (required by tiktoken)
    "regex",
    # numba — whisper/timing.py imports it unconditionally for DTW word-timestamps
    "numba", "numba.core", "numba.typed", "numba.np.ufunc",
    "llvmlite", "llvmlite.binding",
    # audio I/O
    "sounddevice", "soundfile", "_soundfile", "_cffi_backend",
    # HTTP (model download)
    "requests", "certifi", "charset_normalizer", "idna", "urllib3",
]

# ── Exclusions ────────────────────────────────────────────────────────────────

excludes = [
    # Other GUI toolkits we don't use
    "tkinter", "_tkinter", "PyQt5", "PyQt6", "wx",
    # Heavy unused packages
    "matplotlib", "scipy", "pandas", "PIL", "Pillow",
    "IPython", "jupyter", "notebook", "nbformat",
    "pytest", "doctest",
    # Triton JIT compiler (compile-time only; not needed for inference)
    "triton",
]

# ── Analysis ──────────────────────────────────────────────────────────────────

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

# Slim mode: strip out the pip-installed NVIDIA CUDA shared libraries.
# The bundle will use CPU only; CUDA is not available via system libraries either.
if SLIM:
    _cuda_strip = (
        "libcublas", "libcudnn", "libcufft", "libcurand",
        "libcusolver", "libcusparse", "libcupti", "libnccl",
        "libnvrtc", "libnvjitlink", "libnvshmem",
        "nvidia/", "nvidia_",
    )
    # libcudart must be kept even in a CPU-only build: libtorch_global_deps.so
    # has a hard ELF NEEDED entry for it and torch/__init__.py will fail to
    # import if it is missing — even when all actual computation runs on CPU.
    _cuda_keep = ("libcudart",)
    _before = len(a.binaries)
    a.binaries = [
        b for b in a.binaries
        if not any(pfx in b[0].lower() for pfx in _cuda_strip)
        or any(k in b[0].lower() for k in _cuda_keep)
    ]
    print(f"[slim] removed {_before - len(a.binaries)} CUDA binaries (kept libcudart)")

# ── Package ───────────────────────────────────────────────────────────────────

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="whisper-ui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,       # set True if you have UPX installed: sudo apt install upx-ucl
    console=True,    # needed for CLI output; causes no extra window on Linux
    icon="icon.png" if os.path.isfile("icon.png") else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="whisper-ui",
)
