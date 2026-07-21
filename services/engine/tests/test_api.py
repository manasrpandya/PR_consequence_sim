import asyncio
import pytest
from fastapi import HTTPException
from app.main import app, analyze, health, inspect_upload, repositories, simulate
from app.uploads import UploadProblem

def run(coroutine):
    return asyncio.run(coroutine)

def test_health_listing_and_openapi_contract():
    assert run(health())["status"]=="ok"
    repos=run(repositories()); assert repos[0].id=="meridian-commerce"
    paths=app.openapi()["paths"]
    assert "/api/v1/pull-requests/{pull_request_id}/analyze" in paths
    assert "/api/v1/pull-requests/{pull_request_id}/simulate" in paths
    assert "/api/v1/uploads/inspect" in paths
    assert "/api/v1/git-bundles/analyze" in paths
    assert "/api/v1/github/analyze" in paths

def test_analysis_and_simulation_response_schemas():
    body=run(analyze("pr-309")); assert 0<=body.risk_score<=100
    assert body.evidence_pack and body.confidence and body.explanation
    result=run(simulate("pr-309")); assert len(result.results)==6
    assert sum(1 for item in result.results if item.recommended)==1

def test_meaningful_not_found():
    with pytest.raises(HTTPException,match="not found") as caught:
        run(analyze("missing"))
    assert caught.value.status_code==404

def test_missing_project_evidence_is_structured():
    with pytest.raises(UploadProblem) as caught:
        run(inspect_upload(None,None))
    assert caught.value.code=="missing_archive"
