"""Thin adapter between DILARA services and the existing experimental KOD8 engine.

This intentionally does not reimplement or rename KOD8's CL1-CL8 pipeline.
The engine is loaded from KOD8_ENC/kod8_engine.py only when the adapter is used.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
from types import ModuleType

APP_DIR = Path(__file__).resolve().parents[1]
ENGINE_PATH = APP_DIR / "KOD8_ENC" / "kod8_engine.py"

class Kod8Unavailable(RuntimeError):
    pass

class Kod8Adapter:
    def __init__(self, engine_path: Path = ENGINE_PATH):
        self.engine_path = Path(engine_path)
        self._engine: ModuleType | None = None

    def _load(self) -> ModuleType:
        if self._engine is not None:
            return self._engine
        if not self.engine_path.is_file():
            raise Kod8Unavailable(f"KOD8 engine not found: {self.engine_path}")
        spec = importlib.util.spec_from_file_location("dilara_kod8_engine", self.engine_path)
        if spec is None or spec.loader is None:
            raise Kod8Unavailable("Could not load KOD8 engine module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._engine = module
        return module

    def encrypt_text(self, text: str, strategy_id: str = "CL1") -> tuple[str, str]:
        engine = self._load()
        if strategy_id not in engine.CIPHER_LISTS:
            raise ValueError(f"Unknown KOD8 strategy: {strategy_id}")
        cid, ciphertext, _history = engine.run_kod8_pipeline(
            text, encrypt=True, list_id=strategy_id
        )
        return cid, ciphertext

    def decrypt_text(self, ciphertext: str, strategy_id: str) -> str:
        engine = self._load()
        cid, plaintext, _history = engine.run_kod8_pipeline(
            ciphertext, encrypt=False, list_id=strategy_id
        )
        return plaintext
