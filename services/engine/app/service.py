from .models import *
from .predictors.core import DeterministicImpactPredictor, DeterministicTestSelector, TransparentRiskPredictor, WorkflowPredictor
from .explanations import GroundedExplanationProvider

class AnalysisService:
    def __init__(self) -> None:
        self.impact=DeterministicImpactPredictor(); self.tests=DeterministicTestSelector()
        self.risk=TransparentRiskPredictor(); self.workflow=WorkflowPredictor(); self.explanations=GroundedExplanationProvider()
    def analyze(self, repo: Repository, pr: PullRequest) -> AnalysisResult:
        impacts=self.impact.predict(repo,pr); tests,safety=self.tests.select(repo,pr,impacts)
        risk,factors=self.risk.predict(repo,pr,impacts,tests); duration=sum(t.duration_seconds for t in tests)
        workflow=self.workflow.predict(pr,risk,duration); band="low" if risk<35 else "medium" if risk<65 else "high"
        evidence=[EvidenceItem(label="Change surface",detail=f"{len(pr.changed_files)} files, +{pr.additions} / -{pr.deletions}",source="Synthetic PR fixture"),EvidenceItem(label="Dependency graph",detail=f"{len(impacts)} reachable modules across two hops",source="Repository fixture"),EvidenceItem(label="CI history",detail=f"{pr.historical_failure_rate:.0%} historical failure association",source="Synthetic workflow history")]
        explanation,provider,explanation_model=self.explanations.render(pr,impacts,tests,risk,workflow,evidence)
        return AnalysisResult(pull_request_id=pr.id,impacted_nodes=impacts,dependency_paths=[i.dependency_path for i in impacts if len(i.dependency_path)>1],recommended_tests=tests,estimated_test_duration_seconds=duration,expected_full_suite_duration_seconds=repo.full_suite_duration_seconds,missed_test_safety=safety,risk_score=risk,risk_band=band,risk_factors=factors,confidence=round(min(.94,.76+len(tests)*.02-pr.workflow_instability*.1),2),workflow=workflow,evidence_pack=evidence,model_version="deterministic-baseline/1.0",explanation=explanation,explanation_provider=provider,explanation_model=explanation_model)

ACTION_LABELS: dict[ActionId,str]={"recommended_subset":"Run recommended subset","full_suite":"Run full test suite","additional_reviewer":"Request an additional reviewer","split_pr":"Split the PR","rerun_flaky":"Rerun suspected flaky job","none":"Make no intervention"}
OBJECTIVE_WEIGHTS={"risk":.48,"time":.32,"ci":.12,"uncertainty":.08}
class ActionSimulator:
    def simulate(self, analysis: AnalysisResult, pr: PullRequest) -> SimulationResponse:
        flaky=any("flaky" in e.detail.lower() for e in pr.workflow_events); large=pr.additions+pr.deletions>250 or len(pr.changed_files)>=4
        adjustments: dict[ActionId,tuple[float,float,float,float,str]]={
          "recommended_subset":(-5,-analysis.workflow.time_to_green_minutes*.12,analysis.estimated_test_duration_seconds/60,.04,"Fast targeted feedback reduces uncertainty early."),
          "full_suite":(-10,analysis.expected_full_suite_duration_seconds/60,analysis.expected_full_suite_duration_seconds/60,-.06,"Broader coverage lowers residual test risk but costs CI time."),
          "additional_reviewer":(-7 if analysis.risk_score>=40 else -2,-8 if analysis.risk_score>=40 else 4,0,.02,"Another domain reviewer reduces review and ownership uncertainty, with a small coordination cost."),
          "split_pr":(-16 if large else -2,-18 if large else 14,analysis.estimated_test_duration_seconds/120,.05,"Smaller review units reduce technical coupling and review load."),
          "rerun_flaky":(-4,-14 if flaky else 7,analysis.estimated_test_duration_seconds/60,.10,"A rerun is useful only when failure evidence suggests flakiness."),
          "none":(2,8,0,.12,"No intervention preserves CI cost but leaves current uncertainty unresolved.")}
        results=[]
        for key,(risk_delta,time_delta,ci,uncertainty,why) in adjustments.items():
            risk=max(0,analysis.risk_score+risk_delta); eta=max(3,analysis.workflow.time_to_green_minutes+time_delta)
            objective=OBJECTIVE_WEIGHTS["risk"]*risk+OBJECTIVE_WEIGHTS["time"]*min(100,eta/2)+OBJECTIVE_WEIGHTS["ci"]*min(100,ci*2)+OBJECTIVE_WEIGHTS["uncertainty"]*uncertainty*100
            applicable=not (key=="rerun_flaky" and not flaky)
            if not applicable: objective+=18
            assumptions=["Predictions use synthetic fixture history",f"Objective weights: risk {OBJECTIVE_WEIGHTS['risk']:.0%}, time {OBJECTIVE_WEIGHTS['time']:.0%}, CI {OBJECTIVE_WEIGHTS['ci']:.0%}, uncertainty {OBJECTIVE_WEIGHTS['uncertainty']:.0%}"]
            if key=="rerun_flaky": assumptions.append("A workflow event identifies a flaky job" if flaky else "No flaky-job evidence is present")
            results.append(ActionSimulationResult(action=CandidateAction(id=key,label=ACTION_LABELS[key]),predicted_risk_after=round(risk,1),predicted_time_to_green_after=round(eta,1),estimated_ci_minutes=round(ci,1),estimated_delay_reduction=round(analysis.workflow.time_to_green_minutes-eta,1),explanation=why,assumptions=assumptions,confidence=round(max(.55,analysis.confidence-uncertainty),2),objective_score=round(objective,1)))
        best=min(results,key=lambda r:r.objective_score); best.recommended=True
        return SimulationResponse(pull_request_id=pr.id,baseline_risk=analysis.risk_score,baseline_time_to_green=analysis.workflow.time_to_green_minutes,results=sorted(results,key=lambda r:r.objective_score))
