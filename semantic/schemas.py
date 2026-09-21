"""Pydantic contracts for the semantic mapper's output.

The mapper's job is narrow: look at a page snapshot and point at interactions
that *look like* persistent user-controlled state. It never judges correctness.
"This is worth testing for persistence" is in scope; "this is broken" is not —
that verdict belongs to the knowledge engine, after the runner has actually
exercised the page.

These models are provider-neutral. Nothing here imports an LLM SDK.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class InteractionType(str, Enum):
    """Kinds of interaction the system knows how to test.

    Only one member today. Keeping it an enum means the model cannot invent a
    category the knowledge engine has no invariants for.
    """

    PERSISTENT_MUTATION = "persistent_mutation"


class SignalType(str, Enum):
    """How a page tells the user a commit succeeded."""

    TEXT = "text"              # a toast/banner appears — match expected_pattern
    ELEMENT = "element"        # a specific element appears — see element_id
    VALUE_RETAINED = "value_retained"  # no explicit signal; the value just sticks
    URL = "url"                # navigation/redirect — match expected_pattern


class SuccessSignal(BaseModel):
    """What the runner should watch for after triggering the commit action.

    Optional fields carry no defaults on purpose: the model must emit them
    explicitly as null. That keeps every property in the JSON Schema's
    `required` list, which strict structured-output modes demand.
    """

    model_config = ConfigDict(extra="forbid")

    type: SignalType
    expected_pattern: str | None = Field(
        description="Case-insensitive substring to look for. Required for "
        "'text' and 'url' signals; null otherwise."
    )
    element_id: str | None = Field(
        description="Element id from the snapshot (e.g. 'e7') expected to "
        "appear. Required for 'element' signals; null otherwise."
    )

    def is_coherent(self) -> bool:
        """Whether this signal carries the payload its own type needs."""
        if self.type in (SignalType.TEXT, SignalType.URL):
            return bool(self.expected_pattern)
        if self.type is SignalType.ELEMENT:
            return bool(self.element_id)
        return True  # VALUE_RETAINED needs nothing


class PersistentMutationCandidate(BaseModel):
    """One interaction that appears to represent persistent user state."""

    model_config = ConfigDict(extra="forbid")

    interaction_type: Literal[InteractionType.PERSISTENT_MUTATION]

    field_id: str = Field(description="Snapshot id of the editable field.")

    commit_action_id: str | None = Field(
        description="Snapshot id of the control that commits the change "
        "(usually a Save button). Null when the field appears to autosave — "
        "say so in reasoning_summary."
    )

    success_signal: SuccessSignal | None = Field(
        description="How the page appears to confirm the commit, or null if "
        "no confirmation is discernible from the snapshot."
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="0-1. How strongly the snapshot suggests this is "
        "persistent state — NOT how likely it is to be broken.",
    )

    reasoning_summary: str = Field(
        max_length=400,
        description="One or two sentences on what in the snapshot supports "
        "this reading. Describe evidence, not defects.",
    )


class CandidateSet(BaseModel):
    """Top-level object the model returns."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[PersistentMutationCandidate]


class RejectedCandidate(BaseModel):
    """A candidate dropped during reference checking, kept for reporting.

    Schema validation proves the shape is right; it cannot prove `field_id`
    names an element that exists and is editable. These are the ones that
    passed Pydantic and still failed that check.
    """

    candidate: PersistentMutationCandidate
    reason: str


class ClassificationResult(BaseModel):
    """What `semantic.classifier.classify()` hands back."""

    url: str
    model: str
    candidates: list[PersistentMutationCandidate]
    rejected: list[RejectedCandidate]


# JSON Schema keywords the strict structured-output modes of most providers
# reject. We keep them on the Pydantic models — they still validate the parsed
# response client-side — and strip them from the schema we hand to the LLM.
_UNSUPPORTED_SCHEMA_KEYWORDS = frozenset({
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minLength", "maxLength", "pattern", "minItems", "maxItems", "uniqueItems",
    "minProperties", "maxProperties",
})


def _strip_unsupported(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            k: _strip_unsupported(v)
            for k, v in node.items()
            if k not in _UNSUPPORTED_SCHEMA_KEYWORDS
        }
    if isinstance(node, list):
        return [_strip_unsupported(item) for item in node]
    return node


def candidate_set_schema() -> dict:
    """JSON Schema for `CandidateSet`, safe for strict structured outputs.

    Constraints like `confidence`'s 0-1 bound are removed here and enforced
    when the response is parsed instead, so an out-of-range value becomes a
    validation error rather than a schema-compilation error.
    """
    return _strip_unsupported(CandidateSet.model_json_schema())
