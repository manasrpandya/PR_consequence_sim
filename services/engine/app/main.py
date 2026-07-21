import logging
import os
import uuid
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .models import *
from .service import AnalysisService, ActionSimulator
from .store import store
from .uploads import (
    UploadProblem, analyze_github, bundle_evidence, inspect_bundle, inspect_github,
    inspect_project, normalize, open_bundle, run_analysis, storage, validate_zip, parse_diff,
    enforce_hosted_request_limit,
)

app=FastAPI(title="IMerge Engine",version="1.0.0",docs_url=None,redoc_url=None)
logger=logging.getLogger("imerge.engine")
origins=[origin.strip() for origin in os.getenv("ALLOWED_ORIGINS","http://localhost:3000").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=["GET","POST"],allow_headers=["Content-Type"],allow_credentials=False)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    request_id=uuid.uuid4().hex
    request.state.request_id=request_id
    try:
        response=await call_next(request)
    except Exception:
        logger.exception("request_failed request_id=%s method=%s path=%s",request_id,request.method,request.url.path)
        response=JSONResponse(status_code=500,content={"error":{"code":"internal_analysis_failure","message":"The analysis service failed while processing this request.","request_id":request_id}})
    response.headers["X-Request-ID"]=request_id
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Cache-Control"]="no-store"
    return response
service=AnalysisService(); simulator=ActionSimulator()

@app.exception_handler(UploadProblem)
async def upload_problem_handler(request: Request, exc: UploadProblem) -> JSONResponse:
    request_id=getattr(request.state,"request_id",uuid.uuid4().hex)
    logger.warning("request_rejected request_id=%s code=%s path=%s",request_id,exc.code,request.url.path)
    return JSONResponse(status_code=exc.status,content={"error":{"code":exc.code,"message":exc.message,"request_id":request_id}})
def get_pr(pr_id: str) -> PullRequest:
    try: return store.pull_request(pr_id)
    except KeyError as exc: raise HTTPException(404,f"Pull request '{pr_id}' was not found") from exc
@app.get("/health")
async def health() -> dict[str,str]: return {"status":"ok","baseline_version":"deterministic-baseline/1.0"}
@app.get("/api/v1/repositories",response_model=list[RepositorySummary])
async def repositories() -> list[RepositorySummary]: return [RepositorySummary(id=r.id,name=r.name,owner=r.owner,language=r.language,module_count=len(r.modules)) for r in store.repositories.values()]
@app.get("/api/v1/repositories/{repository_id}/pull-requests",response_model=list[PullRequestSummary])
async def pull_requests(repository_id: str) -> list[PullRequestSummary]:
    if repository_id not in store.repositories: raise HTTPException(404,"Repository not found")
    out=[]
    for p in store.pull_requests.values():
        if p.repository_id==repository_id:
            churn=p.additions+p.deletions; band="low" if churn<60 else "medium" if churn<250 else "high"
            out.append(PullRequestSummary(id=p.id,number=p.number,title=p.title,author=p.author,additions=p.additions,deletions=p.deletions,ci_state=p.ci_state,preview_band=band))
    return out
@app.get("/api/v1/pull-requests/{pull_request_id}",response_model=PullRequest)
async def pull_request(pull_request_id: str) -> PullRequest: return get_pr(pull_request_id)
@app.post("/api/v1/pull-requests/{pull_request_id}/analyze",response_model=AnalysisResult)
async def analyze(pull_request_id: str) -> AnalysisResult:
    pr=get_pr(pull_request_id); return service.analyze(store.repository(pr.repository_id),pr)
@app.post("/api/v1/pull-requests/{pull_request_id}/simulate",response_model=SimulationResponse)
async def simulate(pull_request_id: str) -> SimulationResponse:
    pr=get_pr(pull_request_id); analysis=service.analyze(store.repository(pr.repository_id),pr); return simulator.simulate(analysis,pr)
@app.get("/api/v1/pull-requests/{pull_request_id}/ground-truth",response_model=GroundTruth)
async def ground_truth(pull_request_id: str) -> GroundTruth: return get_pr(pull_request_id).ground_truth

@app.post("/api/v1/uploads/inspect",response_model=UploadInspection)
async def inspect_upload(archive: UploadFile | None = File(None), diff: UploadFile | None = File(None)) -> UploadInspection:
    if archive is None: raise UploadProblem("missing_archive","A project ZIP is required")
    if diff is None: raise UploadProblem("missing_diff","A .diff or .patch file is required")
    if not (archive.filename or "").lower().endswith(".zip"): raise UploadProblem("unsupported_type","Project archive must be a .zip file")
    if not (diff.filename or "").lower().endswith((".diff",".patch")): raise UploadProblem("unsupported_type","Change must be a .diff or .patch file")
    archive_data=await archive.read(); diff_data=await diff.read(); enforce_hosted_request_limit(archive_data,diff_data)
    return inspect_project(archive_data,diff_data,archive.filename or "project.zip")

@app.post("/api/v1/uploads/analyze",response_model=UserAnalysisResponse)
async def analyze_upload(archive: UploadFile | None = File(None), diff: UploadFile | None = File(None)) -> UserAnalysisResponse:
    if archive is None: raise UploadProblem("missing_archive","A project ZIP is required")
    if diff is None: raise UploadProblem("missing_diff","A .diff or .patch file is required")
    archive_data=await archive.read(); diff_data=await diff.read(); enforce_hosted_request_limit(archive_data,diff_data)
    inspection=inspect_project(archive_data,diff_data,archive.filename or "project.zip")
    if not inspection.valid: raise UploadProblem("path_mismatch","; ".join(inspection.validation_errors))
    files,_=validate_zip(archive_data); parsed=parse_diff(diff_data)
    repo,pr,limits=normalize(inspection.repository_name,files,parsed,"project_diff")
    return run_analysis(repo,pr,"Uploaded project and diff","project archive","submitted patch",limits)

@app.post("/api/v1/git-bundles/inspect",response_model=UploadInspection)
async def inspect_git_bundle(bundle: UploadFile | None = File(None)) -> UploadInspection:
    if bundle is None: raise UploadProblem("unsupported_type","A .bundle file is required")
    if not (bundle.filename or "").lower().endswith(".bundle"): raise UploadProblem("unsupported_type","Git upload must be a .bundle file")
    data=await bundle.read(); enforce_hosted_request_limit(data); return inspect_bundle(data,bundle.filename or "project.bundle")

@app.post("/api/v1/git-bundles/analyze",response_model=UserAnalysisResponse)
async def analyze_git_bundle(bundle: UploadFile | None = File(None),base: str = Form(...),head: str = Form(...)) -> UserAnalysisResponse:
    if bundle is None: raise UploadProblem("unsupported_type","A .bundle file is required")
    data=await bundle.read(); enforce_hosted_request_limit(data)
    with storage.workspace() as root:
        git_repo,_=open_bundle(data,bundle.filename or "project.bundle",root)
        files,parsed=bundle_evidence(git_repo,base,head)
        repo,pr,limits=normalize(Path(bundle.filename or "project.bundle").stem,files,parsed,"git_bundle",history=True,strip_container=False)
        pr.title=f"{head[:12]} compared with {base[:12]}"
        return run_analysis(repo,pr,"Uploaded Git bundle",base,head,limits)

@app.post("/api/v1/github/inspect",response_model=UploadInspection)
async def inspect_public_github(request: GitHubRequest) -> UploadInspection:
    inspection,_,_=inspect_github(request.url); return inspection

@app.post("/api/v1/github/analyze",response_model=UserAnalysisResponse)
async def analyze_public_github(request: GitHubRequest) -> UserAnalysisResponse:
    return analyze_github(request.url)
