from app.predictors.core import DeterministicImpactPredictor, DeterministicTestSelector, TransparentRiskPredictor
from app.service import ActionSimulator, AnalysisService
from app.store import store

def context(pr_id: str):
    pr=store.pull_request(pr_id); return store.repository(pr.repository_id),pr
def test_dependency_traversal_finds_two_hop_impact():
    repo,pr=context("pr-101"); nodes=DeterministicImpactPredictor().predict(repo,pr)
    assert "payments" in {n.module_id for n in nodes}
    assert next(n for n in nodes if n.module_id=="payments").dependency_path==["storefront","checkout","payments"]
def test_impact_scores_decay_with_distance():
    repo,pr=context("pr-101"); nodes={n.module_id:n for n in DeterministicImpactPredictor().predict(repo,pr)}
    assert nodes["storefront"].score>nodes["checkout"].score>nodes["payments"].score
def test_test_ranking_prioritizes_direct_mapping():
    repo,pr=context("pr-204"); impacts=DeterministicImpactPredictor().predict(repo,pr)
    tests,_=DeterministicTestSelector().select(repo,pr,impacts)
    top=next(test for test in repo.tests if test.id==tests[0].id)
    assert set(top.modules)&{f.module_id for f in pr.changed_files}
def test_critical_module_applies_conservative_fallback():
    repo,pr=context("pr-309"); impacts=DeterministicImpactPredictor().predict(repo,pr)
    tests,safety=DeterministicTestSelector().select(repo,pr,impacts)
    assert safety.fallback_applied and safety.level=="high"
    assert "database-integration" in {t.id for t in tests}
def test_risk_is_transparent_and_ranked():
    service=AnalysisService(); values=[]
    for pr_id in ("pr-101","pr-204","pr-309"):
        repo,pr=context(pr_id); result=service.analyze(repo,pr); values.append(result.risk_score)
        assert sum(f.contribution for f in result.risk_factors)>=result.risk_score-.2
    assert values[0]<values[1]<values[2]
def test_action_simulation_changes_recommendation_by_pr():
    service=AnalysisService(); simulator=ActionSimulator(); choices=[]
    for pr_id in ("pr-101","pr-204","pr-309"):
        repo,pr=context(pr_id); sim=simulator.simulate(service.analyze(repo,pr),pr)
        choices.append(next(r.action.id for r in sim.results if r.recommended))
        assert len(sim.results)==6
    assert len(set(choices))>=2
