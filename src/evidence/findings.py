"""Structured security evidence produced by detectors in ``src/evidence/``.

A ``SecurityFinding`` is the auditable output of one detector run over one
piece of already-extracted data (a string, a Binwalk description line). It
is never itself a verdict — just an observation with enough context for
manual review. Detectors also expose flat counts/flags derived from these
findings (see ``findings_to_counts`` in ``src/evidence/patterns.py``) for
consumption as classifier features.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityFinding:
    """One structured, auditable security observation.

    Attributes:
        type: Category of the finding (e.g. "credential_candidate").
        source: The original string/description that triggered the match.
        context: Short human-readable explanation of what matched and why.
        confidence: "low" | "medium" | "high" — how reliable the signal is.
        detector: Name of the detector that produced this finding.
        detector_version: Version tag of the detector, for reproducibility.
    """

    type: str
    source: str
    context: str
    confidence: str
    detector: str
    detector_version: str
