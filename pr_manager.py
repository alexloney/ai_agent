"""
PR Manager for handling GitHub Pull Request operations.

This module manages the lifecycle of a pull request including:
- Creating WIP PRs
- Updating PR descriptions
- Finalizing PRs
- Committing and pushing changes
"""

import subprocess
import json
import re
from typing import Optional, Dict


class PRManager:
    """Manages GitHub Pull Request operations."""
    
    def __init__(self, repo, branch_name: str, issue_number: str, repo_path: str = None):
        """
        Initialize PR Manager.
        
        Args:
            repo: GitPython Repo object
            branch_name: Name of the branch
            issue_number: GitHub issue number
            repo_path: Path to the repository (for gh commands)
        """
        self.repo = repo
        self.branch_name = branch_name
        self.issue_number = issue_number
        self.repo_path = repo_path or repo.working_dir
        self.pr_number = None
        self.pr_url = None
        self.is_wip = True
        self.initial_body = None  # Store the initial detailed body
    
    def create_wip_pr(self, title: str, initial_body: str) -> bool:
        """
        Create a WIP (Work In Progress) pull request.
        
        Args:
            title: PR title (will be prefixed with [WIP])
            initial_body: Initial PR description
            
        Returns:
            True if successful, False otherwise
        """
        wip_title = f"[WIP] {title}"
        
        # Store the initial body to preserve implementation details
        self.initial_body = initial_body
        
        try:
            # Push the branch first
            print(f"Pushing branch {self.branch_name} to origin...")
            self.repo.remote(name='origin').push(self.branch_name, set_upstream=True)
            
            # Create the PR
            print(f"Creating WIP PR: {wip_title}")
            result = subprocess.run(
                ["gh", "pr", "create", 
                 "--title", wip_title,
                 "--body", initial_body],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Extract PR URL from output
            self.pr_url = result.stdout.strip()
            
            # Extract PR number from URL
            pr_match = re.search(r'/pull/(\d+)', self.pr_url)
            if pr_match:
                self.pr_number = pr_match.group(1)
            
            print(f"✅ Created WIP PR: {self.pr_url}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error creating PR: {e}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            return False
    
    def update_pr_body(self, new_body: str) -> bool:
        """
        Update the PR description.
        
        Args:
            new_body: New PR body content
            
        Returns:
            True if successful, False otherwise
        """
        if not self.pr_number:
            print("Warning: PR number not found, cannot update")
            return False
        
        try:
            subprocess.run(
                ["gh", "pr", "edit", self.pr_number,
                 "--body", new_body],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✅ Updated PR #{self.pr_number} description")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error updating PR: {e}")
            return False
    
    def finalize_pr(self, final_title: str, final_body: str) -> bool:
        """
        Finalize the PR by removing WIP prefix and updating content.
        
        Args:
            final_title: Final PR title (without WIP prefix)
            final_body: Final PR description
            
        Returns:
            True if successful, False otherwise
        """
        if not self.pr_number:
            print("Warning: PR number not found, cannot finalize")
            return False
        
        try:
            subprocess.run(
                ["gh", "pr", "edit", self.pr_number,
                 "--title", final_title,
                 "--body", final_body],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            self.is_wip = False
            print(f"✅ Finalized PR #{self.pr_number}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error finalizing PR: {e}")
            return False
    
    def commit_and_push(self, files: list, commit_message: str) -> bool:
        """
        Commit changes and push to remote.
        
        Args:
            files: List of files to commit
            commit_message: Commit message
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Stage files
            self.repo.index.add(files)
            
            # Check if there are changes to commit
            # Handle case where there's no HEAD yet (new repo)
            try:
                if not self.repo.index.diff("HEAD"):
                    print("No changes to commit")
                    return True
            except Exception:
                # No HEAD exists yet (new repo), proceed with commit
                pass
            
            # Commit
            print(f"Committing: {commit_message}")
            self.repo.index.commit(commit_message)
            
            # Push
            print(f"Pushing to {self.branch_name}...")
            self.repo.remote(name='origin').push(self.branch_name)
            
            print("✅ Committed and pushed changes")
            return True
            
        except Exception as e:
            print(f"Error committing/pushing: {e}")
            return False
    
    def add_pr_comment(self, comment_body: str) -> bool:
        """
        Add a comment to the PR instead of overwriting the description.
        
        Args:
            comment_body: Comment content
            
        Returns:
            True if successful, False otherwise
        """
        if not self.pr_number:
            print("Warning: PR number not found, cannot add comment")
            return False
        
        try:
            subprocess.run(
                ["gh", "pr", "comment", self.pr_number,
                 "--body", comment_body],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✅ Added comment to PR #{self.pr_number}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error adding PR comment: {e}")
            return False
    
    def update_progress(self, phase: str, description: str, details: dict = None) -> bool:
        """
        Update PR progress by adding a timestamped comment.
        This preserves the original PR description and creates a history.
        
        Args:
            phase: Current phase name
            description: Description of current work
            details: Optional dictionary with additional details (files, results, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        import datetime
        
        # Maximum files to display in progress updates
        MAX_FILES_TO_DISPLAY = 10
        
        # Build progress comment with timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        progress_comment = f"""## 🚧 Progress Update - {timestamp}

### Phase: {phase}

{description}
"""
        
        # Add details if provided
        if details:
            if 'files_modified' in details and details['files_modified']:
                progress_comment += f"\n**Files Modified:** {len(details['files_modified'])}\n"
                for f in details['files_modified'][:MAX_FILES_TO_DISPLAY]:
                    progress_comment += f"- `{f}`\n"
                if len(details['files_modified']) > MAX_FILES_TO_DISPLAY:
                    progress_comment += f"- ... and {len(details['files_modified']) - MAX_FILES_TO_DISPLAY} more\n"
            
            if 'files_created' in details and details['files_created']:
                progress_comment += f"\n**Files Created:** {len(details['files_created'])}\n"
                for f in details['files_created'][:MAX_FILES_TO_DISPLAY]:
                    progress_comment += f"- `{f}`\n"
                if len(details['files_created']) > MAX_FILES_TO_DISPLAY:
                    progress_comment += f"- ... and {len(details['files_created']) - MAX_FILES_TO_DISPLAY} more\n"
            
            if 'test_status' in details:
                progress_comment += f"\n**Test Status:** {details['test_status']}\n"
            
            if 'review_status' in details:
                progress_comment += f"\n**Review Status:** {details['review_status']}\n"
            
            if 'iteration' in details:
                progress_comment += f"\n**Iteration:** {details['iteration']}\n"
            
            if 'message' in details:
                progress_comment += f"\n{details['message']}\n"
        
        return self.add_pr_comment(progress_comment)


def parse_pr_content(llm_response: str) -> Dict[str, str]:
    """
    Parse PR content from LLM response.
    
    Handles JSON responses and fallback parsing.
    
    Args:
        llm_response: Raw LLM response text
        
    Returns:
        Dictionary with commit_message, pr_title, and pr_body
    """
    # Try to extract and parse JSON more carefully
    try:
        # Look for the first complete JSON object
        start_idx = llm_response.find('{')
        if start_idx != -1:
            # Find matching closing brace using a simple counter
            brace_count = 0
            end_idx = -1
            for i in range(start_idx, len(llm_response)):
                if llm_response[i] == '{':
                    brace_count += 1
                elif llm_response[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            
            if end_idx != -1:
                json_str = llm_response[start_idx:end_idx]
                data = json.loads(json_str)
                # Validate required fields
                if 'commit_message' in data and 'pr_title' in data and 'pr_body' in data:
                    return data
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Fallback: use the entire response as PR body
    print("Warning: Could not parse JSON from LLM response, using fallback")
    return {
        "commit_message": "fix: resolve issue",
        "pr_title": "Fix issue",
        "pr_body": llm_response
    }
