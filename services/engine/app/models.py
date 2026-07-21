from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

class Module(BaseModel):
    id: str; name: str; path: str; criticality: float; owner: str; shared: bool = False
class DependencyEdge(BaseModel):
    from_module: str; to_module: str
class TestFile(BaseModel):
    id: str; file: str; type: Literal["unit","integration","e2e"]; duration_seconds: int
    modules: list[str]; failure_associations: dict[str,float]
class Repository(BaseModel):
    id: str; name: str; owner: str; default_branch: str; language: str
    modules: list[Module]; dependency_edges: list[DependencyEdge]; tests: list[TestFile]
    full_suite_duration_seconds: int
class ChangedFile(BaseModel):
    path: str; module_id: str; additions: int; deletions: int; summary: str
class WorkflowEvent(BaseModel):
    kind: str; timestamp: str; detail: str
class GroundTruth(BaseModel):
    impacted_modules: list[str]; affected_tests: list[str]; failing_tests: list[str]
    time_to_green_minutes: float
class PullRequest(BaseModel):
    id: str; repository_id: str; number: int; title: str; description: str; author: str
    changed_files: list[ChangedFile]; additions: int; deletions: int; commits: int
    labels: list[str]; opened_at: str; workflow_events: list[WorkflowEvent]; ci_state: str
    historical_failure_rate: float; workflow_instability: float; reviewers: list[str]
    ground_truth: GroundTruth; diff_summary: str
class ImpactedNode(BaseModel):
    module_id: str; module_name: str; score: float; confidence: float
    dependency_path: list[str]; supporting_files: list[str]
class RecommendedTest(BaseModel):
    id: str; file: str; type: str; duration_seconds: int; score: float; reason: str; confidence: float
class SafetyAssessment(BaseModel):
    level: Literal["low","moderate","high"]; warning: str; fallback_applied: bool
class RiskFactor(BaseModel):
    name: str; contribution: float; evidence: str
class WorkflowPrediction(BaseModel):
    time_to_green_minutes: float; bottleneck: str; rerun_probability: float
    review_delay_minutes: float; confidence: float; timeline: list[str]
class EvidenceItem(BaseModel):
    label: str; detail: str; source: str
class AnalysisResult(BaseModel):
    pull_request_id: str; impacted_nodes: list[ImpactedNode]; dependency_paths: list[list[str]]
    recommended_tests: list[RecommendedTest]; estimated_test_duration_seconds: int
    expected_full_suite_duration_seconds: int; missed_test_safety: SafetyAssessment
    risk_score: float = Field(ge=0,le=100); risk_band: str; risk_factors: list[RiskFactor]
    confidence: float; workflow: WorkflowPrediction; evidence_pack: list[EvidenceItem]
    model_version: str; explanation: str
    explanation_provider: Literal["gpt-5.6", "deterministic-fallback"]
    explanation_model: str
ActionId = Literal["recommended_subset","full_suite","additional_reviewer","split_pr","rerun_flaky","none"]
class CandidateAction(BaseModel):
    id: ActionId
    label: str
class ActionSimulationResult(BaseModel):
    action: CandidateAction; predicted_risk_after: float; predicted_time_to_green_after: float
    estimated_ci_minutes: float; estimated_delay_reduction: float; explanation: str
    assumptions: list[str]; confidence: float; objective_score: float; recommended: bool = False
class SimulationResponse(BaseModel):
    pull_request_id: str; baseline_risk: float; baseline_time_to_green: float
    results: list[ActionSimulationResult]
class RepositorySummary(BaseModel):
    id: str; name: str; owner: str; language: str; module_count: int
class PullRequestSummary(BaseModel):
    id: str; number: int; title: str; author: str; additions: int; deletions: int
    ci_state: str; preview_band: str

class Capability(BaseModel):
    name: str; status: Literal["available", "partial", "unavailable"]; detail: str
class GitRef(BaseModel):
    name: str; commit: str; label: str
class UploadInspection(BaseModel):
    inspection_id: str; valid: bool; source: Literal["git_bundle", "project_diff", "github_pr"]
    repository_name: str; detected_language: str; project_type: str
    refs: list[GitRef] = []; default_base: str | None = None; default_head: str | None = None
    changed_files: list[str] = []; additions: int = 0; deletions: int = 0
    capabilities: list[Capability]; warnings: list[str] = []; validation_errors: list[str] = []
class AnalysisMetadata(BaseModel):
    source_label: str; repository_name: str; base: str; head: str; change_label: str
    detected_language: str; changed_files: int; additions: int; deletions: int
    capability_level: Literal["full", "partial", "structural"]; analyzed_at: str
    source_url: str | None = None; limitations: list[str]
class UserAnalysisResponse(BaseModel):
    metadata: AnalysisMetadata; observed: list[EvidenceItem]; predicted: AnalysisResult
    suggested: SimulationResponse
class GitHubRequest(BaseModel):
    url: str
