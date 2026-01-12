"""
Token Manager for controlling context size and preventing token overflow.

This module provides utilities to estimate token counts and manage context
to prevent LLM confusion or crashes due to excessive input.
"""

from typing import List, Dict, Any


class TokenManager:
    """Manages token counts and context truncation."""
    
    # Approximate tokens per character (rough estimate)
    # Most LLMs average ~4 characters per token
    CHARS_PER_TOKEN = 4
    
    def __init__(self, max_tokens: int = 16000):
        """
        Initialize TokenManager.
        
        Args:
            max_tokens: Maximum number of tokens to allow in context
        """
        self.max_tokens = max_tokens
        self.token_budget = {
            'exploration_log': max_tokens // 4,  # 25% for exploration
            'file_content': max_tokens // 2,      # 50% for file content
            'other': max_tokens // 4              # 25% for prompts and other
        }
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a text string.
        
        Args:
            text: The text to estimate
            
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        return len(text) // self.CHARS_PER_TOKEN
    
    def truncate_to_token_limit(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within a token limit.
        
        Args:
            text: The text to truncate
            max_tokens: Maximum number of tokens
            
        Returns:
            Truncated text with ellipsis if truncated
        """
        estimated_tokens = self.estimate_tokens(text)
        
        if estimated_tokens <= max_tokens:
            return text
        
        # Calculate target character count
        target_chars = max_tokens * self.CHARS_PER_TOKEN
        
        # Truncate and add ellipsis
        truncated = text[:target_chars]
        return truncated + f"\n\n... [Truncated. Original length: {len(text)} chars, ~{estimated_tokens} tokens]"
    
    def summarize_exploration_log(self, exploration_log: List[str]) -> List[str]:
        """
        Summarize exploration log if it exceeds token budget.
        
        Keeps the most recent entries and summarizes older ones.
        
        Args:
            exploration_log: List of exploration log entries
            
        Returns:
            Summarized log entries
        """
        if not exploration_log:
            return []
        
        # Calculate total tokens
        total_text = '\n\n'.join(exploration_log)
        total_tokens = self.estimate_tokens(total_text)
        
        if total_tokens <= self.token_budget['exploration_log']:
            return exploration_log
        
        # Keep recent entries, summarize old ones
        # Keep last 3 entries in full
        recent_entries = exploration_log[-3:]
        old_entries = exploration_log[:-3]
        
        # Create summary of old entries
        old_summary = f"Previous {len(old_entries)} tool executions (summarized)"
        
        return [old_summary] + recent_entries
    
    def truncate_file_content(self, file_contents: Dict[str, str], max_tokens: int = None) -> Dict[str, str]:
        """
        Truncate file contents to fit within token budget.
        
        Args:
            file_contents: Dictionary of filename -> content
            max_tokens: Maximum tokens for all files (default: use budget)
            
        Returns:
            Truncated file contents
        """
        if max_tokens is None:
            max_tokens = self.token_budget['file_content']
        
        # Calculate total tokens
        total_text = '\n\n'.join(file_contents.values())
        total_tokens = self.estimate_tokens(total_text)
        
        if total_tokens <= max_tokens:
            return file_contents
        
        # Distribute tokens evenly across files
        tokens_per_file = max_tokens // len(file_contents)
        
        truncated_contents = {}
        for filename, content in file_contents.items():
            truncated_contents[filename] = self.truncate_to_token_limit(
                content, 
                tokens_per_file
            )
        
        return truncated_contents
    
    def get_context_stats(self, **contexts) -> Dict[str, Any]:
        """
        Get statistics about context usage.
        
        Args:
            **contexts: Named text contexts to analyze
            
        Returns:
            Dictionary with token statistics
        """
        stats = {
            'max_tokens': self.max_tokens,
            'budgets': self.token_budget,
            'contexts': {}
        }
        
        total_tokens = 0
        for name, text in contexts.items():
            if isinstance(text, list):
                text = '\n\n'.join(str(item) for item in text)
            elif not isinstance(text, str):
                text = str(text)
            
            tokens = self.estimate_tokens(text)
            total_tokens += tokens
            
            stats['contexts'][name] = {
                'tokens': tokens,
                'chars': len(text),
                'percentage': round(tokens / self.max_tokens * 100, 1)
            }
        
        stats['total_tokens'] = total_tokens
        stats['total_percentage'] = round(total_tokens / self.max_tokens * 100, 1)
        stats['remaining_tokens'] = self.max_tokens - total_tokens
        
        return stats
    
    def check_budget_exceeded(self, **contexts) -> bool:
        """
        Check if token budget is exceeded.
        
        Args:
            **contexts: Named text contexts to check
            
        Returns:
            True if budget exceeded, False otherwise
        """
        stats = self.get_context_stats(**contexts)
        return stats['total_tokens'] > self.max_tokens
    
    def auto_truncate_contexts(self, **contexts) -> Dict[str, str]:
        """
        Automatically truncate contexts to fit within budget.
        
        Prioritizes keeping more recent/important information.
        
        Args:
            **contexts: Named text contexts
            
        Returns:
            Dictionary of truncated contexts
        """
        stats = self.get_context_stats(**contexts)
        
        if stats['total_tokens'] <= self.max_tokens:
            return contexts
        
        print(f"⚠️ Token budget exceeded: {stats['total_tokens']}/{self.max_tokens} tokens")
        print(f"   Truncating contexts to fit within budget...")
        
        # Calculate tokens to remove
        excess_tokens = stats['total_tokens'] - self.max_tokens
        
        # Priority: exploration_log (oldest first), then file_content (proportional)
        truncated = {}
        
        for name, text in contexts.items():
            current_tokens = stats['contexts'][name]['tokens']
            
            if name == 'exploration_log' and isinstance(text, list):
                # Summarize exploration log
                truncated[name] = self.summarize_exploration_log(text)
            elif name == 'file_content' and isinstance(text, dict):
                # Truncate file contents proportionally
                truncated[name] = self.truncate_file_content(text)
            else:
                # For other contexts, truncate if needed
                # Allow 80% of budget for priority contexts
                budget = int(self.max_tokens * 0.1)  # 10% for each other context
                if current_tokens > budget:
                    truncated[name] = self.truncate_to_token_limit(text, budget)
                else:
                    truncated[name] = text
        
        # Verify we're now within budget
        final_stats = self.get_context_stats(**truncated)
        print(f"   ✅ Reduced to {final_stats['total_tokens']} tokens ({final_stats['total_percentage']}%)")
        
        return truncated
