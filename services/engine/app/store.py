import json
from pathlib import Path
from .models import PullRequest, Repository

MODULE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CANDIDATES = (MODULE_ROOT / "fixtures", Path(__file__).resolve().parents[3] / "fixtures")
FIXTURES = next((path for path in FIXTURE_CANDIDATES if path.is_dir()), FIXTURE_CANDIDATES[0])

class FixtureStore:
    def __init__(self) -> None:
        repos = json.loads((FIXTURES / "repositories.json").read_text())["repositories"]
        prs = json.loads((FIXTURES / "pull_requests.json").read_text())["pull_requests"]
        self.repositories = {x["id"]: Repository.model_validate(x) for x in repos}
        self.pull_requests = {x["id"]: PullRequest.model_validate(x) for x in prs}
    def repository(self, repository_id: str) -> Repository:
        return self.repositories[repository_id]
    def pull_request(self, pull_request_id: str) -> PullRequest:
        return self.pull_requests[pull_request_id]

store = FixtureStore()
