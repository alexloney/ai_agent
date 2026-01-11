import os
import subprocess
import difflib
import re
import json
import ast
import time
import sys
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from git import Repo

# --- CONFIGURATION ---
REPO_PATH = os.getcwd()

# SANDBOX CONFIGURATION
ENABLE_SANDBOX = True
DOCKER_IMAGE = "python:3.11-slim" 
DOCKER_TEST_COMMAND = "pip install pytest -r requirements.txt -q && pytest"

llm = ChatOllama(
    model="qwen2.5-coder:32b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)

def get_issue_body(issue_number):
    """
    Fetch issue details from GitHub using the gh CLI.
    
    Args:
        issue_number: The GitHub issue number (string or int)
        
    Returns:
        str: JSON string containing issue title and body, or None on error
    """
    try:
        # Validate issue number to prevent command injection
        issue_num_str = str(issue_number).strip()
        if not issue_num_str.isdigit():
            print(f"Error: Invalid issue number '{issue_number}'. Must be a positive integer.")
            return None
            
        # Execute without shell=True to prevent command injection
        result = subprocess.run(
            ["gh", "issue", "view", issue_num_str, "--json", "title,body"],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error fetching issue: {e}")
        return None
    except FileNotFoundError:
        print("Error: 'gh' command not found. Please install GitHub CLI.")
        return None

def create_branch(repo, issue_number):
    """
    Create or checkout a branch for the given issue number.
    
    Args:
        repo: GitPython Repo object
        issue_number: The GitHub issue number
        
    Returns:
        str: The branch name
    """
    branch_name = f"fix/issue-{issue_number}"
    try:
        if branch_name in repo.heads:
            repo.heads[branch_name].checkout()
        else:
            repo.create_head(branch_name).checkout()
        return branch_name
    except Exception as e:
        print(f"Error creating/checking out branch '{branch_name}': {e}")
        raise

def get_file_tree(repo_path):
    """
    Get a list of code files in the repository.
    Restricted to CODE files only (like V10).
    This prevents the AI from getting distracted by READMEs or Configs.
    
    Args:
        repo_path: Path to the git repository
        
    Returns:
        list: List of file paths with code extensions
    """
    try:
        result = subprocess.run(
            ["git", "ls-files"], 
            cwd=repo_path, capture_output=True, text=True, check=True
        )
        files = result.stdout.splitlines()
        
        # REVERTED: Removed .md, .txt, .json, .yml to force focus on logic
        valid_exts = (".py", ".js", ".go", ".html", ".css", ".java", ".rs", ".c", ".h")
        
        return [f for f in files if f.endswith(valid_exts)]
    except subprocess.CalledProcessError as e:
        print(f"Warning: git ls-files failed ({e}). Falling back to os.walk")
        return []
    except Exception as e:
        print(f"Error getting file tree: {e}")
        return [] 

def plan_changes(issue_content, file_list):
    """
    Stage 1: Architect - Identify files that need to be modified.
    
    Args:
        issue_content: The GitHub issue content
        file_list: List of available files in the repository
        
    Returns:
        list: List of file paths that need to be modified
    """
    if not file_list:
        print("Warning: No files to analyze")
        return []
        
    file_list_str = "\n".join(file_list)
    
    # IMPROVED PROMPT: Explicitly warns against documentation
    prompt = ChatPromptTemplate.from_template("""
    You are a Senior Software Architect.
    
    ISSUE:
    {issue}
    
    REPOSITORY FILE LIST:
    {file_list}
    
    TASK:
    Identify the CODE files that need to be modified.
    
    CRITICAL INSTRUCTIONS:
    1. IGNORE documentation files (README.md, etc) unless the issue is ONLY about docs.
    2. Focus on the LOGIC. If the issue requires changing how a link is built, find the Python file that builds the link.
    3. Select ALL files that are part of the logic chain (e.g. the function definition AND the function call).
    
    OUTPUT FORMAT: Output ONLY the filenames, one per line.
    """)
    
    print(f"Scanning {len(file_list)} files to plan changes...")
    chain = prompt | llm
    response = chain.invoke({"issue": issue_content, "file_list": file_list_str})
    
    # Robust Parsing
    lines = response.content.strip().split('\n')
    valid_files = []
    normalized_list = [f.replace("\\", "/") for f in file_list]
    
    for line in lines:
        clean_line = line.strip().strip('"').strip("'").lstrip('- ').replace("\\", "/")
        if clean_line in normalized_list:
            valid_files.append(clean_line.replace("/", os.sep))
            
    return list(set(valid_files))

def check_syntax(code, filename):
    """
    Validate syntax of code files.
    The Linter (Now smart enough to ignore non-Python files).
    
    Args:
        code: The source code to validate
        filename: The filename (used to determine file type)
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    # 1. Skip non-python files
    if not filename.endswith(".py"):
        return True, None
        
    # 2. Parse Python
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

def run_tests_in_sandbox(repo_path):
    """
    Run tests in a Docker sandbox for isolation.
    The Enforcer (Docker Sandbox).
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        tuple: (success: bool, output: str)
    """
    print("\n--- 🔒 STARTING SANDBOXED TEST RUN ---")
    print(f"Image: {DOCKER_IMAGE}")
    
    abs_path = os.path.abspath(repo_path)
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{abs_path}:/app",
        "-w", "/app",
        DOCKER_IMAGE,
        "/bin/bash", "-c", DOCKER_TEST_COMMAND
    ]
    
    try:
        result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print("✅ Tests Passed!")
            return True, result.stdout
        else:
            print("❌ Tests Failed!")
            output = (result.stdout + "\n" + result.stderr).strip()
            # Limit output to last 4000 characters to avoid overwhelming the LLM
            max_output_length = 4000
            return False, output[-max_output_length:] 
    except FileNotFoundError:
        print("Error: Docker executable not found. Is Docker Desktop running?")
        return False, "Docker not found"
    except subprocess.TimeoutExpired:
        print("Error: Test execution timed out after 300 seconds")
        return False, "Test execution timeout"
    except Exception as e:
        print(f"Error running tests: {e}")
        return False, str(e)

def apply_fix(issue_content, filename, file_content, test_error=None):
    """
    Stage 2: Engineer - Apply fixes to a file using LLM.
    Uses safe variable injection to prevent template injection attacks.
    
    Args:
        issue_content: The GitHub issue description
        filename: Name of the file to fix
        file_content: Current content of the file
        test_error: Optional test error message from previous attempt
        
    Returns:
        str: The fixed file content
    """
    
    is_python = filename.endswith(".py")
    
    # 1. Setup the inputs dictionary
    # We pass the dangerous content here so LangChain treats it as raw text, not a template.
    chain_inputs = {
        "issue": issue_content,
        "filename": filename,
        "content": file_content,
        "test_error": str(test_error) if test_error else "",
        "syntax_error": ""
    }
    
    # 2. Define the Template using placeholders {variable}
    # Do NOT use f-strings (f"") here for the content.
    template_str = """
    You are an expert Engineer.
    CONTEXT: Fixing '{filename}'
    ISSUE: {issue}
    FILE CONTENT:
    {content}
    
    STRICT RULES:
    1. Rewrite the ENTIRE file with the fix.
    2. PRESERVE ALL EXISTING COMMENTS/DOCS.
    3. KEEP ORIGINAL INDENTATION.
    """
    
    if is_python:
        template_str += """
    4. OUTPUT ONLY VALID PYTHON CODE.
    5. DO NOT change class constructors (__init__) unless strictly necessary.
    """
    else:
        template_str += """
    4. OUTPUT ONLY THE RAW FILE CONTENT.
    5. Do not wrap in markdown code blocks if the file is already a markdown file.
    """

    if test_error:
        template_str += "\n\nCRITICAL: PREVIOUS FIX FAILED TESTS:\n{test_error}\nFIX THE CODE."

    print(f"Applying fix to {filename}...")
    
    for attempt in range(3):
        # Handle Syntax Retry Logic
        current_template = template_str
        if chain_inputs["syntax_error"]:
            current_template += "\n\nPREVIOUS ATTEMPT HAD SYNTAX ERROR:\n{syntax_error}\nTRY AGAIN."

        # Create the Template
        prompt = ChatPromptTemplate.from_template(current_template)
        chain = prompt | llm
        
        # Invoke with the Dictionary (Safe!)
        response = chain.invoke(chain_inputs)
        
        code = response.content
        
        # Cleanup Markdown wrappers
        if code.strip().startswith("```"):
            lines = code.splitlines()
            if lines[0].startswith("```"): lines = lines[1:]
            if lines[-1].startswith("```"): lines = lines[:-1]
            code = "\n".join(lines)
            
        # Run Linter
        is_valid, error_msg = check_syntax(code, filename)
        if is_valid:
            return code
        
        print(f"  ...Syntax Error on attempt {attempt+1}: {error_msg}")
        # Update the inputs for the next loop iteration
        chain_inputs["syntax_error"] = error_msg

    print("Warning: Failed to generate valid syntax. Saving best effort.")
    return code

def extract_json_with_fallback(text):
    """
    Extract JSON from LLM response with fallback.
    
    Args:
        text: The response text from the LLM
        
    Returns:
        dict: Parsed JSON or fallback dictionary
    """
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match: 
            return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse JSON from LLM response: {e}")
    except Exception as e:
        print(f"Warning: Unexpected error parsing JSON: {e}")
    
    # Fallback to default values
    return { "commit_message": "fix: resolve issue", "pr_title": "Fix", "pr_body": text }

def generate_pr_content(issue_data, diff):
    """
    Stage 3: Manager - Generate commit message and PR content.
    
    Args:
        issue_data: The GitHub issue data
        diff: Git diff of the changes
        
    Returns:
        dict: Dictionary with commit_message, pr_title, and pr_body
    """
    prompt = ChatPromptTemplate.from_template("""
    You are a Senior Developer.
    ISSUE: {issue}
    CHANGES MADE (Diff):
    {diff}
    TASK: Generate Commit Message, PR Title, and PR Description.
    OUTPUT FORMAT (Strict JSON): {{ "commit_message": "...", "pr_title": "...", "pr_body": "..." }}
    """)
    print("Generating PR documentation...")
    chain = prompt | llm
    response = chain.invoke({"issue": issue_data, "diff": diff})
    return extract_json_with_fallback(response.content)

# --- MAIN EXECUTION ---
def main():
    """Main execution function for the AI agent."""
    print(f"--- Agent V12 (Smart Linter) ---")
    
    # Get issue number from user input
    github_issue_number = input("Enter Issue Number to fix: ").strip()
    if not github_issue_number:
        print("Error: Issue number is required")
        sys.exit(1)
    
    try:
        repo = Repo(REPO_PATH)
    except Exception as e:
        print(f"Error: Failed to open git repository at {REPO_PATH}: {e}")
        sys.exit(1)
    
    issue_data = get_issue_body(github_issue_number)
    if not issue_data:
        print("Error: Failed to fetch issue data")
        sys.exit(1)
    
    try:
        branch = create_branch(repo, github_issue_number)
    except Exception as e:
        print(f"Error: Failed to create branch: {e}")
        sys.exit(1)
        
    file_tree = get_file_tree(REPO_PATH)
    
    target_files = plan_changes(issue_data, file_tree)
    print(f"Plan: Fixing {len(target_files)} files -> {target_files}")
    
    if not target_files:
        print("Agent decided no files needed fixing.")
        sys.exit(0)
        
    # EXECUTE
    for target_file in target_files:
        full_path = os.path.join(REPO_PATH, target_file)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                old_content = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {full_path}")
            continue
        except Exception as e:
            print(f"Error reading file {full_path}: {e}")
            continue
        
        new_code = apply_fix(issue_data, target_file, old_content)
        
        # Write to disk
        try:
            with open(full_path, "w", encoding="utf-8", newline='\n') as f:
                f.write(new_code.replace('\r\n', '\n'))
        except Exception as e:
            print(f"Error writing file {full_path}: {e}")
            sys.exit(1)

    # VERIFY
    if ENABLE_SANDBOX:
        test_passed, test_log = run_tests_in_sandbox(REPO_PATH)
        if not test_passed:
            print("\n⚠️ TESTS FAILED. Entering Repair Loop...")
            primary_file = target_files[0] 
            full_path = os.path.join(REPO_PATH, primary_file)
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    current_content = f.read()
                repaired_code = apply_fix(issue_data, primary_file, current_content, test_error=test_log)
                with open(full_path, "w", encoding="utf-8", newline='\n') as f:
                    f.write(repaired_code.replace('\r\n', '\n'))
            except Exception as e:
                print(f"Error in repair loop: {e}")
                sys.exit(1)

    # COMMIT
    try:
        repo.index.add(target_files)
        git_diff = repo.git.diff("--cached")
        if not git_diff.strip():
            print("No changes detected. Aborting.")
            sys.exit(0)

        pr_details = generate_pr_content(issue_data, git_diff)
        print(f"Commit Message: {pr_details['commit_message']}")
        repo.index.commit(pr_details['commit_message'])
        
        print("Pushing...")
        repo.remote(name='origin').push(branch, set_upstream=True)
        subprocess.run([
            "gh", "pr", "create", 
            "--title", pr_details['pr_title'], 
            "--body", pr_details['pr_body']
        ], check=True)
        print("✅ Successfully created PR!")
    except subprocess.CalledProcessError as e:
        print(f"Error creating PR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error in commit/push process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
