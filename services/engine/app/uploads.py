from __future__ import annotations

import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
import zipfile
import zlib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Iterator, Literal

from .models import (
    AnalysisMetadata, Capability, ChangedFile, DependencyEdge, EvidenceItem, GitRef,
    GroundTruth, Module, PullRequest, Repository, TestFile, UploadInspection,
    UserAnalysisResponse, WorkflowEvent,
)
from .service import ActionSimulator, AnalysisService

HOSTED_REQUEST_LIMIT = 3_500_000
MAX_COMPRESSED = 25 * 1024 * 1024
MAX_EXTRACTED = 100 * 1024 * 1024
MAX_FILES = 4000
MAX_FILE = 2 * 1024 * 1024
MAX_DIFF = 5 * 1024 * 1024
IGNORED_DIRS={"node_modules",".next","dist","build","coverage","vendor",".git"}
SECRET_NAMES={".env",".env.local",".npmrc","id_rsa","id_ed25519","credentials","secrets.yml"}
SOURCE_EXT={".ts",".tsx",".js",".jsx",".mjs",".cjs",".py",".go",".rs",".java",".kt",".rb",".php",".cs",".cpp",".c",".h"}
TEST_RE=re.compile(r"(^|/)(__tests__|tests?|spec)(/|\.)|\.(test|spec)\.",re.I)
DIFF_FILE_RE=re.compile(r"^diff --git a/(.+?) b/(.+)$",re.M)
IMPORT_RE=re.compile(r"(?:from\s+|require\(|import\s*\()[\"']([^\"']+)")

class UploadProblem(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message); self.code=code; self.message=message; self.status=status

class TemporaryStorage:
    @contextmanager
    def workspace(self) -> Iterator[Path]:
        raise NotImplementedError

class LocalTemporaryStorage(TemporaryStorage):
    @contextmanager
    def workspace(self) -> Iterator[Path]:
        root=Path(tempfile.mkdtemp(prefix="imerge-"))
        try: yield root
        finally: shutil.rmtree(root,ignore_errors=True)

storage=LocalTemporaryStorage()

def safe_name(name: str) -> str:
    return Path(name).name[:180] or "upload"

def enforce_hosted_request_limit(*payloads: bytes) -> None:
    if os.getenv("VERCEL") and sum(len(payload) for payload in payloads) > HOSTED_REQUEST_LIMIT:
        raise UploadProblem("request_limit_exceeded", "Hosted uploads must total 3.5 MB or less", 413)

def is_ignored(path: str) -> bool:
    parts=PurePosixPath(path).parts
    return any(p in IGNORED_DIRS for p in parts) or any(p.lower() in SECRET_NAMES or p.lower().endswith((".pem",".key",".p12")) for p in parts)

def is_binary(data: bytes) -> bool:
    return b"\0" in data[:8192]

def validate_zip(data: bytes) -> tuple[dict[str,bytes],list[str]]:
    if len(data)>MAX_COMPRESSED: raise UploadProblem("archive_limit_exceeded","Archive exceeds the 25 MB compressed limit",413)
    files: dict[str,bytes]={}; warnings=[]; total=0
    try:
        archive=zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc: raise UploadProblem("corrupt_archive","The ZIP archive is corrupt") from exc
    infos=archive.infolist()
    if len(infos)>MAX_FILES: raise UploadProblem("archive_limit_exceeded",f"Archive contains more than {MAX_FILES} entries",413)
    for info in infos:
        raw=info.filename.replace("\\","/"); path=PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts: raise UploadProblem("path_traversal","Archive contains an unsafe path")
        mode=info.external_attr>>16
        if stat.S_ISLNK(mode): warnings.append(f"Ignored symbolic link: {raw}"); continue
        if info.is_dir() or is_ignored(raw): continue
        if info.file_size>MAX_FILE: warnings.append(f"Ignored oversized file: {raw}"); continue
        total+=info.file_size
        if total>MAX_EXTRACTED: raise UploadProblem("archive_limit_exceeded","Expanded archive exceeds the 100 MB limit",413)
        try: content=archive.read(info)
        except (RuntimeError,OSError,zipfile.BadZipFile,zlib.error) as exc: raise UploadProblem("extraction_failure","A ZIP entry could not be safely extracted") from exc
        if is_binary(content): warnings.append(f"Ignored binary file: {raw}"); continue
        files[raw]=content
    return files,warnings

@dataclass
class DiffInfo:
    paths:list[str]; additions:int; deletions:int; text:str

def parse_diff(data: bytes) -> DiffInfo:
    if len(data)>MAX_DIFF: raise UploadProblem("archive_limit_exceeded","Diff exceeds the 5 MB limit",413)
    if is_binary(data): raise UploadProblem("unsupported_type","Diff must be a text file")
    text=data.decode("utf-8","replace"); paths=[head for _,head in DIFF_FILE_RE.findall(text)]
    if not paths: raise UploadProblem("missing_diff","No changed paths were found in the diff")
    additions=sum(1 for line in text.splitlines() if line.startswith("+") and not line.startswith("+++"))
    deletions=sum(1 for line in text.splitlines() if line.startswith("-") and not line.startswith("---"))
    return DiffInfo(list(dict.fromkeys(paths)),additions,deletions,text)

def strip_root(paths: list[str]) -> list[str]:
    roots={p.split("/",1)[0] for p in paths if "/" in p}
    project_dirs={"apps","packages","services","src","libs","test","tests","docs","config"}
    if len(roots)==1 and next(iter(roots)).lower() not in project_dirs:
        root=next(iter(roots)); return [p[len(root)+1:] if p.startswith(root+"/") else p for p in paths]
    return paths

def project_language(paths:list[str]) -> str:
    counts:dict[str,int]={}; labels={".ts":"TypeScript",".tsx":"TypeScript",".js":"JavaScript",".jsx":"JavaScript",".py":"Python",".go":"Go",".rs":"Rust",".java":"Java",".rb":"Ruby"}
    for p in paths:
        label=labels.get(Path(p).suffix.lower(),"Other"); counts[label]=counts.get(label,0)+1
    return max(counts,key=lambda name:counts[name]) if counts else "Unknown"

def module_id(path:str) -> str:
    parts=PurePosixPath(path).parts
    if len(parts)>=2 and parts[0] in {"apps","packages","services","src","libs"}: return "-".join(parts[:2])
    return parts[0] if len(parts)>1 else "root"

def normalize(repo_name:str, files:dict[str,bytes], diff:DiffInfo, source:str, history:bool=False,strip_container:bool=True) -> tuple[Repository,PullRequest,list[str]]:
    original=list(files); stripped=strip_root(original) if strip_container else original; files={short:files[raw] for raw,short in zip(original,stripped)}
    source_paths=[p for p in files if Path(p).suffix.lower() in SOURCE_EXT]
    if not source_paths: raise UploadProblem("no_analyzable_source","Archive contains no analyzable source files")
    matches=[p for p in diff.paths if p in files]
    if len(matches)/len(diff.paths)<.5: raise UploadProblem("path_mismatch","Diff paths do not plausibly match the project archive")
    mids=sorted({module_id(p) for p in source_paths}|{module_id(p) for p in matches})
    modules=[Module(id=m,name=m.replace("-"," / "),path=m.replace("-","/"),criticality=.65 if any(x in m.lower() for x in ("db","database","auth","payment")) else .4,owner="Unknown",shared="shared" in m or "database" in m) for m in mids]
    edges:set[tuple[str,str]]=set()
    for path,data in files.items():
        if Path(path).suffix.lower() not in SOURCE_EXT: continue
        src=module_id(path)
        for imp in IMPORT_RE.findall(data.decode("utf-8","replace")):
            for candidate in mids:
                if candidate!=src and candidate.split("-")[-1] in imp: edges.add((src,candidate))
    tests=[]
    for path in source_paths:
        if TEST_RE.search(path):
            related={module_id(path)}|{m for a,b in edges for m in (a,b) if a==module_id(path) or b==module_id(path)}
            tests.append(TestFile(id=re.sub(r"[^a-z0-9]+","-",path.lower()).strip("-"),file=path,type="e2e" if "e2e" in path.lower() else "integration" if "integration" in path.lower() else "unit",duration_seconds=60,modules=sorted(related&set(mids)) or [module_id(path)],failure_associations={}))
    changed=[ChangedFile(path=p,module_id=module_id(p),additions=max(1,diff.additions//len(matches)),deletions=diff.deletions//len(matches),summary="Changed in submitted patch") for p in matches]
    repo=Repository(id=f"upload-{uuid.uuid4().hex[:8]}",name=repo_name,owner="Uploaded locally",default_branch="uploaded-base",language=project_language(source_paths),modules=modules,dependency_edges=[DependencyEdge(from_module=a,to_module=b) for a,b in sorted(edges)],tests=tests,full_suite_duration_seconds=sum(t.duration_seconds for t in tests))
    pr=PullRequest(id=f"change-{uuid.uuid4().hex[:8]}",repository_id=repo.id,number=1,title="Uploaded change",description="Locally submitted change",author="Local upload",changed_files=changed,additions=diff.additions,deletions=diff.deletions,commits=1,labels=[source],opened_at=datetime.now(UTC).isoformat(),workflow_events=[WorkflowEvent(kind="history_available",timestamp=datetime.now(UTC).isoformat(),detail="Local Git history supplied")] if history else [],ci_state="unknown",historical_failure_rate=.12 if history else 0,workflow_instability=.12 if history else 0,reviewers=[],ground_truth=GroundTruth(impacted_modules=[],affected_tests=[],failing_tests=[],time_to_green_minutes=0),diff_summary=f"{len(matches)} changed paths from submitted evidence")
    limits=["Coverage and measured test durations were not provided."]
    if not history: limits.append("Time-to-green is unavailable because this upload contains no CI history.")
    if repo.language not in {"TypeScript","JavaScript"}: limits.append("Generic structural fallback used; enhanced import analysis targets JavaScript and TypeScript.")
    return repo,pr,limits

def run_analysis(repo:Repository,pr:PullRequest,source_label:str,base:str,head:str,limitations:list[str],source_url:str|None=None) -> UserAnalysisResponse:
    analysis=AnalysisService().analyze(repo,pr)
    if not pr.workflow_events:
        analysis.workflow.time_to_green_minutes=0; analysis.workflow.bottleneck="Unavailable — no CI history"; analysis.workflow.confidence=.2
        analysis.risk_factors=[factor for factor in analysis.risk_factors if factor.name not in {"Historical failures","Workflow instability"}]
    else: analysis.workflow.confidence=min(analysis.workflow.confidence,.55)
    analysis.confidence=min(analysis.confidence,.68)
    analysis.evidence_pack.append(EvidenceItem(label="Provenance",detail=f"Derived from {len(pr.changed_files)} submitted changed paths",source=source_label))
    simulation=ActionSimulator().simulate(analysis,pr)
    if not pr.workflow_events:
        for item in simulation.results:
            item.predicted_time_to_green_after=0; item.estimated_delay_reduction=0
            item.assumptions.append("Workflow ETA is unavailable because hosted CI history was not supplied")
    level: Literal["partial","structural"]="partial" if pr.workflow_events else "structural"
    meta=AnalysisMetadata(source_label=source_label,repository_name=repo.name,base=base,head=head,change_label=pr.title,detected_language=repo.language,changed_files=len(pr.changed_files),additions=pr.additions,deletions=pr.deletions,capability_level=level,analyzed_at=datetime.now(UTC).isoformat(),source_url=source_url,limitations=limitations+["Risk is a transparent heuristic estimate, not a production-calibrated failure probability."])
    observed=[EvidenceItem(label="Changed paths",detail=f"{len(pr.changed_files)} source paths matched",source=source_label),EvidenceItem(label="Repository structure",detail=f"{len(repo.modules)} modules and {len(repo.dependency_edges)} import edges detected",source="Static text inspection")]
    return UserAnalysisResponse(metadata=meta,observed=observed,predicted=analysis,suggested=simulation)

def git_env() -> dict[str,str]:
    env=os.environ.copy(); env.update({"GIT_CONFIG_NOSYSTEM":"1","GIT_TERMINAL_PROMPT":"0","GIT_OPTIONAL_LOCKS":"0"}); return env

def git(args:list[str],cwd:Path,timeout:int=15) -> str:
    command=["git","-c","core.hooksPath=/dev/null","-c","filter.lfs.smudge=cat","-c","filter.lfs.clean=cat",*args]
    try: result=subprocess.run(command,cwd=cwd,env=git_env(),capture_output=True,text=True,timeout=timeout,check=False)
    except subprocess.TimeoutExpired as exc: raise UploadProblem("timeout","Git inspection timed out",408) from exc
    if result.returncode: raise UploadProblem("invalid_bundle","Git could not inspect this bundle")
    return result.stdout

def open_bundle(data:bytes,name:str,root:Path) -> tuple[Path,list[GitRef]]:
    if len(data)>MAX_COMPRESSED: raise UploadProblem("archive_limit_exceeded","Bundle exceeds the 25 MB limit",413)
    bundle=root/safe_name(name); bundle.write_bytes(data); repo=root/"repository.git"
    if shutil.which("git") is None:
        from dulwich import porcelain
        from dulwich.repo import Repo
        porcelain.clone(str(bundle),str(repo),bare=True)
        opened=Repo(str(repo)); refs=[]
        for ref,commit in opened.refs.as_dict().items():
            if ref.startswith((b"refs/heads/",b"refs/tags/")):
                label=ref.rsplit(b"/",1)[-1].decode("utf-8","replace")
                refs.append(GitRef(name=ref.decode(),commit=commit.decode(),label=label))
        if not refs: raise UploadProblem("invalid_bundle","Bundle contains no commits")
        return repo,refs
    git(["init","--bare",str(repo)],root); git(["fetch",str(bundle),"refs/*:refs/*"],repo,30)
    expanded=sum(path.stat().st_size for path in repo.rglob("*") if path.is_file())
    if expanded>MAX_EXTRACTED: raise UploadProblem("archive_limit_exceeded","Expanded Git bundle exceeds the 100 MB limit",413)
    raw=git(["for-each-ref","--format=%(refname)|%(objectname)|%(refname:short)","refs/heads","refs/tags"],repo)
    refs=[GitRef(name=line.split("|")[0],commit=line.split("|")[1],label=line.split("|")[2]) for line in raw.splitlines() if line.count("|")==2]
    commits=git(["log","--all","--format=%H|%s","-n","12"],repo).splitlines()
    refs.extend(GitRef(name=c.split("|",1)[0],commit=c.split("|",1)[0],label=c.split("|",1)[1][:80]) for c in commits if "|" in c)
    if not refs: raise UploadProblem("invalid_bundle","Bundle contains no commits")
    return repo,refs

def bundle_evidence(repo:Path,base:str,head:str) -> tuple[dict[str,bytes],DiffInfo]:
    if shutil.which("git") is None:
        from dulwich.objectspec import parse_commit
        from dulwich.patch import write_tree_diff
        from dulwich.repo import Repo
        opened=Repo(str(repo)); base_commit=parse_commit(opened,base.encode()); head_commit=parse_commit(opened,head.encode())
        entries=list(opened.object_store.iter_tree_contents(head_commit.tree))
        if len(entries)>MAX_FILES: raise UploadProblem("archive_limit_exceeded",f"Git tree contains more than {MAX_FILES} files",413)
        files={}; total=0
        for entry in entries:
            name=entry.path.decode("utf-8","replace")
            if is_ignored(name) or Path(name).suffix.lower() not in SOURCE_EXT|{".json",".yml",".yaml"}: continue
            content=getattr(opened[entry.sha],"data",b"")
            if len(content)<=MAX_FILE and not is_binary(content):
                total+=len(content)
                if total>MAX_EXTRACTED: raise UploadProblem("archive_limit_exceeded","Inspected Git files exceed the 100 MB limit",413)
                files[name]=content
        patch_buffer=io.BytesIO(); write_tree_diff(patch_buffer,opened.object_store,base_commit.tree,head_commit.tree)
        return files,parse_diff(patch_buffer.getvalue())
    for ref in (base,head):
        try: git(["rev-parse","--verify",f"{ref}^{{commit}}"],repo)
        except UploadProblem as exc: raise UploadProblem("invalid_git_refs",f"Git ref '{ref[:60]}' is not a valid commit") from exc
    names=git(["ls-tree","-r","--name-only",head],repo).splitlines(); files={}
    if len(names)>MAX_FILES: raise UploadProblem("archive_limit_exceeded",f"Git tree contains more than {MAX_FILES} files",413)
    total=0
    for name in names[:MAX_FILES]:
        if is_ignored(name) or Path(name).suffix.lower() not in SOURCE_EXT|{".json",".yml",".yaml"}: continue
        content=subprocess.run(["git","-c","core.hooksPath=/dev/null","show",f"{head}:{name}"],cwd=repo,capture_output=True,timeout=5).stdout
        if len(content)<=MAX_FILE and not is_binary(content):
            total+=len(content)
            if total>MAX_EXTRACTED: raise UploadProblem("archive_limit_exceeded","Inspected Git files exceed the 100 MB limit",413)
            files[name]=content
    patch=git(["diff","--no-ext-diff","--unified=1",base,head,"--"],repo,30).encode()
    return files,parse_diff(patch)

def inspect_project(archive:bytes,diff_data:bytes,name:str) -> UploadInspection:
    files,warnings=validate_zip(archive); diff=parse_diff(diff_data); stripped=set(strip_root(list(files)))
    matches=[p for p in diff.paths if p in stripped]; errors=[]
    if len(matches)/len(diff.paths)<.5: errors.append("Diff paths do not plausibly match the archive")
    source=[p for p in files if Path(p).suffix.lower() in SOURCE_EXT]
    if not source: errors.append("Archive contains no analyzable source files")
    lang=project_language(source); caps=[Capability(name="Repository structure",status="available",detail=f"{len(source)} source files detected"),Capability(name="Test selection",status="partial",detail="Based on filenames and imports; coverage data was not provided"),Capability(name="Workflow prediction",status="unavailable",detail="No CI or workflow history in project-plus-diff upload")]
    return UploadInspection(inspection_id=uuid.uuid4().hex,valid=not errors,source="project_diff",repository_name=Path(name).stem,detected_language=lang,project_type="Enhanced JS/TS" if lang in {"JavaScript","TypeScript"} else "Generic structural fallback",changed_files=diff.paths,additions=diff.additions,deletions=diff.deletions,capabilities=caps,warnings=warnings,validation_errors=errors)

def inspect_bundle(data:bytes,name:str) -> UploadInspection:
    with storage.workspace() as root:
        repo,refs=open_bundle(data,name,root); head=refs[0].name
        if shutil.which("git") is None:
            from dulwich.objectspec import parse_commit
            from dulwich.repo import Repo
            commit=parse_commit(Repo(str(repo)),head.encode()); base=commit.parents[0].decode() if commit.parents else head
        else:
            try: base=git(["rev-parse",f"{head}^"],repo).strip()
            except UploadProblem: base=head
        files,diff=bundle_evidence(repo,base,head)
        language=project_language(list(files))
        return UploadInspection(inspection_id=uuid.uuid4().hex,valid=True,source="git_bundle",repository_name=Path(name).stem,detected_language=language,project_type="Enhanced JS/TS" if language in {"JavaScript","TypeScript"} else "Generic structural fallback",refs=refs,default_base=base,default_head=head,changed_files=diff.paths,additions=diff.additions,deletions=diff.deletions,capabilities=[Capability(name="Repository structure",status="available",detail=f"{len(files)} text files inspected"),Capability(name="Git history",status="available",detail="Branches, commits, and comparison are available"),Capability(name="Workflow prediction",status="partial",detail="Local commit history is present, but hosted CI and review history are unavailable")])

def github_coordinates(url:str) -> tuple[str,str,int]:
    match=re.fullmatch(r"https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9_.-]{1,100})/pull/([1-9]\d*)/?",url.strip())
    if not match: raise UploadProblem("unsupported_type","Enter a public GitHub pull request URL")
    return match.group(1),match.group(2),int(match.group(3))

def github_json(url:str) -> object:
    if not url.startswith("https://api.github.com/repos/"):
        raise UploadProblem("unsupported_host", "Only GitHub API requests are allowed")
    headers={"Accept":"application/vnd.github+json","User-Agent":"imerge","X-GitHub-Api-Version":"2022-11-28"}
    token=os.getenv("GITHUB_TOKEN")
    if token: headers["Authorization"]=f"Bearer {token}"
    request=urllib.request.Request(url,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=10) as response: return json.loads(response.read(MAX_DIFF+1))
    except urllib.error.HTTPError as exc:
        if exc.code==429 or (exc.code==403 and exc.headers.get("X-RateLimit-Remaining")=="0"): raise UploadProblem("github_rate_limited","GitHub rate limit reached. Try again shortly or use the guided example.",429) from exc
        if exc.code==401: raise UploadProblem("github_auth_failed","GitHub authentication failed. The deployment token may be invalid.",502) from exc
        if exc.code==403: raise UploadProblem("github_not_accessible","GitHub refused access to that pull request. Confirm that the repository is public.",403) from exc
        if exc.code==404: raise UploadProblem("github_not_found","That public pull request was not found or is not accessible.",404) from exc
        raise UploadProblem("github_unavailable","GitHub could not complete the request.",502) from exc
    except TimeoutError as exc: raise UploadProblem("github_timeout","GitHub timed out. Try again or use the guided example.",504) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason,TimeoutError): raise UploadProblem("github_timeout","GitHub timed out. Try again or use the guided example.",504) from exc
        raise UploadProblem("github_unavailable","GitHub could not be reached. Try again or use the guided example.",502) from exc
    except json.JSONDecodeError as exc: raise UploadProblem("github_malformed_response","GitHub returned an unreadable response. Try again shortly.",502) from exc

def inspect_github(url:str) -> tuple[UploadInspection,dict[str,object],list[dict[str,object]]]:
    owner,name,number=github_coordinates(url); pr=github_json(f"https://api.github.com/repos/{owner}/{name}/pulls/{number}")
    files: list[dict[str,object]]=[]; truncated=False
    for page in range(1,4):
        changed=github_json(f"https://api.github.com/repos/{owner}/{name}/pulls/{number}/files?per_page=100&page={page}")
        if not isinstance(changed,list): raise UploadProblem("github_unavailable","GitHub returned an unexpected response",502)
        files.extend(x for x in changed if isinstance(x,dict))
        if len(changed)<100: break
    else: truncated=True
    if not isinstance(pr,dict): raise UploadProblem("github_unavailable","GitHub returned an unexpected response",502)
    paths=[str(x.get("filename","")) for x in files if x.get("filename")]
    if not paths: raise UploadProblem("no_analyzable_source","The pull request has no analyzable changed files")
    lang=project_language(paths); inspection=UploadInspection(inspection_id=uuid.uuid4().hex,valid=True,source="github_pr",repository_name=f"{owner}/{name}",detected_language=lang,project_type="Public GitHub PR",default_base=str(pr.get("base",{}).get("sha","")) if isinstance(pr.get("base"),dict) else None,default_head=str(pr.get("head",{}).get("sha","")) if isinstance(pr.get("head"),dict) else None,changed_files=paths,additions=int(pr.get("additions",0)),deletions=int(pr.get("deletions",0)),capabilities=[Capability(name="Change evidence",status="available",detail="GitHub PR metadata and bounded patches loaded"),Capability(name="Repository structure",status="partial",detail="Analysis is bounded to files visible in the public PR"),Capability(name="Workflow prediction",status="partial",detail="Public PR state is available; full CI history is not")],warnings=["Analysis was capped at the first 300 changed files."] if truncated else [])
    return inspection,pr,files

def analyze_github(url:str) -> UserAnalysisResponse:
    inspection,raw,changed=inspect_github(url); files={}
    for item in changed:
        path=str(item.get("filename","")); patch=str(item.get("patch",f"@@\n+changed {path}")); files[path]=patch.encode()
    # Add manifest-like placeholders for changed source paths; content is patch text, never executed.
    chunks=[]
    for item in changed:
        path=str(item.get("filename","")); patch=str(item.get("patch", "@@\n+changed"))
        chunks.append(f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n{patch}")
    diff_text="\n".join(chunks)
    diff=parse_diff(diff_text.encode()); repo,pr,limits=normalize(inspection.repository_name,files,diff,"github_pr",history=True,strip_container=False)
    user=raw.get("user"); commits=raw.get("commits",1)
    pr.title=str(raw.get("title","Public GitHub pull request")); pr.author=str(user.get("login","GitHub author")) if isinstance(user,dict) else "GitHub author"; pr.commits=commits if isinstance(commits,int) else 1; pr.ci_state=str(raw.get("state","unknown"))
    return run_analysis(repo,pr,"Live public GitHub analysis",inspection.default_base or "base",inspection.default_head or "head",limits+inspection.warnings,url)
