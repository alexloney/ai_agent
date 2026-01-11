import os
import subprocess
import re
import json
import ast
import sys
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

# --- CONFIGURATION ---
REPO_PATH = os.getcwd()

# SANDBOX CONFIGURATION
ENABLE_SANDBOX = True
DOCKER_IMAGE = "python:3.11-slim" 
DOCKER_TEST_COMMAND = "pip install pytest -r requirements.txt -q && pytest"

# OUTPUT CONFIGURATION
MAX_TEST_OUTPUT_LENGTH = 4000  
DOCKER_TIMEOUT = 300  

llm = ChatOllama(
    model="qwen2.5-coder:32b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)

def get_issue_body(issue_number):
    """Fetch issue details from GitHub using the gh CLI."""
    try:
        issue_num_str = str(issue_number).strip()
        if not issue_num_str.isdigit():
            print(f"Error: Invalid issue number '{issue_number}'. Must be a positive integer.")
            return None
            
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
    branch_name = f"fix/issue-{issue_number}"
    try:
        if branch_name in repo.heads:
            repo.heads[branch_name].checkout()
        else:
            repo.create_head(branch_name).checkout()
        return branch_name
    except GitCommandError as e:
        print(f"Error creating/checking out branch '{branch_name}': {e}")
        raise

def get_file_tree(repo_path):
    """Get a list of CODE files (ignoring docs/configs)."""
    try:
        result = subprocess.run(
            ["git", "ls-files"], 
            cwd=repo_path, capture_output=True, text=True, check=True
        )
        files = result.stdout.splitlines()
        # V14: Keep restricted extensions to focus on logic
        valid_exts = (".py", ".js", ".go", ".html", ".css", ".java", ".rs", ".c", ".h")
        return [f for f in files if f.endswith(valid_exts)]
    except Exception as e:
        print(f"Warning: git ls-files failed ({e}). Using fallback method")
        files = []
        valid_exts = (".py", ".js", ".go", ".html", ".css", ".java", ".rs", ".c", ".h")
        for root, _, filenames in os.walk(repo_path):
            if '.git' in root: continue
            for filename in filenames:
                if filename.endswith(valid_exts):
                    rel_path = os.path.relpath(os.path.join(root, filename), repo_path)
                    files.append(rel_path)
        return files

def plan_changes(issue_content, file_list):
    if not file_list:
        print("Warning: No files to analyze")
        return []
        
    file_list_str = "\n".join(file_list)
    prompt = ChatPromptTemplate.from_template("""
    You are a Senior Software Architect.
    ISSUE: {issue}
    FILES: {file_list}
    TASK: Identify the CODE files that need to be modified.
    CRITICAL INSTRUCTIONS:
    1. IGNORE documentation files (README.md, etc).
    2. Focus on the LOGIC. 
    OUTPUT FORMAT: Output ONLY the filenames, one per line.
    """)
    print(f"Scanning {len(file_list)} files to plan changes...")
    chain = prompt | llm
    response = chain.invoke({"issue": issue_content, "file_list": file_list_str})
    
    lines = response.content.strip().split('\n')
    valid_files = []
    normalized_list = [f.replace("\\", "/") for f in file_list]
    for line in lines:
        clean_line = line.strip().strip('"').strip("'").lstrip('- ').replace("\\", "/")
        if clean_line in normalized_list:
            valid_files.append(clean_line.replace("/", os.sep))
    return list(set(valid_files))

def check_syntax(code, filename):
    if not filename.endswith(".py"): return True, None
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}\nLine content: {e.text}"
    except Exception as e:
        return False, str(e)

def run_tests_in_sandbox(repo_path):
    print("\n--- 🔒 STARTING SANDBOXED TEST RUN ---")
    abs_path = os.path.abspath(repo_path)
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{abs_path}:/app",
        "-w", "/app",
        DOCKER_IMAGE,
        "/bin/bash", "-c", DOCKER_TEST_COMMAND
    ]
    try:
        # V14: Using Copilot's timeout logic
        result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=DOCKER_TIMEOUT)
        if result.returncode == 0:
            print("✅ Tests Passed!")
            return True, result.stdout
        else:
            print("❌ Tests Failed!")
            output = (result.stdout + "\n" + result.stderr).strip()
            return False, output[-MAX_TEST_OUTPUT_LENGTH:] 
    except FileNotFoundError:
        print("Error: Docker executable not found.")
        return False, "Docker not found"
    except subprocess.TimeoutExpired:
        print(f"Error: Test execution timed out after {DOCKER_TIMEOUT}s")
        return False, "Timeout"

def clean_llm_response(text):
    """
    V14 (Restored): Aggressively extracts code from LLM chatter.
    """
    # Pattern 1: Markdown code blocks
    code_block = re.search(r'```(?:python)?\s*(.*?)```', text, re.DOTALL | re.IGNORECASE)
    if code_block:
        return code_block.group(1).strip()
    
    # Pattern 2: Fallback - Strip preamble
    lines = text.splitlines()
    start_index = 0
    for i, line in enumerate(lines):
        if line.strip().startswith(('import ', 'from ', 'def ', 'class ', '@', '#')):
            start_index = i
            break
    if start_index > 0:
        return "\n".join(lines[start_index:])
    return text.strip()

def apply_fix(issue_content, filename, file_content, test_error=None):
    is_python = filename.endswith(".py")
    
    chain_inputs = {
        "issue": issue_content,
        "filename": filename,
        "content": file_content,
        "test_error": str(test_error) if test_error else "",
        "syntax_error": ""
    }
    
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
    4. OUTPUT ONLY CODE. NO CONVERSATIONAL TEXT.
    """
    
    if is_python:
        template_str += "\n5. OUTPUT ONLY VALID PYTHON CODE."
    
    if test_error:
        template_str += "\n\nCRITICAL: PREVIOUS FIX FAILED TESTS:\n{test_error}\nFIX THE CODE."

    print(f"Applying fix to {filename}...")
    
    for attempt in range(3):
        if chain_inputs["syntax_error"]:
            template_str += "\n\nPREVIOUS ATTEMPT HAD SYNTAX ERROR:\n{syntax_error}\nREMOVE ALL NON-CODE TEXT."

        prompt = ChatPromptTemplate.from_template(template_str)
        chain = prompt | llm
        response = chain.invoke(chain_inputs)
        
        # V14: Restored Aggressive Cleaning
        code = clean_llm_response(response.content)
            
        is_valid, error_msg = check_syntax(code, filename)
        if is_valid:
            return code
        
        print(f"  ...Syntax Error on attempt {attempt+1}: {error_msg}")
        chain_inputs["syntax_error"] = error_msg

    print("Warning: Failed to generate valid syntax. Saving best effort.")
    return code

def extract_json_with_fallback(text):
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match: return json.loads(match.group(0))
    except: pass
    return { "commit_message": "fix: resolve issue", "pr_title": "Fix", "pr_body": text }

def generate_pr_content(issue_data, diff):
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
    print(f"--- Agent V14 (Safe & Smart) ---")
    
    github_issue_number = input("Enter Issue Number to fix: ").strip()
    if not github_issue_number:
        print("Error: Issue number is required")
        sys.exit(1)
    
    try:
        repo = Repo(REPO_PATH)
    except InvalidGitRepositoryError:
        print(f"Error: {REPO_PATH} is not a valid git repository")
        sys.exit(1)
        
    issue_data = get_issue_body(github_issue_number)
    if not issue_data: sys.exit(1)
    
    try:
        branch = create_branch(repo, github_issue_number)
    except Exception as e:
        print(f"Error creating branch: {e}")
        sys.exit(1)
        
    file_tree = get_file_tree(REPO_PATH)
    target_files = plan_changes(issue_data, file_tree)
    print(f"Plan: Fixing {len(target_files)} files -> {target_files}")
    if not target_files: sys.exit(0)
        
    # EXECUTE
    for target_file in target_files:
        full_path = os.path.join(REPO_PATH, target_file)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                old_content = f.read()
            new_code = apply_fix(issue_data, target_file, old_content)
            with open(full_path, "w", encoding="utf-8", newline='\n') as f:
                f.write(new_code.replace('\r\n', '\n'))
        except Exception as e:
            print(f"Error processing {target_file}: {e}")
            sys.exit(1)

    # V14: Restored The VERIFY LOOP
    if ENABLE_SANDBOX:
        max_repairs = 3
        repair_count = 0
        
        while repair_count < max_repairs:
            test_passed, test_log = run_tests_in_sandbox(REPO_PATH)
            
            if test_passed:
                print("✅ Verification Successful!")
                break
            
            print(f"\n⚠️ TESTS FAILED (Attempt {repair_count+1}/{max_repairs}). Entering Repair Loop...")
            
            # Simple heuristic: Repair the first file in the plan
            primary_file = target_files[0] 
            full_path = os.path.join(REPO_PATH, primary_file)
            with open(full_path, "r", encoding="utf-8") as f:
                current_content = f.read()
            
            repaired_code = apply_fix(issue_data, primary_file, current_content, test_error=test_log)
            with open(full_path, "w", encoding="utf-8", newline='\n') as f:
                f.write(repaired_code.replace('\r\n', '\n'))
                
            repair_count += 1
        
        if not test_passed:
            print("❌ Critical: Tests failed after all repair attempts.")

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
        
        pr_title = str(pr_details.get('pr_title', 'Fix')).replace('\x00', '')
        pr_body = str(pr_details.get('pr_body', '')).replace('\x00', '')
        
        subprocess.run([
            "gh", "pr", "create", 
            "--title", pr_title, 
            "--body", pr_body
        ], check=True, shell=False)
    except Exception as e:
        print(f"Error in commit/push: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
