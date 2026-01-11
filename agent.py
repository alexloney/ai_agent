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

# VERSION
AGENT_VERSION = "15"

# FILE EXTENSIONS
CODE_EXTENSIONS = (".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".html", ".css", ".java", ".rs", ".c", ".h", ".cpp", ".hpp")
TEST_EXTENSIONS = ("_test.py", "test_.py", ".test.js", ".spec.js", ".test.ts", ".spec.ts")
DOC_EXTENSIONS = (".md", ".rst", ".txt")

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

def get_file_tree(repo_path, include_tests=False, include_docs=False):
    """Get a list of files, with options for tests and docs."""
    try:
        result = subprocess.run(
            ["git", "ls-files"], 
            cwd=repo_path, capture_output=True, text=True, check=True
        )
        files = result.stdout.splitlines()
        
        filtered_files = []
        for f in files:
            is_test = any(f.endswith(ext) for ext in TEST_EXTENSIONS) or '/test/' in f or '/tests/' in f
            is_doc = any(f.endswith(ext) for ext in DOC_EXTENSIONS)
            is_code = any(f.endswith(ext) for ext in CODE_EXTENSIONS)
            
            if is_code and not is_test and not is_doc:
                filtered_files.append(f)
            elif include_tests and is_test:
                filtered_files.append(f)
            elif include_docs and is_doc:
                filtered_files.append(f)
                
        return filtered_files
    except Exception as e:
        print(f"Warning: git ls-files failed ({e}). Using fallback method")
        files = []
        for root, _, filenames in os.walk(repo_path):
            if '.git' in root: continue
            for filename in filenames:
                if filename.endswith(CODE_EXTENSIONS):
                    rel_path = os.path.relpath(os.path.join(root, filename), repo_path)
                    files.append(rel_path)
        return files

def analyze_codebase_structure(repo_path, file_list):
    """Analyze the codebase to understand structure, patterns, and conventions."""
    print("\n--- 🔍 ANALYZING CODEBASE STRUCTURE ---")
    
    # Sample files to understand patterns (limit to avoid token overflow)
    sample_files = {}
    for f in file_list[:10]:  # Analyze first 10 files for patterns
        try:
            full_path = os.path.join(repo_path, f)
            with open(full_path, 'r', encoding='utf-8') as file:
                sample_files[f] = file.read()[:2000]  # First 2000 chars
        except:
            continue
    
    if not sample_files:
        return "No files available for analysis"
    
    files_content = "\n\n".join([f"=== {fname} ===\n{content}" for fname, content in sample_files.items()])
    
    prompt = ChatPromptTemplate.from_template("""
    You are a Senior Software Architect analyzing a codebase.
    
    SAMPLE FILES:
    {files_content}
    
    TASK: Analyze these files and identify:
    1. Programming language(s) and frameworks used
    2. Code style and conventions (indentation, naming, etc.)
    3. Common patterns (error handling, imports, class structure)
    4. Testing approach (if visible)
    5. Documentation style
    6. Project structure and organization
    
    Provide a concise analysis (5-10 bullet points) that will help understand how to write code that fits this codebase.
    """)
    
    chain = prompt | llm
    response = chain.invoke({"files_content": files_content})
    analysis = response.content.strip()
    print(f"Codebase Analysis:\n{analysis}\n")
    return analysis

def read_relevant_files(repo_path, file_list, max_files=5):
    """Read contents of relevant files to provide context."""
    file_contents = {}
    for f in file_list[:max_files]:
        try:
            full_path = os.path.join(repo_path, f)
            with open(full_path, 'r', encoding='utf-8') as file:
                file_contents[f] = file.read()
        except Exception as e:
            print(f"Warning: Could not read {f}: {e}")
            continue
    return file_contents

def plan_changes(issue_content, file_list, repo_path, codebase_analysis):
    """Plan changes with deep understanding of the codebase."""
    if not file_list:
        print("Warning: No files to analyze")
        return [], ""
    
    print("\n--- 📋 PLANNING CHANGES ---")
    
    # Read small samples of files for better context
    file_previews = {}
    for f in file_list[:20]:  # Preview up to 20 files
        try:
            full_path = os.path.join(repo_path, f)
            with open(full_path, 'r', encoding='utf-8') as file:
                content = file.read()
                # Include file size and first few lines
                lines = content.split('\n')[:10]
                preview = '\n'.join(lines)
                file_previews[f] = f"{len(content)} chars, Preview:\n{preview}"
        except:
            file_previews[f] = "Unable to read"
    
    file_info = "\n".join([f"{fname}: {preview}" for fname, preview in file_previews.items()])
    
    prompt = ChatPromptTemplate.from_template("""
    You are a Senior Software Architect with deep expertise in analyzing and solving complex software issues.
    
    CODEBASE CONTEXT:
    {codebase_analysis}
    
    ISSUE TO SOLVE:
    {issue}
    
    AVAILABLE FILES (with previews):
    {file_info}
    
    TASK: Create a comprehensive implementation plan.
    
    Think through this step-by-step:
    1. What is the root cause or requirement described in the issue?
    2. Which files need to be modified and why?
    3. What is the logical sequence of changes?
    4. Are there any edge cases or side effects to consider?
    5. Will tests need to be updated or created?
    6. Are there any related files (configs, docs) that should be updated?
    
    OUTPUT FORMAT:
    First, provide your detailed reasoning and implementation plan (3-5 paragraphs).
    Then, list the files that need to be modified, one per line, prefixed with "FILE: "
    
    Example:
    REASONING: [Your detailed analysis here]
    
    FILES TO MODIFY:
    FILE: src/main.py
    FILE: src/utils.py
    """)
    
    chain = prompt | llm
    response = chain.invoke({
        "issue": issue_content,
        "file_info": file_info,
        "codebase_analysis": codebase_analysis
    })
    
    full_response = response.content.strip()
    print(f"\nImplementation Plan:\n{full_response}\n")
    
    # Extract files from response
    lines = full_response.split('\n')
    valid_files = []
    normalized_list = [f.replace("\\", "/") for f in file_list]
    
    for line in lines:
        # Look for FILE: prefix or just filenames
        clean_line = line.strip()
        if clean_line.startswith("FILE:"):
            clean_line = clean_line[5:].strip()
        clean_line = clean_line.strip('"').strip("'").lstrip('- ').replace("\\", "/")
        
        if clean_line in normalized_list:
            valid_files.append(clean_line.replace("/", os.sep))
    
    # Extract reasoning part (everything before FILES TO MODIFY section)
    reasoning = full_response
    if "FILE:" in full_response:
        reasoning = full_response.split("FILE:")[0].strip()
    
    return list(set(valid_files)), reasoning

def check_syntax(code, filename):
    if not filename.endswith(".py"): return True, None
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}\nLine content: {e.text}"
    except Exception as e:
        return False, str(e)

def self_review_changes(issue_content, files_changed, codebase_analysis):
    """Perform a self-review of the changes before committing."""
    print("\n--- 🔍 PERFORMING SELF-REVIEW ---")
    
    # Prepare summary of changes
    changes_summary = []
    for filename, content in files_changed.items():
        lines = content.split('\n')
        changes_summary.append(f"{filename}: {len(lines)} lines")
    
    changes_text = "\n".join(changes_summary)
    
    prompt = ChatPromptTemplate.from_template("""
    You are a Senior Code Reviewer performing a final check before committing.
    
    CODEBASE CONTEXT:
    {codebase_analysis}
    
    ORIGINAL ISSUE:
    {issue}
    
    FILES MODIFIED:
    {changes}
    
    TASK: Review these changes for potential issues:
    
    1. Does the implementation address the issue correctly?
    2. Are there any obvious bugs or logical errors?
    3. Does it follow the codebase conventions?
    4. Are there any security concerns?
    5. Is error handling adequate?
    6. Are there any edge cases not handled?
    7. Is the code maintainable and clear?
    
    OUTPUT FORMAT:
    If you find ANY concerns, list them clearly with specific details.
    If everything looks good, respond with: "APPROVED - No concerns found"
    
    Be thorough but practical - focus on significant issues that could cause problems.
    """)
    
    chain = prompt | llm
    response = chain.invoke({
        "issue": issue_content,
        "changes": changes_text,
        "codebase_analysis": codebase_analysis
    })
    
    review_result = response.content.strip()
    print(f"\nSelf-Review Result:\n{review_result}\n")
    
    # Check if approved
    is_approved = "APPROVED" in review_result.upper() or "NO CONCERNS" in review_result.upper()
    
    return is_approved, review_result

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

def apply_fix(issue_content, filename, file_content, codebase_analysis, implementation_plan, test_error=None, related_files=None):
    """Apply fix with comprehensive context and understanding."""
    is_python = filename.endswith(".py")
    
    # Prepare related files context
    related_context = ""
    if related_files:
        related_context = "\n\nRELATED FILES FOR CONTEXT:\n"
        for rel_file, rel_content in related_files.items():
            # Limit each related file to 1500 chars to manage token count
            related_context += f"\n=== {rel_file} ===\n{rel_content[:1500]}\n"
    
    chain_inputs = {
        "issue": issue_content,
        "filename": filename,
        "content": file_content,
        "codebase_analysis": codebase_analysis,
        "implementation_plan": implementation_plan,
        "related_context": related_context,
        "test_error": str(test_error) if test_error else "",
        "syntax_error": ""
    }
    
    template_str = """
    You are an expert Software Engineer working on a complex codebase.
    
    CODEBASE CONTEXT & CONVENTIONS:
    {codebase_analysis}
    
    IMPLEMENTATION PLAN & REASONING:
    {implementation_plan}
    
    ISSUE DESCRIPTION:
    {issue}
    
    FILE TO MODIFY: {filename}
    
    CURRENT FILE CONTENT:
    {content}
    {related_context}
    
    TASK: Implement a comprehensive, production-quality fix for this file.
    
    CRITICAL REQUIREMENTS:
    1. Follow the codebase conventions and patterns identified in the analysis
    2. Implement the fix according to the implementation plan
    3. Consider edge cases and error handling
    4. Add appropriate comments where they add value (not obvious code)
    5. Ensure the code is maintainable and follows best practices
    6. Rewrite the ENTIRE file with the fix applied
    7. PRESERVE all existing functionality not related to the fix
    8. Keep original indentation and formatting style
    9. OUTPUT ONLY THE COMPLETE FILE CODE - NO EXPLANATORY TEXT BEFORE OR AFTER
    """
    
    if is_python:
        template_str += "\n10. Ensure the output is valid, syntactically correct Python code"
    
    if test_error:
        template_str += "\n\nPREVIOUS ATTEMPT FAILED TESTS WITH ERROR:\n{test_error}\n\nAnalyze this error carefully and fix the root cause. Consider:\n- What exactly is failing?\n- Is it a logic error, edge case, or integration issue?\n- How does this relate to the implementation plan?"

    print(f"\n--- 🔧 APPLYING FIX TO {filename} ---")
    
    for attempt in range(3):
        if chain_inputs["syntax_error"]:
            template_str += "\n\nPREVIOUS ATTEMPT HAD SYNTAX ERROR:\n{syntax_error}\nFix the syntax while maintaining the logic of the fix."

        prompt = ChatPromptTemplate.from_template(template_str)
        chain = prompt | llm
        response = chain.invoke(chain_inputs)
        
        code = clean_llm_response(response.content)
            
        is_valid, error_msg = check_syntax(code, filename)
        if is_valid:
            print(f"✅ Successfully generated fix for {filename}")
            return code
        
        print(f"  ⚠️ Syntax Error on attempt {attempt+1}: {error_msg}")
        chain_inputs["syntax_error"] = error_msg

    print(f"⚠️ Warning: Failed to generate valid syntax after 3 attempts. Using best effort.")
    return code

def extract_json_with_fallback(text):
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match: return json.loads(match.group(0))
    except: pass
    return { "commit_message": "fix: resolve issue", "pr_title": "Fix", "pr_body": text }

def generate_pr_content(issue_data, diff):
    """Generate comprehensive PR documentation with detailed explanations."""
    prompt = ChatPromptTemplate.from_template("""
    You are a Senior Developer creating a pull request for code review.
    
    ORIGINAL ISSUE:
    {issue}
    
    CODE CHANGES (Git Diff):
    {diff}
    
    TASK: Generate high-quality PR documentation that would be suitable for a professional code review.
    
    Include:
    1. A clear, descriptive commit message (conventional commits format: "type: description")
    2. A professional PR title
    3. A detailed PR description that explains:
       - What problem this solves
       - How it solves it (high-level approach)
       - Key changes made
       - Any important considerations or trade-offs
    
    OUTPUT FORMAT (Strict JSON):
    {{
        "commit_message": "feat: add feature X to improve Y",
        "pr_title": "Implement feature X",
        "pr_body": "## Summary\n\n[Detailed description]\n\n## Changes\n\n- Change 1\n- Change 2"
    }}
    """)
    
    print("\n--- 📝 GENERATING PR DOCUMENTATION ---")
    chain = prompt | llm
    response = chain.invoke({"issue": issue_data, "diff": diff})
    return extract_json_with_fallback(response.content)

# --- MAIN EXECUTION ---
def main():
    print(f"--- AI Agent V{AGENT_VERSION} (Copilot-Enhanced) ---")
    
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
    
    # PHASE 1: ANALYZE CODEBASE
    print("\n" + "="*60)
    print("PHASE 1: ANALYZING CODEBASE")
    print("="*60)
    file_tree = get_file_tree(REPO_PATH, include_tests=False, include_docs=False)
    codebase_analysis = analyze_codebase_structure(REPO_PATH, file_tree)
    
    # PHASE 2: PLAN CHANGES
    print("\n" + "="*60)
    print("PHASE 2: PLANNING IMPLEMENTATION")
    print("="*60)
    target_files, implementation_plan = plan_changes(issue_data, file_tree, REPO_PATH, codebase_analysis)
    print(f"\n📌 Files to modify ({len(target_files)}): {target_files}")
    
    if not target_files:
        print("No files identified for modification. Exiting.")
        sys.exit(0)
    
    # PHASE 3: GATHER CONTEXT FOR FIXES
    print("\n" + "="*60)
    print("PHASE 3: GATHERING CONTEXT")
    print("="*60)
    # Read all target files and some related files for context
    all_file_contents = {}
    for target_file in target_files:
        full_path = os.path.join(REPO_PATH, target_file)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                all_file_contents[target_file] = f.read()
        except Exception as e:
            print(f"Error reading {target_file}: {e}")
            sys.exit(1)
    
    # PHASE 4: APPLY FIXES
    print("\n" + "="*60)
    print("PHASE 4: IMPLEMENTING FIXES")
    print("="*60)
    for target_file in target_files:
        full_path = os.path.join(REPO_PATH, target_file)
        old_content = all_file_contents[target_file]
        
        # Provide other target files as related context
        related_files = {f: content for f, content in all_file_contents.items() if f != target_file}
        
        new_code = apply_fix(
            issue_data, 
            target_file, 
            old_content,
            codebase_analysis,
            implementation_plan,
            test_error=None,
            related_files=related_files
        )
        
        try:
            with open(full_path, "w", encoding="utf-8", newline='\n') as f:
                f.write(new_code.replace('\r\n', '\n'))
            print(f"✅ Updated {target_file}")
        except Exception as e:
            print(f"Error writing {target_file}: {e}")
            sys.exit(1)

    # PHASE 5: VERIFY AND REPAIR
    print("\n" + "="*60)
    print("PHASE 5: TESTING AND VALIDATION")
    print("="*60)
    if ENABLE_SANDBOX:
        max_repairs = 3
        repair_count = 0
        
        while repair_count < max_repairs:
            test_passed, test_log = run_tests_in_sandbox(REPO_PATH)
            
            if test_passed:
                print("✅ All tests passed!")
                break
            
            print(f"\n⚠️ TESTS FAILED (Attempt {repair_count+1}/{max_repairs})")
            print("Analyzing failures and applying targeted fixes...")
            
            # Try to repair each file that might be causing issues
            for target_file in target_files:
                full_path = os.path.join(REPO_PATH, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    current_content = f.read()
                
                # Provide context from other files
                related_files = {f: all_file_contents[f] for f in target_files if f != target_file}
                
                repaired_code = apply_fix(
                    issue_data, 
                    target_file, 
                    current_content,
                    codebase_analysis,
                    implementation_plan,
                    test_error=test_log,
                    related_files=related_files
                )
                
                with open(full_path, "w", encoding="utf-8", newline='\n') as f:
                    f.write(repaired_code.replace('\r\n', '\n'))
                
                # Update our tracking
                all_file_contents[target_file] = repaired_code
                
            repair_count += 1
        
        if not test_passed:
            print("❌ Warning: Tests still failing after all repair attempts.")
            print("Proceeding with current implementation...")
    
    # PHASE 5.5: SELF-REVIEW
    print("\n" + "="*60)
    print("PHASE 5.5: CODE REVIEW")
    print("="*60)
    # Re-read all modified files for review
    current_file_contents = {}
    for target_file in target_files:
        full_path = os.path.join(REPO_PATH, target_file)
        with open(full_path, "r", encoding="utf-8") as f:
            current_file_contents[target_file] = f.read()
    
    review_approved, review_comments = self_review_changes(
        issue_data,
        current_file_contents,
        codebase_analysis
    )
    
    if not review_approved:
        print("⚠️ Self-review identified concerns. Proceeding anyway (human review recommended).")
        review_notes = f"\n\n## ⚠️ Self-Review Notes\n\n{review_comments}\n"
    else:
        print("✅ Self-review passed!")
        review_notes = ""

    # PHASE 6: COMMIT AND CREATE PR
    print("\n" + "="*60)
    print("PHASE 6: COMMITTING AND CREATING PR")
    print("="*60)
    try:
        repo.index.add(target_files)
        git_diff = repo.git.diff("--cached")
        if not git_diff.strip():
            print("No changes detected. Aborting.")
            sys.exit(0)

        pr_details = generate_pr_content(issue_data, git_diff)
        commit_msg = pr_details['commit_message']
        print(f"Commit Message: {commit_msg}")
        repo.index.commit(commit_msg)
        
        print("Pushing to remote...")
        repo.remote(name='origin').push(branch, set_upstream=True)
        
        pr_title = str(pr_details.get('pr_title', 'Fix')).replace('\x00', '')
        pr_body = str(pr_details.get('pr_body', '')).replace('\x00', '')
        
        # Enhance PR body with implementation details
        enhanced_pr_body = f"""{pr_body}

## Implementation Details

{implementation_plan}

## Files Modified
{chr(10).join(f'- `{f}`' for f in target_files)}
{review_notes}
---
*Generated by AI Agent V{AGENT_VERSION} with comprehensive analysis and planning*
"""
        
        subprocess.run([
            "gh", "pr", "create", 
            "--title", pr_title, 
            "--body", enhanced_pr_body
        ], check=True, shell=False)
        
        print("\n" + "="*60)
        print("✅ SUCCESS! Pull request created.")
        print("="*60)
    except Exception as e:
        print(f"Error in commit/push: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
