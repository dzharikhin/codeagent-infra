"""Consolidated git operations."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import subprocess

from opencode_framework.models import GitResult
from opencode_framework.exceptions import GitError


@dataclass
class GitBranchInfo:
    """Information about a Git branch."""
    
    name: str
    exists: bool
    is_orphan: bool = False


@dataclass
class WorktreeResult:
    """Result of worktree creation."""
    
    success: bool
    path: Optional[Path] = None
    error: Optional[str] = None


class GitOperations:
    """Unified interface for all git operations."""
    
    @staticmethod
    def run_command(
        args: List[str],
        cwd: Optional[Path] = None,
        check: bool = False,
    ) -> GitResult:
        """Run a git command and return a structured result.
        
        Args:
            args: Git command arguments
            cwd: Working directory for the command
            check: Whether to raise on non-zero exit code
            
        Returns:
            GitResult with success status and output
            
        Raises:
            GitError: If check=True and command fails
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60,
                check=check,
            )
            
            git_result = GitResult(
                success=result.returncode == 0,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                returncode=result.returncode,
            )
            
            return git_result
            
        except subprocess.CalledProcessError as e:
            return GitResult(
                success=False,
                stdout=e.stdout or "",
                stderr=e.stderr or "",
                returncode=e.returncode,
            )
        except subprocess.TimeoutExpired:
            return GitResult(
                success=False,
                stdout="",
                stderr="Git command timed out",
                returncode=-1,
            )
        except FileNotFoundError:
            return GitResult(
                success=False,
                stdout="",
                stderr="git command not found",
                returncode=-1,
            )
    
    @staticmethod
    def branch_exists(
        branch_name: str,
        cwd: Optional[Path] = None,
    ) -> bool:
        """Check if a branch exists locally.
        
        Args:
            branch_name: Name of the branch
            cwd: Working directory
            
        Returns:
            True if branch exists
        """
        result = GitOperations.run_command(
            ["rev-parse", "--verify", f"refs/heads/{branch_name}"],
            cwd=cwd,
        )
        return result.success
    
    @staticmethod
    def get_current_branch(cwd: Optional[Path] = None) -> Optional[str]:
        """Get the current branch name.
        
        Args:
            cwd: Working directory
            
        Returns:
            Current branch name or None
        """
        result = GitOperations.run_command(
            ["branch", "--show-current"],
            cwd=cwd,
        )
        if result.success and result.stdout:
            return result.stdout
        return None
    
    @staticmethod
    def is_inside_git_tree(path: Path) -> bool:
        """Check if path is inside a Git working tree.
        
        Args:
            path: Path to check
            
        Returns:
            True if inside a git tree
        """
        result = GitOperations.run_command(
            ["rev-parse", "--is-inside-work-tree"],
            cwd=path,
        )
        return result.success
    
    @staticmethod
    def get_repo_root(path: Path) -> Optional[Path]:
        """Get the repository root for the given path.
        
        Args:
            path: Path inside the repository
            
        Returns:
            Repository root path or None if not in a repo
        """
        result = GitOperations.run_command(
            ["rev-parse", "--show-toplevel"],
            cwd=path,
        )
        if result.success and result.stdout:
            return Path(result.stdout)
        return None
    
    @staticmethod
    def is_bare_repository(path: Path) -> bool:
        """Check if repository is bare.
        
        Args:
            path: Path to repository
            
        Returns:
            True if bare repository
        """
        result = GitOperations.run_command(
            ["rev-parse", "--is-bare-repository"],
            cwd=path,
        )
        return result.success and result.stdout.lower() == "true"
    
    @staticmethod
    def has_staged_changes(path: Path) -> bool:
        """Check if there are staged changes.
        
        Args:
            path: Working directory
            
        Returns:
            True if there are staged changes
        """
        result = GitOperations.run_command(
            ["diff", "--cached", "--quiet"],
            cwd=path,
        )
        return not result.success
    
    @staticmethod
    def create_orphan_branch(
        branch_name: str,
        cwd: Optional[Path] = None,
    ) -> bool:
        """Create an orphan branch with no commit history.
        
        Args:
            branch_name: Name of new branch
            cwd: Working directory
            
        Returns:
            True on success
        """
        result = GitOperations.run_command(
            ["checkout", "--orphan", branch_name],
            cwd=cwd,
        )
        if not result.success:
            return False
        
        result = GitOperations.run_command(
            ["reset", "--hard"],
            cwd=cwd,
        )
        return result.success
    
    @staticmethod
    def create_worktree(
        worktree_path: Path,
        branch_name: str,
        cwd: Optional[Path] = None,
    ) -> WorktreeResult:
        """Create a linked worktree.
        
        If branch doesn't exist, creates it as an orphan branch.
        
        Args:
            worktree_path: Path where worktree will be created
            branch_name: Branch name (creates orphan if doesn't exist)
            cwd: Repository root
            
        Returns:
            WorktreeResult with success status
        """
        if GitOperations.branch_exists(branch_name, cwd=cwd):
            result = GitOperations.run_command(
                ["worktree", "add", str(worktree_path), branch_name],
                cwd=cwd,
            )
        else:
            result = GitOperations.run_command(
                [
                    "worktree", "add",
                    "--orphan",
                    "-b", branch_name,
                    str(worktree_path),
                ],
                cwd=cwd,
            )
        
        if not result.success:
            return WorktreeResult(
                success=False,
                error=result.stderr or "Failed to create worktree",
            )
        
        return WorktreeResult(
            success=True,
            path=worktree_path,
        )
    
    @staticmethod
    def remove_worktree(
        worktree_path: Path,
        cwd: Optional[Path] = None,
    ) -> bool:
        """Remove a worktree.
        
        Args:
            worktree_path: Path to worktree
            cwd: Repository root
            
        Returns:
            True on success
        """
        result = GitOperations.run_command(
            ["worktree", "remove", str(worktree_path), "--force"],
            cwd=cwd,
        )
        return result.success
    
    @staticmethod
    def list_worktrees(cwd: Optional[Path] = None) -> List[Path]:
        """List all worktree paths.
        
        Args:
            cwd: Repository root
            
        Returns:
            List of worktree paths
        """
        result = GitOperations.run_command(
            ["worktree", "list", "--porcelain"],
            cwd=cwd,
        )
        
        worktrees = []
        if result.success:
            for line in result.stdout.splitlines():
                if line.startswith("worktree "):
                    worktree_path = Path(line.split(" ", 1)[1])
                    worktrees.append(worktree_path)
        
        return worktrees
    
    @staticmethod
    def is_worktree(path: Path) -> bool:
        """Check if the given path is a worktree.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is a worktree
        """
        git_file = path / ".git"
        return git_file.is_file()
    
    @staticmethod
    def get_worktree_gitdir(worktree_path: Path) -> Optional[Path]:
        """Get the .git directory for a worktree.
        
        Args:
            worktree_path: Path to worktree
            
        Returns:
            Path to .git directory or None
        """
        git_file = worktree_path / ".git"
        if git_file.is_file():
            content = git_file.read_text().strip()
            if content.startswith("gitdir: "):
                gitdir = content[8:]
                return worktree_path / gitdir
        return None
    
    @staticmethod
    def make_initial_commit(
        message: str,
        cwd: Optional[Path] = None,
        allow_empty: bool = True,
    ) -> bool:
        """Create an initial commit.
        
        Args:
            message: Commit message
            cwd: Working directory
            allow_empty: Whether to allow empty commit
            
        Returns:
            True on success
        """
        args = ["commit", "-m", message]
        if allow_empty:
            args.append("--allow-empty")
        
        result = GitOperations.run_command(args, cwd=cwd)
        return result.success
    
    @staticmethod
    def add_all_files(cwd: Optional[Path] = None) -> bool:
        """Stage all files in the working directory.
        
        Args:
            cwd: Working directory
            
        Returns:
            True on success
        """
        result = GitOperations.run_command(["add", "."], cwd=cwd)
        return result.success
    
    @staticmethod
    def setup_opencode_worktree(
        repo_root: Path,
        branch_name: str,
        opencode_dir: Path,
    ) -> WorktreeResult:
        """Set up the .opencode directory as a worktree.
        
        This function:
        1. Creates the worktree at .opencode/
        2. Uses an orphan branch if it doesn't exist
        3. Creates an initial empty commit
        
        Args:
            repo_root: Repository root
            branch_name: Branch name for worktree
            opencode_dir: Path to .opencode directory
            
        Returns:
            WorktreeResult with success status
        """
        existing_branch = GitOperations.branch_exists(branch_name, cwd=repo_root)
        
        result = GitOperations.create_worktree(
            opencode_dir,
            branch_name,
            cwd=repo_root,
        )
        
        if not result.success:
            return result
        
        if not existing_branch:
            success = GitOperations.make_initial_commit(
                message="Initial OpenCode framework configuration",
                cwd=opencode_dir,
                allow_empty=True,
            )
            if not success:
                GitOperations.remove_worktree(opencode_dir, cwd=repo_root)
                return WorktreeResult(
                    success=False,
                    error="Failed to create initial commit",
                )
        
        return result
