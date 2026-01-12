"""
Tools for the ReAct pattern implementation.

This module provides tools that the agent can use to explore the codebase
dynamically, similar to how a human developer would investigate an issue.
"""

import os
import re
import subprocess
from typing import List, Dict, Optional, Tuple


class CodebaseTools:
    """Tools for exploring and searching the codebase."""
    
    def __init__(self, repo_path: str):
        """
        Initialize codebase tools.
        
        Args:
            repo_path: Path to the repository
        """
        self.repo_path = repo_path
    
    def search_code(self, query: str, file_pattern: str = None, case_sensitive: bool = False) -> List[Dict[str, any]]:
        """
        Search for a string or pattern in the codebase using grep.
        
        Args:
            query: The string or regex pattern to search for
            file_pattern: Optional file pattern (e.g., "*.py")
            case_sensitive: Whether search should be case-sensitive
            
        Returns:
            List of matches with file path, line number, and content
        """
        matches = []
        
        try:
            # Build grep command
            cmd = ["grep", "-rn"]
            if not case_sensitive:
                cmd.append("-i")
            
            # Add pattern
            cmd.append(query)
            
            # Add file pattern if specified
            if file_pattern:
                cmd.extend(["--include", file_pattern])
            
            # Add repo path
            cmd.append(self.repo_path)
            
            # Run grep
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Parse results
            for line in result.stdout.splitlines():
                # Format: filepath:line_number:content
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    file_path = os.path.relpath(parts[0], self.repo_path)
                    line_num = parts[1]
                    content = parts[2]
                    
                    matches.append({
                        'file_path': file_path,
                        'line_number': int(line_num) if line_num.isdigit() else 0,
                        'content': content.strip()
                    })
            
        except subprocess.TimeoutExpired:
            print("Warning: search_code timed out")
        except FileNotFoundError:
            # grep not available, fall back to Python implementation
            matches = self._search_code_fallback(query, file_pattern, case_sensitive)
        except Exception as e:
            print(f"Warning: search_code failed: {e}")
        
        return matches
    
    def _search_code_fallback(self, query: str, file_pattern: str = None, case_sensitive: bool = False) -> List[Dict[str, any]]:
        """Fallback Python implementation of code search."""
        matches = []
        pattern = re.compile(query if case_sensitive else query, re.IGNORECASE if not case_sensitive else 0)
        
        for root, _, files in os.walk(self.repo_path):
            # Skip .git directory
            if '.git' in root:
                continue
            
            for filename in files:
                # Check file pattern if specified
                if file_pattern:
                    import fnmatch
                    if not fnmatch.fnmatch(filename, file_pattern):
                        continue
                
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, self.repo_path)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            if pattern.search(line):
                                matches.append({
                                    'file_path': rel_path,
                                    'line_number': line_num,
                                    'content': line.strip()
                                })
                except (UnicodeDecodeError, PermissionError):
                    continue
        
        return matches
    
    def find_references(self, symbol: str, file_pattern: str = None) -> List[Dict[str, any]]:
        """
        Find references to a symbol (function, class, variable) in the codebase.
        
        Args:
            symbol: The symbol name to find
            file_pattern: Optional file pattern (e.g., "*.py")
            
        Returns:
            List of references with file path, line number, and content
        """
        # Search for the symbol as a whole word
        # Using word boundaries to avoid partial matches
        query = r'\b' + re.escape(symbol) + r'\b'
        return self.search_code(query, file_pattern, case_sensitive=True)
    
    def read_file(self, file_path: str, start_line: int = None, end_line: int = None) -> Optional[str]:
        """
        Read the contents of a file.
        
        Args:
            file_path: Path to the file (relative to repo)
            start_line: Optional starting line number (1-indexed)
            end_line: Optional ending line number (inclusive)
            
        Returns:
            File content as string, or None if file not found
        """
        full_path = os.path.join(self.repo_path, file_path)
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                if start_line is None and end_line is None:
                    return f.read()
                
                # Read specific lines
                lines = f.readlines()
                start_idx = (start_line - 1) if start_line else 0
                end_idx = end_line if end_line else len(lines)
                
                return ''.join(lines[start_idx:end_idx])
        except FileNotFoundError:
            print(f"Warning: File not found: {file_path}")
            return None
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return None
    
    def list_files(self, directory: str = "", pattern: str = None) -> List[str]:
        """
        List files in a directory.
        
        Args:
            directory: Directory path (relative to repo, default is root)
            pattern: Optional file pattern (e.g., "*.py")
            
        Returns:
            List of file paths
        """
        dir_path = os.path.join(self.repo_path, directory)
        files = []
        
        try:
            for root, _, filenames in os.walk(dir_path):
                # Skip .git
                if '.git' in root:
                    continue
                
                for filename in filenames:
                    if pattern:
                        import fnmatch
                        if not fnmatch.fnmatch(filename, pattern):
                            continue
                    
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, self.repo_path)
                    files.append(rel_path)
        except Exception as e:
            print(f"Warning: Could not list files in {directory}: {e}")
        
        return files
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, any]]:
        """
        Get metadata about a file.
        
        Args:
            file_path: Path to the file (relative to repo)
            
        Returns:
            Dictionary with file info (size, lines, etc.) or None
        """
        full_path = os.path.join(self.repo_path, file_path)
        
        try:
            stat = os.stat(full_path)
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            return {
                'file_path': file_path,
                'size_bytes': stat.st_size,
                'line_count': len(lines),
                'char_count': len(content)
            }
        except Exception as e:
            print(f"Warning: Could not get info for {file_path}: {e}")
            return None


class ToolExecutor:
    """Executor for running tools based on LLM decisions."""
    
    def __init__(self, tools: CodebaseTools):
        """
        Initialize tool executor.
        
        Args:
            tools: CodebaseTools instance
        """
        self.tools = tools
        self.execution_history = []
    
    def execute_tool(self, tool_name: str, **kwargs) -> Tuple[bool, any]:
        """
        Execute a tool by name with given arguments.
        
        Args:
            tool_name: Name of the tool to execute
            **kwargs: Arguments to pass to the tool
            
        Returns:
            Tuple of (success, result)
        """
        try:
            if tool_name == "search_code":
                result = self.tools.search_code(**kwargs)
            elif tool_name == "find_references":
                result = self.tools.find_references(**kwargs)
            elif tool_name == "read_file":
                result = self.tools.read_file(**kwargs)
            elif tool_name == "list_files":
                result = self.tools.list_files(**kwargs)
            elif tool_name == "get_file_info":
                result = self.tools.get_file_info(**kwargs)
            else:
                return False, f"Unknown tool: {tool_name}"
            
            # Record execution
            self.execution_history.append({
                'tool': tool_name,
                'args': kwargs,
                'result': result
            })
            
            return True, result
        except Exception as e:
            error_msg = f"Tool execution failed: {e}"
            print(f"Warning: {error_msg}")
            return False, error_msg
    
    def get_execution_summary(self) -> str:
        """Get a summary of all tool executions."""
        summary = []
        for i, execution in enumerate(self.execution_history, 1):
            summary.append(f"{i}. {execution['tool']}({execution['args']})")
        return '\n'.join(summary)
    
    def format_tool_result(self, result: any, max_items: int = 10) -> str:
        """
        Format tool result for display to LLM.
        
        Args:
            result: The tool result
            max_items: Maximum number of items to include in formatted output
            
        Returns:
            Formatted string
        """
        if result is None:
            return "No result"
        
        if isinstance(result, str):
            # Truncate long strings
            if len(result) > 2000:
                return result[:2000] + f"\n... (truncated, {len(result)} total chars)"
            return result
        
        if isinstance(result, list):
            if len(result) == 0:
                return "No results found"
            
            formatted = []
            for item in result[:max_items]:
                if isinstance(item, dict):
                    formatted.append(str(item))
                else:
                    formatted.append(str(item))
            
            output = '\n'.join(formatted)
            if len(result) > max_items:
                output += f"\n... ({len(result) - max_items} more results)"
            
            return output
        
        return str(result)
