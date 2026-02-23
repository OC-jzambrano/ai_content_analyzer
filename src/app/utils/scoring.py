from __future__ import annotations

from typing import Dict, List, Tuple

SAFE = "Safe"
WARNING = "Warning"
UNSAFE = "Unsafe"


# -----------------------------
# Threshold Configuration
# -----------------------------

VISUAL_SAFE_THRESHOLD = 90
VISUAL_WARNING_THRESHOLD = 70

TEXT_SAFE_THRESHOLD = 85
TEXT_WARNING_THRESHOLD = 70

STRICT_SAFE_THRESHOLD = 90  # Hate & Violence strict rule


# -----------------------------
# Category Weights
# -----------------------------

VISUAL_WEIGHTS: Dict[str, float] = {
    "Adult Content": 2.0,
    "Violence / Weapons": 2.0,
    "Racy Content": 1.0,
    "Medical / Gore": 1.0,
    "Spoof / Fake Content": 1.5,
}

TEXT_WEIGHTS: Dict[str, float] = {
    "Profanity": 1.0,
    "Hate Speech": 2.0,
    "Misinformation": 2.0,
    "Brand Mentions": 1.0,
    "Disclosure Compliance": 1.0,
    "Political Content": 1.0,
}


# -----------------------------
# Status Mapping
# -----------------------------

def visual_status(category: str, score: float) -> str:
    """
    Applies:
    - Standard visual thresholds
    - Strict rule for Violence
    - Spoof rule
    """

    if category == "Spoof / Fake Content":
        # Spoof must be flagged below 90
        return SAFE if score >= VISUAL_SAFE_THRESHOLD else WARNING

    if category == "Violence / Weapons":
        if score >= STRICT_SAFE_THRESHOLD:
            return SAFE
        if score >= VISUAL_WARNING_THRESHOLD:
            return WARNING
        return UNSAFE

    if score >= VISUAL_SAFE_THRESHOLD:
        return SAFE
    if score >= VISUAL_WARNING_THRESHOLD:
        return WARNING
    return UNSAFE


def text_status(category: str, score: float) -> str:
    """
    Applies:
    - Standard text thresholds
    - Strict rule for Hate Speech
    - Political non-blocking rule
    """

    if category == "Hate Speech":
        if score >= STRICT_SAFE_THRESHOLD:
            return SAFE
        if score >= TEXT_WARNING_THRESHOLD:
            return WARNING
        return UNSAFE

    if category == "Political Content":
        # Always labeled
        if score >= TEXT_SAFE_THRESHOLD:
            return SAFE
        if score >= TEXT_WARNING_THRESHOLD:
            return WARNING
        return UNSAFE  # <70 blocks

    if score >= TEXT_SAFE_THRESHOLD:
        return SAFE
    if score >= TEXT_WARNING_THRESHOLD:
        return WARNING
    return UNSAFE


# -----------------------------
# Weighted Aggregation
# -----------------------------

def weighted_average(categories: List[Tuple[str, float]], weights: Dict[str, float]) -> float:
    total_weight = 0.0
    weighted_sum = 0.0

    for category, score in categories:
        weight = weights.get(category, 1.0)
        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        return 100.0

    return weighted_sum / total_weight