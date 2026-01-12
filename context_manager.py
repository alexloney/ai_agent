"""
Context Manager for RAG (Retrieval-Augmented Generation).

This module provides semantic search capabilities for code using vector embeddings.
It enables the agent to find relevant code files based on issue descriptions rather
than relying on fixed file limits.
"""

import os
import hashlib
from typing import List, Dict, Tuple, Optional, Any
import chromadb
from chromadb.config import Settings


class CodeContextManager:
    """Manages code embeddings and semantic search using ChromaDB."""
    
    def __init__(self, repo_path: str, persist_directory: str = None):
        """
        Initialize the context manager.
        
        Args:
            repo_path: Path to the repository
            persist_directory: Directory to persist the vector database (default: .chroma in repo)
        """
        self.repo_path = repo_path
        
        # Use a persistent directory in the repo
        if persist_directory is None:
            persist_directory = os.path.join(repo_path, ".chroma")
        
        self.persist_directory = persist_directory
        
        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False
        ))
        
        # Collection name based on repo path hash for uniqueness
        repo_hash = hashlib.md5(repo_path.encode()).hexdigest()[:8]
        self.collection_name = f"code_embeddings_{repo_hash}"
        
        # Try to get existing collection or create new
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
        except Exception as e:
            # Collection doesn't exist, create it
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"repo_path": repo_path}
            )
    
    def _chunk_code(self, code: str, filename: str, chunk_size: int = 1000) -> List[Dict[str, str]]:
        """
        Chunk code into manageable pieces for embedding.
        
        For Python files, tries to chunk by functions/classes.
        For other files, uses simple line-based chunking.
        
        Args:
            code: The code content
            filename: Name of the file
            chunk_size: Target size for chunks in characters
            
        Returns:
            List of chunk dictionaries with 'content', 'start_line', 'end_line'
        """
        chunks = []
        
        if filename.endswith('.py'):
            # Try to chunk by functions/classes
            lines = code.split('\n')
            current_chunk = []
            current_start = 1
            in_function_or_class = False
            indent_level = 0
            
            # Track if we've seen any function/class yet
            has_seen_definition = False
            
            for i, line in enumerate(lines, 1):
                stripped = line.lstrip()
                
                # Detect function or class definition
                if stripped.startswith(('def ', 'class ', 'async def ')):
                    # Save previous chunk if it exists
                    if current_chunk:
                        chunks.append({
                            'content': '\n'.join(current_chunk),
                            'start_line': current_start,
                            'end_line': i - 1
                        })
                    current_chunk = [line]
                    current_start = i
                    in_function_or_class = True
                    has_seen_definition = True
                    indent_level = len(line) - len(stripped)
                elif in_function_or_class:
                    current_chunk.append(line)
                    # Check if we've exited the function/class (simplified heuristic)
                    # A non-empty line with same or less indentation than the def/class line
                    # likely indicates we've exited (unless it's a continuation or decorator)
                    current_indent = len(line) - len(stripped) if stripped else float('inf')
                    if stripped and current_indent <= indent_level and i > current_start:
                        # Don't exit on decorators or strings
                        if not stripped.startswith(('@', '"', "'", '#')):
                            in_function_or_class = False
                else:
                    current_chunk.append(line)
                    
                    # Special handling for module-level code before first definition
                    # If we haven't seen a definition yet and chunk is getting large,
                    # save it as "imports and module constants" chunk
                    if not has_seen_definition and len('\n'.join(current_chunk)) > chunk_size // 2:
                        chunks.append({
                            'content': '\n'.join(current_chunk),
                            'start_line': current_start,
                            'end_line': i
                        })
                        current_chunk = []
                        current_start = i + 1
                
                # Also split if chunk gets too large
                if len('\n'.join(current_chunk)) > chunk_size:
                    chunks.append({
                        'content': '\n'.join(current_chunk),
                        'start_line': current_start,
                        'end_line': i
                    })
                    current_chunk = []
                    current_start = i + 1
            
            # Add final chunk - this ensures trailing code is captured
            if current_chunk:
                chunks.append({
                    'content': '\n'.join(current_chunk),
                    'start_line': current_start,
                    'end_line': len(lines)
                })
        else:
            # Simple line-based chunking for non-Python files
            lines = code.split('\n')
            current_chunk = []
            current_start = 1
            
            for i, line in enumerate(lines, 1):
                current_chunk.append(line)
                
                if len('\n'.join(current_chunk)) > chunk_size:
                    chunks.append({
                        'content': '\n'.join(current_chunk),
                        'start_line': current_start,
                        'end_line': i
                    })
                    current_chunk = []
                    current_start = i + 1
            
            # Add final chunk
            if current_chunk:
                chunks.append({
                    'content': '\n'.join(current_chunk),
                    'start_line': current_start,
                    'end_line': len(lines)
                })
        
        return chunks if chunks else [{'content': code, 'start_line': 1, 'end_line': len(code.split('\n'))}]
    
    def index_codebase(self, file_list: List[str], force_reindex: bool = False):
        """
        Index the codebase into the vector database.
        
        Args:
            file_list: List of file paths to index
            force_reindex: If True, clear existing index and reindex all files
        """
        if force_reindex:
            # Delete and recreate collection
            try:
                self.client.delete_collection(name=self.collection_name)
            except:
                pass
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"repo_path": self.repo_path}
            )
        
        documents = []
        metadatas = []
        ids = []
        
        for file_path in file_list:
            full_path = os.path.join(self.repo_path, file_path)
            
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                # Chunk the code
                chunks = self._chunk_code(code, file_path)
                
                for idx, chunk in enumerate(chunks):
                    # Create unique ID for this chunk
                    chunk_id = f"{file_path}::{idx}"
                    
                    # Store chunk content and metadata
                    documents.append(chunk['content'])
                    metadatas.append({
                        'file_path': file_path,
                        'chunk_index': idx,
                        'start_line': chunk['start_line'],
                        'end_line': chunk['end_line'],
                        'file_size': len(code)
                    })
                    ids.append(chunk_id)
                    
            except Exception as e:
                print(f"Warning: Could not index {file_path}: {e}")
                continue
        
        # Add to collection in batches (ChromaDB has limits)
        batch_size = 5000
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i+batch_size]
            batch_meta = metadatas[i:i+batch_size]
            batch_ids = ids[i:i+batch_size]
            
            self.collection.add(
                documents=batch_docs,
                metadatas=batch_meta,
                ids=batch_ids
            )
        
        print(f"✅ Indexed {len(documents)} code chunks from {len(file_list)} files")
    
    def semantic_search(self, query: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        Perform semantic search on the codebase.
        
        Args:
            query: The search query (e.g., issue description or feature name)
            n_results: Number of results to return
            
        Returns:
            List of dictionaries containing file_path, content, relevance score
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            # Format results
            search_results = []
            if results['documents'] and len(results['documents']) > 0:
                for i in range(len(results['documents'][0])):
                    search_results.append({
                        'file_path': results['metadatas'][0][i]['file_path'],
                        'content': results['documents'][0][i],
                        'start_line': results['metadatas'][0][i]['start_line'],
                        'end_line': results['metadatas'][0][i]['end_line'],
                        'distance': results['distances'][0][i] if 'distances' in results else None
                    })
            
            return search_results
        except Exception as e:
            print(f"Warning: Semantic search failed: {e}")
            return []
    
    def get_relevant_files(self, query: str, max_files: int = 20) -> List[str]:
        """
        Get a list of relevant files for a given query.
        
        This is the main method used by the agent to find files related to an issue.
        
        Args:
            query: The issue description or search query
            max_files: Maximum number of files to return
            
        Returns:
            List of file paths sorted by relevance
        """
        # Search for relevant chunks
        results = self.semantic_search(query, n_results=max_files * 3)
        
        # Deduplicate by file path and sort by relevance
        seen_files = {}
        for result in results:
            file_path = result['file_path']
            if file_path not in seen_files:
                seen_files[file_path] = result['distance'] if result['distance'] else 0
        
        # Sort by distance (lower is better)
        sorted_files = sorted(seen_files.items(), key=lambda x: x[1])
        
        # Return file paths
        return [f[0] for f in sorted_files[:max_files]]
    
    def get_file_content_with_context(self, file_path: str, query: str = None) -> str:
        """
        Get file content with optional relevant context highlighted.
        
        Args:
            file_path: Path to the file
            query: Optional query to find relevant sections
            
        Returns:
            File content as string
        """
        full_path = os.path.join(self.repo_path, file_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return ""
