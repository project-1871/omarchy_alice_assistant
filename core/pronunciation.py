"""Pronunciation preprocessing for TTS."""
import re


# Contractions to expand before TTS (apostrophes confuse the model)
# Order matters: longer/specific matches first
CONTRACTIONS = {
    # Negatives
    "won't": "will not",
    "can't": "cannot",
    "shan't": "shall not",
    "shouldn't": "should not",
    "wouldn't": "would not",
    "couldn't": "could not",
    "mustn't": "must not",
    "mightn't": "might not",
    "needn't": "need not",
    "hadn't": "had not",
    "hasn't": "has not",
    "haven't": "have not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "doesn't": "does not",
    "didn't": "did not",
    "don't": "do not",
    "ain't": "am not",
    # Will
    "I'll": "I will",
    "you'll": "you will",
    "he'll": "he will",
    "she'll": "she will",
    "it'll": "it will",
    "we'll": "we will",
    "they'll": "they will",
    "that'll": "that will",
    "who'll": "who will",
    # Would / Had
    "I'd": "I would",
    "you'd": "you would",
    "he'd": "he would",
    "she'd": "she would",
    "we'd": "we would",
    "they'd": "they would",
    "who'd": "who would",
    # Have
    "I've": "I have",
    "you've": "you have",
    "we've": "we have",
    "they've": "they have",
    "could've": "could have",
    "would've": "would have",
    "should've": "should have",
    "might've": "might have",
    "must've": "must have",
    # Am / Are / Is
    "I'm": "I am",
    "you're": "you are",
    "he's": "he is",
    "she's": "she is",
    "it's": "it is",
    "we're": "we are",
    "they're": "they are",
    "that's": "that is",
    "there's": "there is",
    "here's": "here is",
    "what's": "what is",
    "who's": "who is",
    "how's": "how is",
    "where's": "where is",
    "when's": "when is",
    "let's": "let us",
}

# Names that need phonetic spelling for Piper/Alba
# Add entries as: 'original': 'phonetic'
NAMES = {
    # Examples - add names Alice mispronounces
    # 'Glenn': 'Glen',
    # 'Niamh': 'Neev',
    # 'Siobhan': 'Shivawn',
}

# Abbreviations to expand
ABBREVIATIONS = {
    # Titles
    'Dr.': 'Doctor',
    'Dr': 'Doctor',
    'Mr.': 'Mister',
    'Mr': 'Mister',
    'Mrs.': 'Missus',
    'Mrs': 'Missus',
    'Ms.': 'Miss',
    'Ms': 'Miss',
    'Prof.': 'Professor',
    'Jr.': 'Junior',
    'Sr.': 'Senior',
    'St.': 'Saint',

    # Common
    'etc.': 'etcetera',
    'vs.': 'versus',
    'vs': 'versus',
    'e.g.': 'for example',
    'i.e.': 'that is',
    'w/': 'with',
    'w/o': 'without',
    'b/c': 'because',

    # Tech
    'API': 'A P I',
    'APIs': 'A P Is',
    'URL': 'U R L',
    'URLs': 'U R Ls',
    'UI': 'U I',
    'CPU': 'C P U',
    'GPU': 'G P U',
    'RAM': 'ram',
    'SSD': 'S S D',
    'HDD': 'H D D',
    'USB': 'U S B',
    'HTTP': 'H T T P',
    'HTTPS': 'H T T P S',
    'HTML': 'H T M L',
    'CSS': 'C S S',
    'JSON': 'jason',
    'SQL': 'sequel',
    'CLI': 'C L I',
    'GUI': 'gooey',
    'OS': 'O S',
    'IP': 'I P',
    'AI': 'A I',
    'ML': 'M L',
    'LLM': 'L L M',
    'TTS': 'T T S',
    'STT': 'S T T',

    # Units
    'GB': 'gigabytes',
    'MB': 'megabytes',
    'KB': 'kilobytes',
    'TB': 'terabytes',
    'GHz': 'gigahertz',
    'MHz': 'megahertz',
    'km': 'kilometers',
    'cm': 'centimeters',
    'mm': 'millimeters',
    'kg': 'kilograms',
    'mg': 'milligrams',

    # Time
    'hr': 'hour',
    'hrs': 'hours',
    'min': 'minute',
    'mins': 'minutes',
    'sec': 'second',
    'secs': 'seconds',
    'approx.': 'approximately',
    'approx': 'approximately',

    # Days/Months
    'Mon': 'Monday',
    'Tue': 'Tuesday',
    'Wed': 'Wednesday',
    'Thu': 'Thursday',
    'Fri': 'Friday',
    'Sat': 'Saturday',
    'Sun': 'Sunday',
    'Jan': 'January',
    'Feb': 'February',
    'Mar': 'March',
    'Apr': 'April',
    'Jun': 'June',
    'Jul': 'July',
    'Aug': 'August',
    'Sep': 'September',
    'Oct': 'October',
    'Nov': 'November',
    'Dec': 'December',
}

# Symbols to remove entirely
SYMBOLS_TO_REMOVE = [
    '*', '#', '`', '~', '^', '|', '\\', '{', '}', '[', ']',
    '<', '>', '_', '•', '→', '←', '↑', '↓', '©', '®', '™',
    '§', '¶', '†', '‡',
]

# Symbols to replace with words (optional - for ones that carry meaning)
SYMBOLS_TO_WORDS = {
    '@': ' at ',
    '&': ' and ',
    '+': ' plus ',
    '=': ' equals ',
    '%': ' percent',
    '/': ' ',  # Just a space, or could be 'slash' if needed
    '$': ' dollars',
    '£': ' pounds',
    '€': ' euros',
    # Pause punctuation — preserve as commas so the model breathes naturally
    '…': ', ',
    '—': ', ',
    '–': ', ',
}


def preprocess(text: str) -> str:
    """Clean up text for better TTS pronunciation."""
    if not text:
        return text

    # 0. Expand contractions (apostrophes confuse KittenTTS)
    # Normalize curly apostrophes to straight first
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    for contraction, expansion in CONTRACTIONS.items():
        # Case-insensitive replacement, preserving original case flavor
        pattern = r'\b' + re.escape(contraction) + r'\b'
        text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)

    # 1a. Normalize ellipsis variants to pause before symbol replacement
    text = re.sub(r'\.{2,}', ', ', text)  # ... or .... → pause

    # 1b. Collapse repeated punctuation
    text = re.sub(r'!{2,}', '!', text)
    text = re.sub(r'\?{2,}', '?', text)

    # 1. Handle symbols that become words
    for symbol, word in SYMBOLS_TO_WORDS.items():
        text = text.replace(symbol, word)

    # 2. Remove unwanted symbols
    for symbol in SYMBOLS_TO_REMOVE:
        text = text.replace(symbol, '')

    # 3. Expand abbreviations (word boundary aware)
    for abbrev, expansion in ABBREVIATIONS.items():
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(abbrev) + r'\b'
        text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)

    # 4. Fix names (case-sensitive for proper nouns)
    for name, phonetic in NAMES.items():
        pattern = r'\b' + re.escape(name) + r'\b'
        text = re.sub(pattern, phonetic, text)

    # 5. Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()

    # 6. Clean up orphaned punctuation
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)

    # 7. Semicolons → comma pause (model handles commas better than semicolons)
    text = text.replace(';', ',')

    # 7b. Lengthen pause after sentence-ending periods (before next word or end of string)
    # Inserts a comma after the period so the model takes an extra breath
    text = re.sub(r'\. ([A-Z])', r'. , \1', text)  # mid-text sentences
    text = re.sub(r'\.$', '. ,', text)              # final period

    # 8. Ensure text ends with punctuation so the model doesn't trail off
    text = text.strip()
    if text and text[-1] not in '.!?,':
        text += '.'

    return text
