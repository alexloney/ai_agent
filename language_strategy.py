"""
Language-specific strategies for the AI agent.

This module provides a strategy pattern for handling language-specific
operations like syntax checking, file extensions, and test commands.
"""

from abc import ABC, abstractmethod
import ast
from typing import Tuple, List, Optional


class LanguageStrategy(ABC):
    """Abstract base class for language-specific strategies."""
    
    @abstractmethod
    def get_code_extensions(self) -> tuple:
        """Return tuple of code file extensions for this language."""
        pass
    
    @abstractmethod
    def get_test_extensions(self) -> tuple:
        """Return tuple of test file extensions for this language."""
        pass
    
    @abstractmethod
    def check_syntax(self, code: str, filename: str) -> Tuple[bool, Optional[str]]:
        """
        Check syntax of code.
        
        Args:
            code: The code to check
            filename: Name of the file (for context)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def get_docker_image(self) -> str:
        """Return the Docker image to use for testing."""
        pass
    
    @abstractmethod
    def get_docker_test_command(self) -> str:
        """Return the Docker command to run tests."""
        pass
    
    def is_code_file(self, filename: str) -> bool:
        """Check if a file is a code file for this language."""
        return filename.endswith(self.get_code_extensions())
    
    def is_test_file(self, filename: str) -> bool:
        """Check if a file is a test file for this language."""
        return filename.endswith(self.get_test_extensions())


class PythonStrategy(LanguageStrategy):
    """Python-specific strategy implementation."""
    
    def get_code_extensions(self) -> tuple:
        return (".py",)
    
    def get_test_extensions(self) -> tuple:
        return ("_test.py", "test_.py")
    
    def check_syntax(self, code: str, filename: str) -> Tuple[bool, Optional[str]]:
        """Check Python syntax using AST parser."""
        if not filename.endswith(".py"):
            return True, None
        
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            error_msg = f"SyntaxError at line {e.lineno}: {e.msg}"
            if e.text:
                error_msg += f"\nLine content: {e.text}"
            return False, error_msg
        except Exception as e:
            return False, str(e)
    
    def get_docker_image(self) -> str:
        return "python:3.11-slim"
    
    def get_docker_test_command(self) -> str:
        return "pip install pytest -r requirements.txt -q && pytest"
    
    def identify_failing_test_file(self, test_log: str, repo_path: str) -> Optional[str]:
        """
        Scan pytest output to find the specific test file that failed.
        
        Args:
            test_log: The test output log
            repo_path: Path to the repository
            
        Returns:
            Path to failing test file or None
        """
        import re
        match = re.search(r'(tests[\\/][a-zA-Z0-9_]+\.py)', test_log)
        if match:
            return match.group(1).replace("\\", "/")
        return None


class MultiLanguageStrategy(LanguageStrategy):
    """
    Strategy that supports multiple languages.
    
    This is useful for polyglot projects. It delegates to language-specific
    strategies based on file extensions.
    """
    
    def __init__(self, strategies: List[LanguageStrategy]):
        """
        Initialize with a list of language strategies.
        
        Args:
            strategies: List of LanguageStrategy instances
        """
        self.strategies = strategies
    
    def get_code_extensions(self) -> tuple:
        """Return combined code extensions from all strategies."""
        extensions = []
        for strategy in self.strategies:
            extensions.extend(strategy.get_code_extensions())
        return tuple(extensions)
    
    def get_test_extensions(self) -> tuple:
        """Return combined test extensions from all strategies."""
        extensions = []
        for strategy in self.strategies:
            extensions.extend(strategy.get_test_extensions())
        return tuple(extensions)
    
    def check_syntax(self, code: str, filename: str) -> Tuple[bool, Optional[str]]:
        """Check syntax using the appropriate strategy for the file."""
        for strategy in self.strategies:
            if filename.endswith(strategy.get_code_extensions()):
                return strategy.check_syntax(code, filename)
        # If no specific strategy found, assume valid
        return True, None
    
    def get_docker_image(self) -> str:
        """Return the first strategy's Docker image (can be overridden)."""
        if self.strategies:
            return self.strategies[0].get_docker_image()
        return "ubuntu:latest"
    
    def get_docker_test_command(self) -> str:
        """Return the first strategy's test command (can be overridden)."""
        if self.strategies:
            return self.strategies[0].get_docker_test_command()
        return "echo 'No tests configured'"
