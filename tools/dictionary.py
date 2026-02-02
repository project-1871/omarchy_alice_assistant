"""Dictionary tool - definitions and synonyms using Free Dictionary API"""

import urllib.request
import urllib.parse
import json
import re
from tools.base import Tool


class DictionaryTool(Tool):
    name = "dictionary"
    description = "Look up word definitions and synonyms"
    triggers = [
        "define", "definition", "meaning of", "what does",
        "synonym", "synonyms", "thesaurus", "another word for",
        "how do you spell", "spell"
    ]

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        try:
            # Extract the word to look up
            word = self._extract_word(query_lower)
            if not word:
                return "What word would you like me to look up?"

            # Check if user wants synonyms
            if any(w in query_lower for w in ["synonym", "thesaurus", "another word"]):
                return self._get_synonyms(word)
            else:
                return self._get_definition(word)

        except Exception as e:
            return f"Dictionary lookup failed: {e}"

    def _extract_word(self, query: str) -> str | None:
        """Extract the word to look up from the query"""
        # Remove common phrases to find the word
        patterns = [
            r"define\s+(?:the\s+word\s+)?['\"]?(\w+)['\"]?",
            r"definition\s+(?:of\s+)?(?:the\s+word\s+)?['\"]?(\w+)['\"]?",
            r"meaning\s+of\s+(?:the\s+word\s+)?['\"]?(\w+)['\"]?",
            r"what\s+does\s+['\"]?(\w+)['\"]?\s+mean",
            r"synonym(?:s)?\s+(?:for|of)\s+['\"]?(\w+)['\"]?",
            r"another\s+word\s+for\s+['\"]?(\w+)['\"]?",
            r"(?:how\s+do\s+you\s+)?spell\s+['\"]?(\w+)['\"]?",
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                return match.group(1)

        # Fallback: get last word that isn't a common word
        common = {'define', 'definition', 'meaning', 'of', 'the', 'word', 'what',
                  'does', 'mean', 'synonym', 'synonyms', 'for', 'another', 'a', 'is'}
        words = [w for w in query.split() if w not in common and len(w) > 2]
        return words[-1] if words else None

    def _get_definition(self, word: str) -> str:
        """Get word definition from Free Dictionary API"""
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word)}"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Alice/1.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return f"I couldn't find a definition for '{word}'. Check the spelling?"
            raise

        if not data:
            return f"No definition found for '{word}'."

        entry = data[0]
        word_proper = entry.get('word', word)

        # Get phonetic
        phonetic = entry.get('phonetic', '')
        if not phonetic:
            phonetics = entry.get('phonetics', [])
            for p in phonetics:
                if p.get('text'):
                    phonetic = p['text']
                    break

        # Get definitions (limit to first 2 meanings)
        definitions = []
        for meaning in entry.get('meanings', [])[:2]:
            part_of_speech = meaning.get('partOfSpeech', '')
            for defn in meaning.get('definitions', [])[:1]:
                text = defn.get('definition', '')
                if text:
                    definitions.append(f"{part_of_speech}: {text}")

        if not definitions:
            return f"No definition found for '{word}'."

        result = f"{word_proper}"
        if phonetic:
            result += f" ({phonetic})"
        result += ". " + " ".join(definitions)

        return result

    def _get_synonyms(self, word: str) -> str:
        """Get synonyms from Free Dictionary API"""
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word)}"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Alice/1.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return f"I couldn't find synonyms for '{word}'."
            raise

        if not data:
            return f"No synonyms found for '{word}'."

        # Collect all synonyms
        synonyms = set()
        for entry in data:
            for meaning in entry.get('meanings', []):
                for syn in meaning.get('synonyms', []):
                    synonyms.add(syn)
                for defn in meaning.get('definitions', []):
                    for syn in defn.get('synonyms', []):
                        synonyms.add(syn)

        if not synonyms:
            return f"No synonyms found for '{word}'."

        # Limit to 8 synonyms
        syn_list = list(synonyms)[:8]

        if len(syn_list) == 1:
            return f"A synonym for '{word}' is {syn_list[0]}."
        else:
            return f"Synonyms for '{word}': {', '.join(syn_list)}."
