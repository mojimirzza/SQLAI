from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Document:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


class VectorStorePort(Protocol):
    def search(self, query: str, top_k: int = 3) -> list[Document]: ...
