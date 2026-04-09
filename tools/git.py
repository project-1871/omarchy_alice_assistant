"""Git status briefing tool — finds active repos and reports what you worked on."""
import os
import subprocess
from datetime import date, datetime
from tools.base import Tool

# Directories to scan for git repos (non-recursive — checks these folders' immediate children)
_SCAN_ROOTS = [
    os.path.expanduser('~'),
    os.path.expanduser('~/500G/my_aps_&_projects'),
    os.path.expanduser('~/500G'),
]

# Individual known repos to always include
_KNOWN_REPOS = [
    os.path.expanduser('~/alice-assistant'),
    os.path.expanduser('~/claudecodeui'),
]

# Max depth for repo discovery under scan roots
_MAX_DEPTH = 1


def _run_git(repo: str, args: list[str], timeout: int = 5) -> str:
    """Run a git command in a repo dir. Returns stdout or '' on error."""
    try:
        result = subprocess.run(
            ['git', '-C', repo] + args,
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ''


def _is_git_repo(path: str) -> bool:
    return os.path.isdir(os.path.join(path, '.git'))


def _find_repos() -> list[str]:
    """Return de-duplicated list of git repo paths."""
    repos = set()
    for known in _KNOWN_REPOS:
        if _is_git_repo(known):
            repos.add(os.path.realpath(known))

    for root in _SCAN_ROOTS:
        if not os.path.isdir(root):
            continue
        try:
            for entry in os.scandir(root):
                if entry.is_dir(follow_symlinks=False) and _is_git_repo(entry.path):
                    repos.add(os.path.realpath(entry.path))
        except PermissionError:
            pass

    return sorted(repos)


def _repo_name(path: str) -> str:
    return os.path.basename(path)


def _commits_today(repo: str) -> list[str]:
    """Return list of commit summaries made today."""
    today = date.today().strftime('%Y-%m-%d')
    output = _run_git(repo, [
        'log', '--oneline', '--since', f'{today} 00:00', '--until', f'{today} 23:59'
    ])
    return [line for line in output.splitlines() if line]


def _last_commit_time(repo: str) -> datetime | None:
    """Return datetime of the most recent commit, or None."""
    output = _run_git(repo, ['log', '-1', '--format=%ci'])
    if not output:
        return None
    try:
        return datetime.fromisoformat(output[:19])
    except ValueError:
        return None


def _status_summary(repo: str) -> str:
    """Return a short status summary: branch + changed/untracked counts."""
    branch = _run_git(repo, ['branch', '--show-current']) or 'detached'
    status = _run_git(repo, ['status', '--short'])
    lines = [l for l in status.splitlines() if l.strip()]
    staged = sum(1 for l in lines if l[0] != ' ' and l[0] != '?')
    unstaged = sum(1 for l in lines if l[1] == 'M' or l[1] == 'D')
    untracked = sum(1 for l in lines if l.startswith('??'))
    parts = [f"branch: {branch}"]
    if staged:
        parts.append(f"{staged} staged")
    if unstaged:
        parts.append(f"{unstaged} unstaged changes")
    if untracked:
        parts.append(f"{untracked} untracked")
    if not (staged or unstaged or untracked):
        parts.append("clean")
    return ', '.join(parts)


def _diff_stat(repo: str) -> str:
    """Return git diff --stat for uncommitted changes (short form)."""
    output = _run_git(repo, ['diff', '--stat', 'HEAD'])
    if not output:
        return ''
    # Just the summary line (last line)
    lines = output.splitlines()
    return lines[-1].strip() if lines else ''


class GitTool(Tool):
    name = "git"
    description = "Git status briefing — what repos are active, what you committed today, current branch and status"
    triggers = [
        "git status", "git summary", "git briefing", "git log",
        "what did i work on", "what have i worked on",
        "what did i commit", "what have i committed",
        "what branch", "show git", "git diff",
        "which branch", "any commits today", "commits today",
    ]

    def execute(self, query: str) -> str:
        tl = query.lower()

        # "what did I work on today/this week" — show repos with recent commits
        if any(p in tl for p in ["what did i work on", "what have i worked on",
                                  "what did i commit", "commits today", "any commits today"]):
            return self._worked_on_today()

        # "git status [for X]" or "git summary" — status of all/specific repos
        if any(p in tl for p in ["git status", "git summary", "git briefing", "show git"]):
            return self._full_status(tl)

        # "what branch" / "which branch"
        if any(p in tl for p in ["what branch", "which branch"]):
            return self._branch_info(tl)

        # "git diff"
        if "git diff" in tl:
            return self._diff_info(tl)

        # "git log"
        if "git log" in tl:
            return self._worked_on_today()

        return self._worked_on_today()

    # ── handlers ──────────────────────────────────────────────────────────────

    def _worked_on_today(self) -> str:
        repos = _find_repos()
        active = []
        for repo in repos:
            commits = _commits_today(repo)
            if commits:
                active.append((repo, commits))

        if not active:
            # Fall back to repos with recent uncommitted changes
            dirty = []
            for repo in repos:
                status = _run_git(repo, ['status', '--short'])
                if status.strip():
                    dirty.append(repo)
            if dirty:
                names = ', '.join(_repo_name(r) for r in dirty)
                return f"No commits today, but you've got uncommitted changes in: {names}."
            return "No commits today and everything's clean. Lazy day, babe?"

        lines = ["Here's what you worked on today:"]
        for repo, commits in active:
            lines.append(f"\n{_repo_name(repo)}:")
            for c in commits[:5]:
                lines.append(f"  • {c}")
            if len(commits) > 5:
                lines.append(f"  … and {len(commits) - 5} more")
        return '\n'.join(lines)

    def _full_status(self, tl: str) -> str:
        repos = _find_repos()
        if not repos:
            return "I can't find any git repos in your usual spots."

        # Check if a specific repo is named
        target = self._find_named_repo(tl, repos)
        if target:
            repos = [target]

        lines = []
        for repo in repos:
            summary = _status_summary(repo)
            last = _last_commit_time(repo)
            last_str = last.strftime('%b %d %H:%M') if last else 'no commits'
            lines.append(f"{_repo_name(repo)}: {summary} (last commit: {last_str})")

        return '\n'.join(lines) if lines else "No repos found."

    def _branch_info(self, tl: str) -> str:
        repos = _find_repos()
        target = self._find_named_repo(tl, repos)
        if target:
            branch = _run_git(target, ['branch', '--show-current']) or 'detached HEAD'
            return f"{_repo_name(target)} is on branch: {branch}"

        lines = []
        for repo in repos:
            branch = _run_git(repo, ['branch', '--show-current']) or 'detached'
            lines.append(f"{_repo_name(repo)}: {branch}")
        return '\n'.join(lines) if lines else "No repos found."

    def _diff_info(self, tl: str) -> str:
        repos = _find_repos()
        target = self._find_named_repo(tl, repos)
        if target:
            stat = _diff_stat(target)
            return f"{_repo_name(target)}: {stat}" if stat else f"{_repo_name(target)}: nothing uncommitted."

        lines = []
        for repo in repos:
            stat = _diff_stat(repo)
            if stat:
                lines.append(f"{_repo_name(repo)}: {stat}")
        return '\n'.join(lines) if lines else "Everything's committed, nothing pending."

    def _find_named_repo(self, tl: str, repos: list[str]) -> str | None:
        """Return a repo whose name appears in the query, or None."""
        for repo in repos:
            name = _repo_name(repo).lower()
            if name in tl:
                return repo
        return None
