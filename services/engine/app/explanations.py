from __future__ import annotations

import json
import os
from typing import Any, Literal

from .models import EvidenceItem, ImpactedNode, PullRequest, RecommendedTest, WorkflowPrediction
from .predictors.core import TemplateExplanationProvider


class GroundedExplanationProvider:
    """Use OpenAI when configured; otherwise preserve the deterministic explanation path."""

    def __init__(self) -> None:
        self.fallback = TemplateExplanationProvider()
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")

    def render(
        self,
        pr: PullRequest,
        impacts: list[ImpactedNode],
        tests: list[RecommendedTest],
        risk: float,
        workflow: WorkflowPrediction,
        evidence: list[EvidenceItem],
    ) -> tuple[str, Literal["gpt-5.6", "deterministic-fallback"], str]:
        fallback = self.fallback.render(pr, impacts, tests, risk, workflow)
        if not os.getenv("OPENAI_API_KEY"):
            return fallback, "deterministic-fallback", "template-v1"

        pack: dict[str, Any] = {
            "change": {"files": len(pr.changed_files), "additions": pr.additions, "deletions": pr.deletions},
            "predictions": {
                "risk_score": risk,
                "impacts": [
                    {"evidence_id": f"impact-{index + 1}", "module": item.module_name, "path": item.dependency_path, "confidence": item.confidence}
                    for index, item in enumerate(impacts[:8])
                ],
                "tests": [
                    {"evidence_id": f"test-{index + 1}", "file": item.file, "reason": item.reason, "confidence": item.confidence}
                    for index, item in enumerate(tests[:8])
                ],
                "workflow": {"evidence_id": "workflow-1", "bottleneck": workflow.bottleneck, "time_to_green_minutes": workflow.time_to_green_minutes, "confidence": workflow.confidence},
            },
            "evidence": [
                {"evidence_id": f"evidence-{index + 1}", "label": item.label, "detail": item.detail, "source": item.source}
                for index, item in enumerate(evidence[:10])
            ],
        }
        try:
            from openai import OpenAI

            client = OpenAI(timeout=12.0, max_retries=1)
            response = client.responses.create(
                model=self.model,
                store=False,
                max_output_tokens=450,
                input=[
                    {"role": "system", "content": "Explain this deterministic consequence analysis in under 180 words. Ground every conclusion in the supplied evidence IDs and cite IDs inline in square brackets. Do not create, alter, or imply independent numerical predictions. State uncertainty plainly."},
                    {"role": "user", "content": json.dumps(pack, separators=(",", ":"))},
                ],
            )
            text = response.output_text.strip()
            if not text or "[" not in text:
                raise ValueError("Ungrounded explanation response")
            return text, "gpt-5.6", self.model
        except Exception:
            return fallback, "deterministic-fallback", "template-v1"
