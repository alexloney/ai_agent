import os
import subprocess
import re
import json
import sys
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

# Import our new modules
from language_strategy import PythonStrategy, LanguageStrategy
from pr_manager import PRManager, parse_pr_content

# --- CONFIGURATION ---
REPO_PATH = os.getcwd()

# VERSION
AGENT_VERSION = "16"

# Language Strategy - can be configured for different projects
LANGUAGE_STRATEGY = PythonStrategy()

# DOC_EXTENSIONS - used for filtering documentation files
DOC_EXTENSIONS = (".md", ".rst", ".txt")

# SANDBOX CONFIGURATION
ENABLE_SANDBOX = True

# OUTPUT CONFIGURATION
MAX_TEST_OUTPUT_LENGTH = 4000  
DOCKER_TIMEOUT = 300

# REVIEW CONFIGURATION
MAX_REVIEW_ITERATIONS = 3  # Maximum number of review-refactor cycles  

llm = ChatOllama(
    model="qwen2.5-coder:32b-instruct",
    temperature=0.1,
    base_url="http://localhost:11434"
)

def identify_failing_test_file(test_log, repo_path):
    """Scans the test output to find the specific test file that failed."""
    # Delegate to language strategy if available
    if hasattr(LANGUAGE_STRATEGY, 'identify_failing_test_file'):
        return LANGUAGE_STRATEGY.identify_failing_test_file(test_log, repo_path)
    
    # Generic fallback
    match = re.search(r'(tests?[\\/][a-zA-Z0-9_]+\.\w+)', test_log)
    if match:
        return match.group(1).replace("\\", "/")
    return None

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
        return [], [], ""
    
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
    2. Which existing files need to be modified and why?
    3. What new files need to be created (if any)?
    4. What is the logical sequence of changes?
    5. Are there any edge cases or side effects to consider?
    6. Will tests need to be updated or created?
    7. Are there any related files (configs, docs) that should be updated?
    
    OUTPUT FORMAT:
    First, provide your detailed reasoning and implementation plan (3-5 paragraphs).
    Then, list the files that need to be modified, one per line, prefixed with "MODIFY: "
    Then, list any new files to create, one per line, prefixed with "CREATE: "
    
    Example:
    REASONING: [Your detailed analysis here]
    
    FILES TO MODIFY:
    MODIFY: src/main.py
    MODIFY: src/utils.py
    
    NEW FILES TO CREATE:
    CREATE: src/new_feature.py
    CREATE: tests/test_new_feature.py
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
    files_to_modify = []
    files_to_create = []
    normalized_list = [f.replace("\\", "/") for f in file_list]
    
    for line in lines:
        clean_line = line.strip()
        
        # Check for MODIFY prefix
        if clean_line.startswith("MODIFY:"):
            clean_line = clean_line[7:].strip()
            clean_line = clean_line.strip('"').strip("'").lstrip('- ').replace("\\", "/")
            if clean_line in normalized_list:
                files_to_modify.append(clean_line.replace("/", os.sep))
        
        # Check for CREATE prefix
        elif clean_line.startswith("CREATE:"):
            clean_line = clean_line[7:].strip()
            clean_line = clean_line.strip('"').strip("'").lstrip('- ').replace("\\", "/")
            files_to_create.append(clean_line.replace("/", os.sep))
        
        # Legacy support: look for FILE: prefix
        elif clean_line.startswith("FILE:"):
            clean_line = clean_line[5:].strip()
            clean_line = clean_line.strip('"').strip("'").lstrip('- ').replace("\\", "/")
            if clean_line in normalized_list:
                files_to_modify.append(clean_line.replace("/", os.sep))
    
    # Extract reasoning part (everything before FILES/MODIFY/CREATE sections)
    reasoning = full_response
    if "MODIFY:" in full_response or "FILE:" in full_response or "CREATE:" in full_response:
        # Find the first occurrence of any of these markers
        split_markers = ["MODIFY:", "FILE:", "CREATE:"]
        first_marker_pos = len(full_response)
        for marker in split_markers:
            pos = full_response.find(marker)
            if pos != -1 and pos < first_marker_pos:
                first_marker_pos = pos
        if first_marker_pos < len(full_response):
            reasoning = full_response[:first_marker_pos].strip()
    
    return list(set(files_to_modify)), list(set(files_to_create)), reasoning

def check_syntax(code, filename):
    """Check syntax using the language strategy."""
    return LANGUAGE_STRATEGY.check_syntax(code, filename)

def self_review_changes(issue_content, files_changed, codebase_analysis):
    """Perform a self-review of the changes before committing."""
    print("\n--- 🔍 PERFORMING SELF-REVIEW ---")
    
    # Prepare summary of changes with actual content for better review
    changes_summary = []
    for filename, content in files_changed.items():
        lines = content.split('\n')
        # Include first 50 lines and last 20 lines for context
        preview_lines = lines[:50]
        if len(lines) > 70:
            preview_lines.append("... [content truncated] ...")
            preview_lines.extend(lines[-20:])
        preview = '\n'.join(preview_lines)
        changes_summary.append(f"=== {filename} ({len(lines)} lines) ===\n{preview}")
    
    changes_text = "\n\n".join(changes_summary)
    
    prompt = ChatPromptTemplate.from_template("""
    You are a Senior Code Reviewer performing a final check before committing.
    
    CODEBASE CONTEXT:
    {codebase_analysis}
    
    ORIGINAL ISSUE:
    {issue}
    
    MODIFIED FILES WITH CONTENT:
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
    If you find ANY significant concerns that would prevent the code from working correctly,
    respond with:
    REJECTED - [List of specific issues that must be fixed]
    
    If you find minor concerns or suggestions but the code should work:
    APPROVED_WITH_NOTES - [List of suggestions for future improvement]
    
    If everything looks good:
    APPROVED - No concerns found
    
    Be thorough but practical - focus on significant issues that could cause problems.
    Do not reject for minor style issues or missing comments.
    """)
    
    chain = prompt | llm
    response = chain.invoke({
        "issue": issue_content,
        "changes": changes_text,
        "codebase_analysis": codebase_analysis
    })
    
    review_result = response.content.strip()
    print(f"\nSelf-Review Result:\n{review_result}\n")
    
    # Check approval status
    review_upper = review_result.upper()
    if "REJECTED" in review_upper:
        return False, review_result
    elif "APPROVED" in review_upper:
        return True, review_result
    
    # If unclear, treat as approved with caution
    print("Warning: Review result unclear, treating as approved")
    return True, review_result

def run_tests_in_sandbox(repo_path):
    print("\n--- 🔒 STARTING SANDBOXED TEST RUN ---")
    abs_path = os.path.abspath(repo_path)
    
    # Get Docker configuration from language strategy
    docker_image = LANGUAGE_STRATEGY.get_docker_image()
    docker_test_cmd = LANGUAGE_STRATEGY.get_docker_test_command()
    
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{abs_path}:/app",
        "-w", "/app",
        docker_image,
        "/bin/bash", "-c", docker_test_cmd
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

def apply_fix(issue_content, filename, file_content, codebase_analysis, implementation_plan, test_error=None, related_files=None, review_feedback=None):
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
        "review_feedback": str(review_feedback) if review_feedback else "",
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
    
    if review_feedback:
        template_str += "\n\nPREVIOUS ATTEMPT WAS REJECTED BY CODE REVIEW:\n{review_feedback}\n\nAddress ALL the review concerns. This is critical - the code was rejected for good reasons."
    
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

def create_new_file(issue_content, filename, codebase_analysis, implementation_plan, related_files=None):
    """Generate content for a new file."""
    print(f"\n--- ✨ CREATING NEW FILE: {filename} ---")
    
    # Prepare related files context
    related_context = ""
    if related_files:
        related_context = "\n\nRELATED FILES FOR CONTEXT:\n"
        for rel_file, rel_content in related_files.items():
            related_context += f"\n=== {rel_file} ===\n{rel_content[:1500]}\n"
    
    is_python = filename.endswith(".py")
    
    prompt = ChatPromptTemplate.from_template("""
    You are an expert Software Engineer creating a new file for a codebase.
    
    CODEBASE CONTEXT & CONVENTIONS:
    {codebase_analysis}
    
    IMPLEMENTATION PLAN & REASONING:
    {implementation_plan}
    
    ISSUE DESCRIPTION:
    {issue}
    
    NEW FILE TO CREATE: {filename}
    {related_context}
    
    TASK: Create complete, production-quality code for this new file.
    
    CRITICAL REQUIREMENTS:
    1. Follow the codebase conventions and patterns identified in the analysis
    2. Implement according to the implementation plan
    3. Include proper imports, error handling, and documentation
    4. Add appropriate comments where they add value
    5. Ensure the code is maintainable and follows best practices
    6. OUTPUT ONLY THE COMPLETE FILE CODE - NO EXPLANATORY TEXT BEFORE OR AFTER
    {python_requirement}
    """)
    
    chain_inputs = {
        "issue": issue_content,
        "filename": filename,
        "codebase_analysis": codebase_analysis,
        "implementation_plan": implementation_plan,
        "related_context": related_context,
        "python_requirement": "\n7. Ensure the output is valid, syntactically correct Python code" if is_python else "",
        "syntax_error": ""
    }
    
    for attempt in range(3):
        chain = prompt | llm
        response = chain.invoke(chain_inputs)
        code = clean_llm_response(response.content)
        
        is_valid, error_msg = check_syntax(code, filename)
        if is_valid:
            print(f"✅ Successfully generated content for {filename}")
            return code
        
        print(f"  ⚠️ Syntax Error on attempt {attempt+1}: {error_msg}")
        # Update prompt to include syntax error feedback
        chain_inputs["syntax_error"] = f"\n\nPREVIOUS ATTEMPT HAD SYNTAX ERROR:\n{error_msg}\nFix the syntax."
    
    print(f"⚠️ Warning: Failed to generate valid syntax after 3 attempts for {filename}")
    return code

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
        "pr_body": "## Summary\\n\\n[Detailed description]\\n\\n## Changes\\n\\n- Change 1\\n- Change 2"
    }}
    
    IMPORTANT: Output ONLY valid JSON, nothing else.
    """)
    
    print("\n--- 📝 GENERATING PR DOCUMENTATION ---")
    chain = prompt | llm
    response = chain.invoke({"issue": issue_data, "diff": diff})
    return parse_pr_content(response.content)

# --- MAIN EXECUTION ---
def main():
    print(f"--- AI Agent V{AGENT_VERSION} (Enhanced with WIP PR & Review Loop) ---")
    
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
    
    # Initialize PR Manager
    pr_manager = PRManager(repo, branch, github_issue_number)
    
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
    files_to_modify, files_to_create, implementation_plan = plan_changes(
        issue_data, file_tree, REPO_PATH, codebase_analysis
    )
    print(f"\n📌 Files to modify ({len(files_to_modify)}): {files_to_modify}")
    print(f"📌 Files to create ({len(files_to_create)}): {files_to_create}")
    
    if not files_to_modify and not files_to_create:
        print("No files identified for modification or creation. Exiting.")
        sys.exit(0)
    
    # Create WIP PR early
    print("\n" + "="*60)
    print("CREATING WIP PULL REQUEST")
    print("="*60)
    
    initial_pr_body = f"""## 🚧 Work In Progress

This PR is being automatically generated to address issue #{github_issue_number}.

### Current Status: Planning Complete

**Files to Modify:** {len(files_to_modify)}
{chr(10).join(f'- `{f}`' for f in files_to_modify)}

**Files to Create:** {len(files_to_create)}
{chr(10).join(f'- `{f}`' for f in files_to_create)}

### Implementation Plan
{implementation_plan}

---
*This PR will be automatically updated as work progresses...*
"""
    
    # Generate initial PR title from issue
    pr_title = f"Fix issue #{github_issue_number}"
    pr_created = pr_manager.create_wip_pr(pr_title, initial_pr_body)
    
    if not pr_created:
        print("Warning: Failed to create WIP PR, continuing anyway...")
    
    # PHASE 3: GATHER CONTEXT FOR FIXES
    print("\n" + "="*60)
    print("PHASE 3: GATHERING CONTEXT")
    print("="*60)
    
    # Update PR with current phase
    pr_manager.update_progress("Phase 3: Gathering Context", 
                              "Reading existing files and preparing to implement changes...")
    
    # Read all target files for modification
    all_file_contents = {}
    for target_file in files_to_modify:
        full_path = os.path.join(REPO_PATH, target_file)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                all_file_contents[target_file] = f.read()
        except Exception as e:
            print(f"Error reading {target_file}: {e}")
            sys.exit(1)
    
    # PHASE 4: IMPLEMENT CHANGES (with review-refactor loop)
    print("\n" + "="*60)
    print("PHASE 4: IMPLEMENTING CHANGES (with Review Loop)")
    print("="*60)
    
    pr_manager.update_progress("Phase 4: Implementing Changes",
                              "Applying fixes to existing files and creating new files...")
    
    review_iteration = 0
    review_approved = False
    
    while review_iteration < MAX_REVIEW_ITERATIONS and not review_approved:
        if review_iteration > 0:
            print(f"\n--- 🔄 REVIEW-REFACTOR ITERATION {review_iteration} ---")
        
        # Apply fixes to existing files
        for target_file in files_to_modify:
            full_path = os.path.join(REPO_PATH, target_file)
            old_content = all_file_contents.get(target_file, "")
            
            # Provide other files as related context
            related_files = {f: content for f, content in all_file_contents.items() if f != target_file}
            
            # On first iteration, no review feedback. On subsequent iterations, include review feedback
            review_feedback = None if review_iteration == 0 else last_review_result
            
            new_code = apply_fix(
                issue_data, 
                target_file, 
                old_content,
                codebase_analysis,
                implementation_plan,
                test_error=None,
                related_files=related_files,
                review_feedback=review_feedback
            )
            
            try:
                with open(full_path, "w", encoding="utf-8", newline='\n') as f:
                    f.write(new_code.replace('\r\n', '\n'))
                print(f"✅ Updated {target_file}")
                # Update our tracking
                all_file_contents[target_file] = new_code
            except Exception as e:
                print(f"Error writing {target_file}: {e}")
                sys.exit(1)
        
        # Create new files
        for new_file in files_to_create:
            full_path = os.path.join(REPO_PATH, new_file)
            
            # Ensure directory exists (only if not root)
            dir_path = os.path.dirname(full_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            # Provide existing files as context
            related_files = all_file_contents.copy()
            
            new_code = create_new_file(
                issue_data,
                new_file,
                codebase_analysis,
                implementation_plan,
                related_files=related_files
            )
            
            try:
                with open(full_path, "w", encoding="utf-8", newline='\n') as f:
                    f.write(new_code.replace('\r\n', '\n'))
                print(f"✅ Created {new_file}")
                # Track new file content
                all_file_contents[new_file] = new_code
            except Exception as e:
                print(f"Error creating {new_file}: {e}")
                sys.exit(1)
        
        # PHASE 4.5: SELF-REVIEW
        print("\n" + "="*60)
        print(f"PHASE 4.5: CODE REVIEW (Iteration {review_iteration + 1})")
        print("="*60)
        
        pr_manager.update_progress("Phase 4.5: Code Review",
                                  f"Performing self-review of changes (iteration {review_iteration + 1})...")
        
        # Re-read all modified/created files for review
        current_file_contents = {}
        all_files = files_to_modify + files_to_create
        for file_path in all_files:
            full_path = os.path.join(REPO_PATH, file_path)
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    current_file_contents[file_path] = f.read()
            except Exception as e:
                print(f"Warning: Could not read {file_path} for review: {e}")
        
        review_approved, last_review_result = self_review_changes(
            issue_data,
            current_file_contents,
            codebase_analysis
        )
        
        if review_approved:
            print("✅ Self-review passed!")
            # Commit the approved changes
            commit_msg = f"feat: implement changes for issue #{github_issue_number} (review approved)"
            pr_manager.commit_and_push(all_files, commit_msg)
            pr_manager.update_progress("Phase 4.5: Review Complete",
                                      "✅ Code review passed! Changes have been committed.")
            break
        else:
            print(f"⚠️ Self-review iteration {review_iteration + 1} identified concerns.")
            print("Will refactor based on review feedback...")
            review_iteration += 1
            
            if review_iteration >= MAX_REVIEW_ITERATIONS:
                print(f"\n❌ Maximum review iterations ({MAX_REVIEW_ITERATIONS}) reached.")
                print("Proceeding with current implementation (human review strongly recommended).")
                # Commit anyway with a warning
                commit_msg = f"feat: implement changes for issue #{github_issue_number} (review concerns noted)"
                pr_manager.commit_and_push(all_files, commit_msg)
                pr_manager.update_progress("Phase 4.5: Review Incomplete",
                                          f"⚠️ Max review iterations reached. Please review carefully.\n\n{last_review_result}")

    # PHASE 5: TESTING AND VALIDATION
    print("\n" + "="*60)
    print("PHASE 5: TESTING AND VALIDATION")
    print("="*60)
    
    pr_manager.update_progress("Phase 5: Testing",
                              "Running tests in sandboxed environment...")
    
    if ENABLE_SANDBOX:
        max_repairs = 3
        repair_count = 0
        test_passed = False
        
        while repair_count < max_repairs:
            test_passed, test_log = run_tests_in_sandbox(REPO_PATH)
            
            if test_passed:
                print("✅ All tests passed!")
                break
            
            print(f"\n⚠️ TESTS FAILED (Attempt {repair_count+1}/{max_repairs})")
            print("Analyzing failures and applying targeted fixes...")

            failing_test_file = identify_failing_test_file(test_log, REPO_PATH)
            test_context = ""
            if failing_test_file:
                print(f"   Detected failing test: {failing_test_file}")
                try:
                    with open(os.path.join(REPO_PATH, failing_test_file), "r") as f:
                        test_context = f"\n\nFAILING TEST CODE:\n{f.read()}"
                except: pass
            
            # Try to repair each file that might be causing issues
            all_files = files_to_modify + files_to_create
            for target_file in all_files:
                full_path = os.path.join(REPO_PATH, target_file)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        current_content = f.read()
                except:
                    continue
                
                # Provide context from other files
                related_files = {f: all_file_contents.get(f, "") for f in all_files if f != target_file}
                
                repaired_code = apply_fix(
                    issue_data, 
                    target_file, 
                    current_content,
                    codebase_analysis,
                    implementation_plan,
                    test_error=f"{test_log}\n{test_context}",
                    related_files=related_files
                )
                
                with open(full_path, "w", encoding="utf-8", newline='\n') as f:
                    f.write(repaired_code.replace('\r\n', '\n'))
                
                # Update our tracking
                all_file_contents[target_file] = repaired_code
                
            repair_count += 1
            
            # Commit the repair attempt
            if repair_count < max_repairs:
                commit_msg = f"fix: repair test failures (attempt {repair_count})"
                pr_manager.commit_and_push(all_files, commit_msg)
        
        if not test_passed:
            print("❌ Warning: Tests still failing after all repair attempts.")
            print("Proceeding with current implementation...")
            pr_manager.update_progress("Phase 5: Testing Complete (with failures)",
                                      f"⚠️ Tests failed after {max_repairs} repair attempts.\n\nPlease review test failures manually.")
        else:
            pr_manager.update_progress("Phase 5: Testing Complete",
                                      "✅ All tests passed!")
    else:
        print("⚠️ Sandbox testing disabled")
        pr_manager.update_progress("Phase 5: Testing Skipped",
                                  "Sandbox testing is disabled.")

    # PHASE 6: FINALIZE PR
    print("\n" + "="*60)
    print("PHASE 6: FINALIZING PULL REQUEST")
    print("="*60)
    
    # Generate final PR content
    try:
        all_files = files_to_modify + files_to_create
        
        # Get diff of the latest changes
        # If there are parent commits, compare HEAD with its parent
        # Otherwise, show all staged changes (for first commit)
        if repo.head.commit.parents:
            git_diff = repo.git.diff("HEAD^", "HEAD")
        else:
            # New repository, get the diff of the first commit
            git_diff = repo.git.show("HEAD")
        
        if not git_diff.strip():
            print("Warning: No diff found, using empty diff")
            git_diff = "No changes in diff"

        pr_details = generate_pr_content(issue_data, git_diff)
        final_title = pr_details.get('pr_title', f'Fix issue #{github_issue_number}')
        final_body_base = pr_details.get('pr_body', '')
        
        # Enhance PR body with implementation details
        review_notes = ""
        if not review_approved:
            review_notes = f"\n\n## ⚠️ Review Notes\n\n{last_review_result}\n"
        
        final_pr_body = f"""{final_body_base}

## Implementation Details

{implementation_plan}

## Files Modified
{chr(10).join(f'- `{f}`' for f in files_to_modify)}

## Files Created
{chr(10).join(f'- `{f}`' for f in files_to_create)}
{review_notes}
---
*Generated by AI Agent V{AGENT_VERSION} with comprehensive analysis, review loop, and iterative development*
"""
        
        # Finalize the PR (remove WIP prefix and update content)
        pr_manager.finalize_pr(final_title, final_pr_body)
        
        print("\n" + "="*60)
        print("✅ SUCCESS! Pull request finalized.")
        print("="*60)
        if pr_manager.pr_url:
            print(f"PR URL: {pr_manager.pr_url}")
            
    except Exception as e:
        print(f"Error finalizing PR: {e}")
        import traceback
        traceback.print_exc()
        print("PR remains in WIP state")

if __name__ == "__main__":
    main()
