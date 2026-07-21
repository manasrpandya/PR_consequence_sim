from statistics import mean
from .service import AnalysisService
from .store import store
def metrics(pred: set[str], actual: set[str]) -> tuple[float,float,float]:
    tp=len(pred&actual); precision=tp/len(pred) if pred else 0; recall=tp/len(actual) if actual else 1
    return precision,recall,2*precision*recall/(precision+recall) if precision+recall else 0
def main() -> None:
    service=AnalysisService(); module_scores=[]; test_scores=[]; misses=[]; ratios=[]; risks=[]; eta_errors=[]
    for pr in store.pull_requests.values():
        a=service.analyze(store.repository(pr.repository_id),pr)
        module_scores.append(metrics({x.module_id for x in a.impacted_nodes},set(pr.ground_truth.impacted_modules)))
        selected={x.id for x in a.recommended_tests}; test_scores.append(metrics(selected,set(pr.ground_truth.affected_tests)))
        misses.append(len(set(pr.ground_truth.failing_tests)-selected)/max(1,len(pr.ground_truth.failing_tests)))
        ratios.append(a.estimated_test_duration_seconds/a.expected_full_suite_duration_seconds)
        risks.append((pr.id,a.risk_score)); eta_errors.append(abs(a.workflow.time_to_green_minutes-pr.ground_truth.time_to_green_minutes))
    avg=lambda xs,i:mean(x[i] for x in xs)
    print("IMerge — fixture evaluation")
    print(f"Impacted modules  P={avg(module_scores,0):.3f} R={avg(module_scores,1):.3f} F1={avg(module_scores,2):.3f}")
    print(f"Selected tests     P={avg(test_scores,0):.3f} R={avg(test_scores,1):.3f} F1={avg(test_scores,2):.3f}")
    print(f"Missed failing-test rate: {mean(misses):.3f}")
    print(f"Selected/full CI duration: {mean(ratios):.1%}")
    print("Risk ranking: "+" > ".join(f"{p} ({s:.1f})" for p,s in sorted(risks,key=lambda x:x[1],reverse=True)))
    print(f"Time-to-green MAE: {mean(eta_errors):.1f} minutes")
if __name__=="__main__": main()
