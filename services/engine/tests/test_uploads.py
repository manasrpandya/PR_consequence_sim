import io
import os
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest

from app.uploads import (
    LocalTemporaryStorage, UploadProblem, bundle_evidence, inspect_bundle,
    inspect_project, is_binary, is_ignored, normalize, open_bundle, parse_diff,
    run_analysis, validate_zip,
)

def make_zip(files:dict[str,bytes],symlink:str|None=None) -> bytes:
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w",zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items(): archive.writestr(name,data)
        if symlink:
            info=zipfile.ZipInfo(symlink); info.external_attr=(stat.S_IFLNK|0o777)<<16
            archive.writestr(info,"target.ts")
    return stream.getvalue()

def patch(path:str,body:str="+export const changed = true") -> bytes:
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -0,0 +1 @@\n{body}\n".encode()

def sample_archive() -> bytes:
    return make_zip({"project/packages/cart/index.ts":b"import {pay} from '../payments'\nexport const cart=1", "project/packages/cart/index.test.ts":b"import {cart} from './index'", "project/packages/payments/index.ts":b"export const pay=1", "project/.env":b"TOKEN=secret", "project/node_modules/pkg/index.js":b"ignored", "project/image.bin":b"\0binary"})

def test_zip_safety_filters_binary_secret_dependencies_and_symlinks():
    files,warnings=validate_zip(make_zip({"src/index.ts":b"export {}",".env":b"SECRET=yes","node_modules/x.js":b"x","asset.bin":b"\0x"},"src/link.ts"))
    assert set(files)=={"src/index.ts"}
    assert any("symbolic link" in item for item in warnings)
    assert is_binary(b"a\0b") and is_ignored("build/output.js") and is_ignored("keys/private.pem")

@pytest.mark.parametrize("name",["../escape.ts","/absolute.ts","src/../../escape.ts"])
def test_zip_rejects_path_traversal(name:str):
    with pytest.raises(UploadProblem,match="unsafe path"):
        validate_zip(make_zip({name:b"x"}))

def test_zip_enforces_decompression_limits(monkeypatch):
    monkeypatch.setattr("app.uploads.MAX_EXTRACTED",10)
    with pytest.raises(UploadProblem,match="Expanded archive"):
        validate_zip(make_zip({"src/a.ts":b"x"*11}))

def test_project_diff_validation_and_path_matching():
    good=inspect_project(sample_archive(),patch("packages/cart/index.ts"),"project.zip")
    assert good.valid and good.detected_language=="TypeScript"
    bad=inspect_project(sample_archive(),patch("unrelated/missing.ts"),"project.zip")
    assert not bad.valid and "plausibly match" in bad.validation_errors[0]

def test_normalization_uses_existing_pipeline_and_degrades_without_history():
    files,_=validate_zip(sample_archive()); parsed=parse_diff(patch("packages/cart/index.ts"))
    repo,pr,limits=normalize("project",files,parsed,"project_diff")
    result=run_analysis(repo,pr,"Uploaded project and diff","archive","patch",limits)
    assert pr.changed_files[0].path=="packages/cart/index.ts"
    assert result.predicted.model_version=="deterministic-baseline/1.0"
    assert result.metadata.capability_level=="structural"
    assert result.predicted.workflow.time_to_green_minutes==0
    assert any("unavailable" in item.lower() for item in result.metadata.limitations)

def test_temporary_workspace_cleanup():
    storage=LocalTemporaryStorage()
    with storage.workspace() as root:
        path=root; (root/"evidence.txt").write_text("temporary")
        assert root.exists()
    assert not path.exists()

def make_bundle(tmp_path:Path) -> tuple[bytes,str,str]:
    repo=tmp_path/"source"; repo.mkdir()
    subprocess.run(["git","init","-q"],cwd=repo,check=True)
    subprocess.run(["git","config","user.email","test@example.com"],cwd=repo,check=True)
    subprocess.run(["git","config","user.name","Test"],cwd=repo,check=True)
    (repo/"src").mkdir(); (repo/"src/app.ts").write_text("export const value = 1\n")
    (repo/"src/app.test.ts").write_text("import {value} from './app'\n")
    subprocess.run(["git","add","."],cwd=repo,check=True); subprocess.run(["git","commit","-qm","base"],cwd=repo,check=True)
    base=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    (repo/"src/app.ts").write_text("export const value = 2\nexport const added = true\n")
    subprocess.run(["git","add","."],cwd=repo,check=True); subprocess.run(["git","commit","-qm","change"],cwd=repo,check=True)
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    target=tmp_path/"project.bundle"; subprocess.run(["git","bundle","create",target,"--all"],cwd=repo,check=True)
    return target.read_bytes(),base,head

def test_git_bundle_validation_ref_discovery_and_comparison(tmp_path):
    data,base,head=make_bundle(tmp_path); inspection=inspect_bundle(data,"project.bundle")
    assert inspection.valid and len(inspection.refs)>=2
    storage=LocalTemporaryStorage()
    with storage.workspace() as root:
        repo,_=open_bundle(data,"project.bundle",root); files,diff=bundle_evidence(repo,base,head)
        assert "src/app.ts" in files and diff.paths==["src/app.ts"] and diff.additions==2

def test_invalid_bundle_is_structured(tmp_path):
    with pytest.raises(UploadProblem) as caught:
        inspect_bundle(b"not a git bundle","broken.bundle")
    assert caught.value.code=="invalid_bundle"
