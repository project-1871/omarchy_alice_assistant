"""Web search tool using DuckDuckGo."""
import os
import sys
import re
import json
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.base import Tool


class WebSearchTool(Tool):
    """Search the web using DuckDuckGo."""

    name = "websearch"
    description = "Search the web for information"
    triggers = [
        "search the web", "search for", "look up", "google",
        "search online", "web search", "find online",
        "what is", "who is", "where is", "when was", "how do",
        "duckduckgo", "ddg"
    ]

    def __init__(self):
        self.api_url = "https://api.duckduckgo.com/"
        self.html_url = "https://html.duckduckgo.com/html/"

    def execute(self, query: str, **kwargs) -> str:
        # Extract search terms (remove trigger words)
        search_terms = self._extract_search_terms(query)

        if not search_terms:
            return "What should I search for?"

        # Try instant answer API first (fast, structured)
        result = self._instant_answer(search_terms)
        if result:
            return result

        # Fall back to HTML search
        return self._html_search(search_terms)

    def _extract_search_terms(self, query: str) -> str:
        """Extract actual search terms from query."""
        search_terms = query.lower()

        # Remove trigger phrases
        triggers_to_remove = [
            "search the web for", "search for", "look up",
            "google", "search online", "web search for",
            "web search", "find online", "duckduckgo", "ddg",
            "can you", "please", "alice"
        ]
        for trigger in triggers_to_remove:
            search_terms = search_terms.replace(trigger, "")

        return search_terms.strip()

    def _instant_answer(self, query: str) -> str | None:
        """Get instant answer from DuckDuckGo API."""
        try:
            params = urllib.parse.urlencode({
                'q': query,
                'format': 'json',
                'no_html': 1,
                'skip_disambig': 1
            })
            url = f"{self.api_url}?{params}"

            req = urllib.request.Request(url, headers={
                'User-Agent': 'Alice Assistant/1.0'
            })

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            # Check for abstract (main answer)
            if data.get('AbstractText'):
                source = data.get('AbstractSource', 'DuckDuckGo')
                abstract_url = data.get('AbstractURL', '')
                result = f"**{source}**: {data['AbstractText']}"
                if abstract_url:
                    result += f"\n\nSource: {abstract_url}"
                return result

            # Check for answer (direct answer)
            if data.get('Answer'):
                return f"**Answer**: {data['Answer']}"

            # Check for definition
            if data.get('Definition'):
                source = data.get('DefinitionSource', 'Dictionary')
                return f"**{source}**: {data['Definition']}"

            # Check for related topics
            if data.get('RelatedTopics'):
                results = []
                for topic in data['RelatedTopics'][:5]:
                    if isinstance(topic, dict) and topic.get('Text'):
                        results.append(f"- {topic['Text']}")
                if results:
                    return f"**Related results for '{query}':**\n" + "\n".join(results)

            return None

        except Exception as e:
            return None

    def _html_search(self, query: str) -> str:
        """Fallback: scrape DuckDuckGo HTML results."""
        try:
            data = urllib.parse.urlencode({'q': query}).encode('utf-8')
            req = urllib.request.Request(self.html_url, data=data, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0'
            })

            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8')

            # Extract results using regex (avoiding external dependencies)
            results = []

            # Find result snippets
            pattern = r'<a class="result__snippet"[^>]*>([^<]+)</a>'
            snippets = re.findall(pattern, html)

            # Find result titles and URLs
            title_pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
            titles = re.findall(title_pattern, html)

            for i, (url, title) in enumerate(titles[:5]):
                snippet = snippets[i] if i < len(snippets) else ""
                # Clean HTML entities
                title = self._clean_html(title)
                snippet = self._clean_html(snippet)
                results.append(f"**{title}**\n{snippet}\n{url}")

            if results:
                return f"**Web results for '{query}':**\n\n" + "\n\n".join(results)

            return f"No results found for '{query}'. Try a different search term."

        except Exception as e:
            return f"Search failed: {str(e)}. Check your internet connection."

    def _clean_html(self, text: str) -> str:
        """Clean HTML entities from text."""
        entities = {
            '&amp;': '&', '&lt;': '<', '&gt;': '>',
            '&quot;': '"', '&#39;': "'", '&nbsp;': ' ',
            '&#x27;': "'", '&#x2F;': '/'
        }
        for entity, char in entities.items():
            text = text.replace(entity, char)
        return text.strip()
