from __future__ import annotations
from abc import ABC, abstractmethod
from collections import deque
from ..models import *

class ImpactPredictor(ABC):
    @abstractmethod
    def predict(self, repo: Repository, pr: PullRequest) -> list[ImpactedNode]: ...
class TestSelector(ABC):
    @abstractmethod
    def select(self, repo: Repository, pr: PullRequest, impacts: list[ImpactedNode]) -> tuple[list[RecommendedTest], SafetyAssessment]: ...
class RiskPredictor(ABC):
    @abstractmethod
    def predict(self, repo: Repository, pr: PullRequest, impacts: list[ImpactedNode], tests: list[RecommendedTest]) -> tuple[float,list[RiskFactor]]: ...

class DeterministicImpactPredictor(ImpactPredictor):
    """Traverse both callers and dependencies: a changed contract can affect either direction."""
    def predict(self, repo: Repository, pr: PullRequest) -> list[ImpactedNode]:
        graph: dict[str,set[str]] = {m.id:set() for m in repo.modules}
        for e in repo.dependency_edges:
            graph[e.from_module].add(e.to_module); graph[e.to_module].add(e.from_module)
        changed = {f.module_id for f in pr.changed_files}; best: dict[str,tuple[float,list[str]]] = {}
        queue: deque[tuple[str,float,list[str],int]] = deque((m,1.0,[m],0) for m in changed)
        while queue:
            node, score, path, depth = queue.popleft()
            module = next(m for m in repo.modules if m.id == node)
            weighted = min(1.0, score * (1.15 if module.shared else 1.0))
            if node in best and best[node][0] >= weighted: continue
            best[node] = (weighted,path)
            if depth < 2:
                for nxt in graph[node]: queue.append((nxt,score*0.62,path+[nxt],depth+1))
        modules = {m.id:m for m in repo.modules}
        return sorted([ImpactedNode(module_id=k,module_name=modules[k].name,score=round(v[0]*100,1),confidence=round(0.92-0.12*(len(v[1])-1),2),dependency_path=v[1],supporting_files=[f.path for f in pr.changed_files if f.module_id in v[1]]) for k,v in best.items()],key=lambda x:x.score,reverse=True)

class DeterministicTestSelector(TestSelector):
    def select(self, repo: Repository, pr: PullRequest, impacts: list[ImpactedNode]) -> tuple[list[RecommendedTest],SafetyAssessment]:
        scores = {i.module_id:i.score/100 for i in impacts}; changed={f.module_id for f in pr.changed_files}
        critical = any(m.id in changed and (m.shared or m.criticality >= .95) for m in repo.modules)
        ranked=[]
        for test in repo.tests:
            direct=len(set(test.modules)&changed)/len(test.modules)
            impact=max((scores.get(m,0.0) for m in test.modules),default=0.0)
            history=max((test.failure_associations.get(m,0.0) for m in scores),default=0.0)
            type_weight={"unit":.08,"integration":.14,"e2e":.10}[test.type]
            score=.48*direct+.27*impact+.2*history+type_weight-.00012*test.duration_seconds
            if score >= .37 or (critical and any(m in scores for m in test.modules)):
                reason = "Directly covers a changed module" if direct else "Covers a dependency in the predicted blast radius"
                if history >= .5: reason += f"; historical failure association {history:.0%}"
                ranked.append(RecommendedTest(id=test.id,file=test.file,type=test.type,duration_seconds=test.duration_seconds,score=round(min(1.0,score)*100,1),reason=reason,confidence=round(min(.96,.65+score*.28),2)))
        ranked.sort(key=lambda x:x.score,reverse=True)
        warning = "Critical shared infrastructure changed; conservative integration coverage is included." if critical else "Subset omits low-signal tests; run the full suite before merge if uncertainty changes."
        return ranked, SafetyAssessment(level="high" if critical else "moderate" if len(changed)>1 else "low",warning=warning,fallback_applied=critical)

class TransparentRiskPredictor(RiskPredictor):
    def predict(self, repo: Repository, pr: PullRequest, impacts: list[ImpactedNode], tests: list[RecommendedTest]) -> tuple[float,list[RiskFactor]]:
        changed={f.module_id for f in pr.changed_files}; mods={m.id:m for m in repo.modules}; churn=pr.additions+pr.deletions
        values=[("Change surface",min(14.0,len(pr.changed_files)*3.0+churn/80),f"{len(pr.changed_files)} files and {churn} changed lines"),("Module criticality",max(mods[m].criticality for m in changed)*22,f"Highest touched criticality is {max(mods[m].criticality for m in changed):.0%}"),("Dependency fan-out",min(18.0,max(0,len(impacts)-len(changed))*3.2),f"{len(impacts)} modules in the predicted radius"),("Cross-module scope",min(14.0,max(0,len(changed)-1)*6),f"Touches {len(changed)} module boundaries"),("Historical failures",pr.historical_failure_rate*18,f"Similar areas fail CI {pr.historical_failure_rate:.0%} of the time"),("Workflow instability",pr.workflow_instability*14,f"Workflow instability index is {pr.workflow_instability:.0%}"),("Coverage uncertainty",max(0,10-len(tests)*1.5),f"{len(tests)} tests selected")]
        factors=[RiskFactor(name=n,contribution=round(v,1),evidence=e) for n,v,e in values]
        return round(min(100,sum(v for _,v,_ in values)),1),factors

class WorkflowPredictor:
    def predict(self, pr: PullRequest, risk: float, test_seconds: int) -> WorkflowPrediction:
        review=4+pr.commits*3+len(pr.changed_files)*2; rerun=min(.82,.04+pr.historical_failure_rate*.8+pr.workflow_instability*.45)
        eta=5+test_seconds/60+review+risk*.52+rerun*24
        bottleneck="database integration and migration review" if "database" in {f.module_id for f in pr.changed_files} else "cross-module review" if len(pr.changed_files)>1 else "CI feedback"
        return WorkflowPrediction(time_to_green_minutes=round(eta,1),bottleneck=bottleneck,rerun_probability=round(rerun,2),review_delay_minutes=round(review,1),confidence=round(.86-pr.workflow_instability*.2,2),timeline=["Changes queued","Recommended checks complete",f"{bottleneck.title()} resolved","Green candidate"])

class ExplanationProvider(ABC):
    @abstractmethod
    def render(self, pr: PullRequest, impacts: list[ImpactedNode], tests: list[RecommendedTest], risk: float, workflow: WorkflowPrediction) -> str: ...
class TemplateExplanationProvider(ExplanationProvider):
    def render(self, pr: PullRequest, impacts: list[ImpactedNode], tests: list[RecommendedTest], risk: float, workflow: WorkflowPrediction) -> str:
        top=", ".join(i.module_name for i in impacts[:3]); band="low" if risk<35 else "medium" if risk<65 else "high"
        return f"This is a {band}-risk change because {len(pr.changed_files)} changed files propagate into {top}. The {len(tests)} recommended checks concentrate on direct coverage and historically sensitive dependencies. Expect about {workflow.time_to_green_minutes:.0f} minutes to green; the most likely constraint is {workflow.bottleneck}. These are fixture-based baseline estimates, not production measurements."
