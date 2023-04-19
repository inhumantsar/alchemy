from collections import namedtuple
from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Generator, List, Optional, Tuple

from github_bot_api import Event, Webhook, GithubApp
from github.Repository import Repository
from github.GitCommit import GitCommit
from github.PullRequest import PullRequest
from github.InputGitTreeElement import InputGitTreeElement

from alchemy.loader import CacheOptions, ModelOptions, RepoOptions, create_simple_vector_index

assert (GH_BOT_UID := int(os.environ["GH_BOT_UID"]))
assert (GH_APP_ID := int(os.environ["GH_APP_ID"]))
assert (GH_APP_KEY := os.environ["GH_APP_KEY"])
assert (GH_USER_AGENT := os.environ["GH_USER_AGENT"])

@dataclass
class EditTarget:
    path: Path
    """File path relative to project root."""
    commit: str
    """Git commit ID"""
    block: Tuple[int, int]
    """Code block fenced by start and end line numbers."""


@dataclass
class EditCommand:
    repo: Repository
    command: str
    branch: str
    targets: Optional[List[EditTarget]] = None
    pr: str = None


# test: https://pythex.org/?regex=https%3A%2F%2Fgithub.com%2F%5B%5E%2F%5D%2B%2F%5B%5E%2F%5D%2B%2Fblob%2F(%3FP%3Ccommit%3E%5B%5E%2F%5D%2B)%2F(%3FP%3Cpath_str%3E%5B%5E%23%5D%2B)%23L(%3FP%3Cblock_start%3E%5Cd%2B)(%3F%3A-L(%3FP%3Cblock_end%3E%5Cd%2B))%3F&test_string=https%3A%2F%2Fgithub.com%2Flinuxserver%2Fdocker-sabnzbd%2Fblob%2Fmaster%2Froot%2Fetc%2Fs6-overlay%2Fs6-rc.d%2Finit-sabnzbd-config%2Frun%23L4-L7%0Ahttps%3A%2F%2Fgithub.com%2Flinuxserver%2Fdocker-sabnzbd%2Fblob%2Fmaster%2FDockerfile%23L28-L45%0Ahttps%3A%2F%2Fgithub.com%2Flinuxserver%2Fdocker-sabnzbd%2Fblob%2Fmaster%2FDockerfile%23L53%0Aasdfasdfasdf%20asdfasdfasdf%20asdfasdf%20asdfa%20sdf%20https%3A%2F%2Fgithub.com%2Flinuxserver%2Fdocker-sabnzbd%2Fblob%2Fmaster%2FDockerfile%23L53%20asdfasdf%20asdf%20asdf&ignorecase=0&multiline=0&dotall=0&verbose=0
_target_regex = re.compile(r"https://github.com/[^/]+/[^/]+/blob/(?P<commit>[^/]+)/(?P<path_str>[^#]+)#L(?P<start>\d+)(?:-L(?P<end>\d+))?")

_app = GithubApp(user_agent=GH_USER_AGENT, app_id=GH_APP_ID, private_key=GH_APP_KEY)
_webhook = Webhook(secret=None)

_RESP_PATH_PREFIX = '%%%'
_PROMPT_HELPER = f"""
You are a software developer helping to refactor, improve, and maintain a codebase. When prompted to 
perform an update, you must return the entire updated files. Format your responses as plaintext without 
markdown, as if you were editing the file directly, and prefix each file with '{_RESP_PATH_PREFIX}' followed
by a space and the filename. eg: '{_RESP_PATH_PREFIX} relative/path/to/file.py'
"""

@_webhook.listen("*")
def on_any_event(event: Event) -> bool:
    print(event)

    client = _app.installation_client(event.payload["installation"]["id"])
    cmd = EditCommand(repo=client.get_repo(event["repository"]["full_name"]))

    return True


def _get_targets_from_body(haystack: str) -> Generator[EditTarget, None, None]:
    for line in haystack.splitlines():
        if matches := _target_regex.match(line):
            commit, path_str, start, end = matches.groups()
            start = int(start)
            end = int(end) if end else start + 1
            yield EditTarget(Path(path_str), commit, (start, end))


def _create_or_update_branch(cmd: EditCommand, commit_id: str):
    if ref := cmd.repo.get_git_ref(f"heads/{cmd.branch}"):
        ref.edit(commit_id)

    ref = cmd.repo.create_git_ref(f"refs/heads/{cmd.branch}", commit_id)

def _update_file_content(repo: Repository, cmd: EditCommand, path: str, content: str, parent: GitCommit = None) -> GitCommit:
    if not parent:
        branch = repo.get_branch(cmd.branch) or repo.get_branch(repo.default_branch)
        parent = branch.commit.commit
    
    # TODO: reuse existing file mode
    tree = repo.create_git_tree([InputGitTreeElement(path, "100644", "blob", content)], parent.tree)

    return repo.create_git_commit(f"Update {path}", tree, [parent])


def _make_targeted_changes():
    # TODO: get and update individual files
    pass

def _make_freeform_changes(repo: Repository, cmd: EditCommand):
    repo_owner, repo_name = repo.full_name.split('/')

    repo_opts = RepoOptions(
        owner=repo_owner,
        repo=repo_name
    )

    # will it explode if 404?
    if branch := repo.get_branch(cmd.branch):
        repo_opts.branch = branch

    # TODO: load params from env vars
    model_opts = ModelOptions(model_name="gpt-4", temperature=0.2, request_timeout=600)

    # TODO: cache invalidation?
    # TODO: load params from env vars
    cache_opts = CacheOptions()

    # TODO: connect to a dedicated vector db and refresh records when appropriate
    index = create_simple_vector_index(repo_opts, cache_opts, model_opts)    

    resp = index.query(_PROMPT_HELPER + cmd.command).response
    
    # TODO: validate filenames provided in resp and ask gpt for clarification if they can't be found.
    OutputFile = namedtuple("OutputFile", ["path", "content"])
    output_files: List[OutputFile] = []
    for line in resp.splitlines():
        if line.startswith(_RESP_PATH_PREFIX):
            _, key = line.split(_RESP_PATH_PREFIX)
            output_files.append(OutputFile(key.strip(), ""))
        else:
            output_files[-1].content += line + "\n"

    prev_commit = None
    for f in output_files:
        prev_commit = _update_file_content(repo, cmd, f.path, f.content, prev_commit)
        _create_or_update_branch(repo, branch, prev_commit.sha)



def _make_changes(repo: Repository, cmd: EditCommand) -> GitCommit:
    if cmd.targets:
       _make_targeted_changes()
    else:
        _make_freeform_changes(repo, cmd)


def handle_issues_opened(repo: Repository, event: Event):
    """Make the changes requested in a GitHub issue and open a new PR for them."""
    assert (body := event["issue"]["body"])
    assert (number := event["issue"]["number"])
    assert (title := event["issue"]["title"])

    branch = f"bot/issue-{number}"
    cmd_opts = {"repo": repo, "cmd": body, "branch": branch}
    cmds = [EditCommand(**cmd_opts, t) for t in _get_targets_from_body(body)] or EditCommand(**cmd_opts)

    for cmd in cmds:
        _make_changes(cmd)

    repo.create_pull(title, f"Closes #{number}", repo.default_branch, branch)


def handle_pr_comment(repo: Repository, event: Event):
    REPLY_TEMPLATE = "Addressed in %s"
    comment = event["comment"]

    # don't respond to other people's PRs or the bot's own comments
    assert event["pull_request"]["user"]["id"] == GH_BOT_UID
    assert comment["user"]["id"] != GH_BOT_UID

    branch = event["pull_request"]["head"]["ref"]
    start = int(event["start_line"] or event["line"])

    target = EditTarget(
        comment["path"],
        comment["commit_id"],
        (start, int(event["line"])),
    )
    commit: GitCommit = _make_changes(EditCommand(repo=repo, command=comment["body"], targets=[target], branch=branch))

    pr = repo.get_pull(event["pull_request"]["number"])

    # why doesn't intellisense see this fn?
    pr.create_review_comment_reply(target.commit, REPLY_TEMPLATE.format(target.commit))
