"""Installable components: UI/engine packs come with the installer,
heavy artifacts (torch, models, ffmpeg) download on first run."""
import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Component:
    id: str  # e.g. engine-cpu, model-gigaam-v3, ffmpeg
    title: str  # human-readable, shown in setup UI
    description: str  # one line: what it is and why it is needed
    version: str
    url: str
    sha256: str
    size: int  # bytes, 0 if unknown
    files: tuple = ()  # relative paths the archive must contain


@dataclass
class Manifest:
    version: int = 1
    components: tuple = field(default_factory=tuple)

    @staticmethod
    def from_dict(data: dict) -> "Manifest":
        try:
            comps = tuple(Component(**c) for c in data.get("components", []))
        except TypeError as e:
            raise ValueError(f"bad manifest: {e}") from e
        return Manifest(version=data.get("version", 1), components=comps)

    @staticmethod
    def from_json(text: str) -> "Manifest":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"bad manifest json: {e}") from e
        if not isinstance(data, dict):
            raise ValueError("bad manifest: top level must be an object")
        return Manifest.from_dict(data)

    def get(self, component_id: str) -> Component:
        for c in self.components:
            if c.id == component_id:
                return c
        raise KeyError(f"unknown component: {component_id}")
