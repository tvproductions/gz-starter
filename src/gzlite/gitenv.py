"""Environment isolation for git subprocesses."""

from __future__ import annotations

import os


def clean_git_env() -> dict[str, str]:
    """Return a copy of the environment with every ``GIT_*`` variable removed.

    Git hooks and worktrees export variables such as ``GIT_DIR``,
    ``GIT_INDEX_FILE`` and ``GIT_COMMON_DIR`` that silently redirect any git
    command to the invoking repository. A command aimed at another directory
    must not inherit them.
    """
    return {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
