"""Document ingestion and retrieval tool."""
import os
import sys
import re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.base import Tool
from core.memory import Memory


class DocumentsTool(Tool):
    """Ingest and search documents (PDFs, images, text files)."""

    name = "documents"
    description = "Ingest and search PDFs, images, and documents"
    triggers = [
        "read this", "ingest this", "remember this document",
        "save this pdf", "scan this", "ocr this",
        "store this file", "add to memory",
        "search documents", "search my docs", "find in documents",
        "what do you know about", "what did i save about",
        "show me the", "recall the"
    ]

    def __init__(self):
        self.memory = Memory()

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        # Check if searching
        if any(t in query_lower for t in ["search", "find", "what do you know", "what did i save", "recall"]):
            return self._search_docs(query)

        # Check if listing
        if any(t in query_lower for t in ["list documents", "show documents", "my documents", "what documents"]):
            return self._list_docs()

        # Otherwise, try to ingest
        return self._ingest_doc(query)

    def _extract_path(self, query: str) -> str | None:
        """Extract file path from query."""
        # Look for quoted paths
        quoted = re.search(r'["\']([^"\']+)["\']', query)
        if quoted:
            return quoted.group(1)

        # Look for paths starting with / or ~ or .
        path_match = re.search(r'([/~.][^\s]+)', query)
        if path_match:
            path = path_match.group(1)
            # Expand ~
            if path.startswith('~'):
                path = os.path.expanduser(path)
            return path

        # Look for common file extensions
        ext_match = re.search(r'(\S+\.(?:pdf|png|jpg|jpeg|txt|md))', query, re.IGNORECASE)
        if ext_match:
            return ext_match.group(1)

        return None

    def _extract_name(self, query: str) -> str | None:
        """Extract document name from query."""
        # Look for "as <name>" or "called <name>"
        name_match = re.search(r'(?:as|called|named)\s+["\']?(\w+)["\']?', query, re.IGNORECASE)
        if name_match:
            return name_match.group(1)
        return None

    def _ingest_doc(self, query: str) -> str:
        """Ingest a document into memory."""
        path = self._extract_path(query)
        if not path:
            return "I need a file path. Try: 'read this /path/to/file.pdf' or 'ingest ~/Documents/notes.txt'"

        # Expand path
        path = os.path.expanduser(path)

        if not os.path.exists(path):
            return f"File not found: {path}"

        name = self._extract_name(query)
        success, message = self.memory.ingest_file(path, name)

        if success:
            return f"Got it. {message}"
        else:
            return f"Couldn't ingest that. {message}"

    def _search_docs(self, query: str) -> str:
        """Search documents for a query."""
        # Extract search terms (remove trigger words)
        search_terms = query.lower()
        for trigger in ["search documents", "search my docs", "find in documents",
                        "what do you know about", "what did i save about",
                        "search for", "find", "search"]:
            search_terms = search_terms.replace(trigger, "")
        search_terms = search_terms.strip()

        if not search_terms:
            return "What should I search for?"

        results = self.memory.search_docs(search_terms)

        if not results:
            return f"Nothing found for '{search_terms}' in your documents."

        response = f"Found {len(results)} match(es) for '{search_terms}':\n\n"
        for r in results[:5]:  # Limit to 5 results
            response += f"**{r['name']}** ({r['type']}):\n"
            response += f"...{r['snippet']}...\n\n"

        return response

    def _list_docs(self) -> str:
        """List all stored documents."""
        docs = self.memory.list_docs()

        if not docs:
            return "No documents stored yet. Use 'read this /path/to/file' to add one."

        response = f"You have {len(docs)} document(s) stored:\n"
        for doc_name in docs:
            doc = self.memory.get_doc(doc_name)
            doc_type = doc.get('type', 'unknown') if doc else 'unknown'
            response += f"- {doc_name} ({doc_type})\n"

        return response
