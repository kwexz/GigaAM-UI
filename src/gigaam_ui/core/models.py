"""Model catalog. Only verified revisions ship; add others after smoke tests."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    id: str  # revision on ai-sage/GigaAM-v3
    title: str
    description: str
    punctuated: bool


REPO = "ai-sage/GigaAM-v3"

CATALOG: dict[str, ModelInfo] = {
    "e2e_rnnt": ModelInfo(
        id="e2e_rnnt",
        title="GigaAM v3 E2E RNNT",
        description="Best quality with punctuation and text normalization.",
        punctuated=True,
    ),
}


def get(model_id: str) -> ModelInfo:
    try:
        return CATALOG[model_id]
    except KeyError:
        raise SystemExit(f"Unknown model: {model_id} (available: {sorted(CATALOG)})")
