"""
Git sync helpers for recipe submodule.
"""
import subprocess
from pathlib import Path
from datetime import datetime

RECIPES_PATH = Path(__file__).parent / "reseptit"


def run_git(*args) -> tuple[bool, str]:
    """Run a git command in the recipes directory."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=RECIPES_PATH,
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def get_status() -> dict:
    """Get git status of recipes directory."""
    success, output = run_git("status", "--porcelain")
    
    if not success:
        return {"error": output, "has_changes": False, "files": []}
    
    files = [line.strip() for line in output.split('\n') if line.strip()]
    return {
        "has_changes": len(files) > 0,
        "files": files,
        "error": None
    }


def pull() -> tuple[bool, str]:
    """Pull latest changes from remote."""
    return run_git("pull", "--rebase")


def sync() -> dict:
    """Full sync: pull, add, commit, push."""
    result = {
        "success": False,
        "message": "",
        "details": []
    }
    
    # Check status first
    status = get_status()
    if status.get("error"):
        result["message"] = f"Git error: {status['error']}"
        return result
    
    # Pull first
    pull_ok, pull_msg = pull()
    result["details"].append(f"Pull: {pull_msg or 'OK'}")
    
    if not pull_ok and "conflict" in pull_msg.lower():
        result["message"] = "Conflict detected - manual fix needed"
        return result
    
    # If no local changes, we're done
    if not status["has_changes"]:
        result["success"] = True
        result["message"] = "Already up to date"
        return result
    
    # Add all changes
    add_ok, add_msg = run_git("add", ".")
    result["details"].append(f"Add: {add_msg or 'OK'}")
    
    if not add_ok:
        result["message"] = f"Failed to stage: {add_msg}"
        return result
    
    # Commit
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_msg = f"Update recipes {timestamp}"
    commit_ok, commit_out = run_git("commit", "-m", commit_msg)
    result["details"].append(f"Commit: {commit_out or 'OK'}")
    
    if not commit_ok and "nothing to commit" not in commit_out.lower():
        result["message"] = f"Failed to commit: {commit_out}"
        return result
    
    # Push
    push_ok, push_msg = run_git("push")
    result["details"].append(f"Push: {push_msg or 'OK'}")
    
    if not push_ok:
        result["message"] = f"Failed to push: {push_msg}"
        return result
    
    result["success"] = True
    result["message"] = f"Synced {len(status['files'])} file(s)"
    return result
