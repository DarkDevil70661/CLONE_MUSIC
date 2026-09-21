import asyncio
import os
import shlex
import shutil
from typing import Tuple

# ---------------------------------------------------------
# Git executable configuration
# ---------------------------------------------------------

GIT_EXECUTABLE = shutil.which("git")

if GIT_EXECUTABLE:
    os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
else:
    # Heroku + heroku-buildpack-apt সাধারণত এখানে Git রাখে
    os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = "/usr/bin/git"


from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

import config

from ..logging import LOGGER


# ---------------------------------------------------------
# Install requirements
# ---------------------------------------------------------

def install_req(cmd: str) -> Tuple[str, str, int, int]:

    async def install_requirements():

        args = shlex.split(cmd)

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        return (
            stdout.decode("utf-8", "replace").strip(),
            stderr.decode("utf-8", "replace").strip(),
            process.returncode,
            process.pid,
        )

    return asyncio.get_event_loop().run_until_complete(
        install_requirements()
    )


# ---------------------------------------------------------
# Git updater
# ---------------------------------------------------------

def git():

    REPO_LINK = config.UPSTREAM_REPO

    # -----------------------------------------------------
    # Git token authentication
    # -----------------------------------------------------

    if config.GIT_TOKEN:

        GIT_USERNAME = REPO_LINK.split("com/")[1].split("/")[0]

        TEMP_REPO = REPO_LINK.split("https://")[1]

        UPSTREAM_REPO = (
            f"https://{GIT_USERNAME}:{config.GIT_TOKEN}@{TEMP_REPO}"
        )

    else:

        UPSTREAM_REPO = config.UPSTREAM_REPO

    # -----------------------------------------------------
    # Check Git executable
    # -----------------------------------------------------

    git_path = shutil.which("git")

    if not git_path:

        git_path = "/usr/bin/git"

    if not os.path.exists(git_path):

        LOGGER(__name__).error(
            "Git executable was not found. "
            "Please install Git on the system."
        )

        return

    os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = git_path

    LOGGER(__name__).info(
        f"Git executable found: {git_path}"
    )

    # -----------------------------------------------------
    # Open repository
    # -----------------------------------------------------

    try:

        repo = Repo(os.getcwd())

        LOGGER(__name__).info(
            "[VPS DEPLOYER] Git Client Found"
        )

    except InvalidGitRepositoryError:

        LOGGER(__name__).info(
            "[VPS DEPLOYER] Initializing Git repository..."
        )

        repo = Repo.init(os.getcwd())

        # -------------------------------------------------
        # Configure origin
        # -------------------------------------------------

        if "origin" in repo.remotes:

            origin = repo.remote("origin")

        else:

            origin = repo.create_remote(
                "origin",
                UPSTREAM_REPO
            )

        # -------------------------------------------------
        # Fetch upstream
        # -------------------------------------------------

        try:

            origin.fetch()

            LOGGER(__name__).info(
                "Successfully fetched upstream repository."
            )

        except GitCommandError as e:

            LOGGER(__name__).error(
                f"Git fetch failed: {e}"
            )

            return

        # -------------------------------------------------
        # Create branch
        # -------------------------------------------------

        try:

            branch = config.UPSTREAM_BRANCH

            repo.create_head(
                branch,
                origin.refs[branch]
            )

            repo.heads[branch].set_tracking_branch(
                origin.refs[branch]
            )

            repo.heads[branch].checkout(True)

        except GitCommandError as e:

            LOGGER(__name__).error(
                f"Git branch setup failed: {e}"
            )

            return

        # -------------------------------------------------
        # Pull latest changes
        # -------------------------------------------------

        try:

            nrs = repo.remote("origin")

            nrs.fetch(config.UPSTREAM_BRANCH)

            try:

                nrs.pull(config.UPSTREAM_BRANCH)

            except GitCommandError:

                LOGGER(__name__).warning(
                    "Git pull failed. Performing hard reset..."
                )

                repo.git.reset(
                    "--hard",
                    "FETCH_HEAD"
                )

        except GitCommandError as e:

            LOGGER(__name__).error(
                f"Git update failed: {e}"
            )

            return

        # -------------------------------------------------
        # Install requirements
        # -------------------------------------------------

        stdout, stderr, returncode, pid = install_req(
            "pip3 install --no-cache-dir -r requirements.txt"
        )

        if stdout:

            LOGGER(__name__).info(
                stdout
            )

        if stderr:

            LOGGER(__name__).warning(
                stderr
            )

        if returncode != 0:

            LOGGER(__name__).error(
                f"requirements.txt installation failed "
                f"with exit code {returncode}"
            )

            return

        LOGGER(__name__).info(
            "Fetching updates from upstream repository..."
        )


    except GitCommandError as e:

        LOGGER(__name__).error(
            f"Git command failed: {e}"
        )

    except Exception as e:

        LOGGER(__name__).error(
            f"Unexpected Git error: {e}"
        )
