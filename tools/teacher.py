"""Teacher mode — lesson engine for Alice's teaching functionality."""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

LESSONS_DIR = getattr(config, 'LESSONS_DIR', '/home/glenn/500G/learning/classes')
LESSON_PROGRESS_FILE = getattr(config, 'LESSON_PROGRESS_FILE',
                               os.path.join(config.MEMORY_DIR, 'lesson_progress.json'))
SCHEDULE_FILE = os.path.join(LESSONS_DIR, '00-schedule.md')

# Phrases meaning "advance" (next section OR next step)
ADVANCE_PHRASES = [
    'next', 'continue', 'move on', 'ready', 'got it', 'understood',
    "let's continue", 'lets continue', 'keep going', 'go on', 'go ahead',
    'i understand', 'i get it', 'yep', 'ok', 'okay', 'yes', 'yeah',
    'done', 'done it', 'all done', 'finished', 'finished it', 'completed',
    'move forward', 'proceed', 'sounds good', "i'm done", 'im done',
]

# LLM uncertainty markers — trigger web search escalation
UNCERTAINTY_MARKERS = [
    "i'm not sure", "i don't know", "i'm uncertain",
    "i'm not certain", "i cannot say", "i don't have",
    "not sure", "don't know", "unclear to me",
    "cannot be certain", "i lack", "i have no information",
    "i'm unsure", "i am not sure", "not confident",
]


# ─────────────────────────────────────────────
# Progress file helpers
# ─────────────────────────────────────────────

def load_progress() -> dict:
    """Load lesson progress from persistent file."""
    if os.path.exists(LESSON_PROGRESS_FILE):
        try:
            with open(LESSON_PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        'lessons_completed': [],
        'current_lesson': None,
        'weak_topics': {},
        'session_notes': [],
        'total_sessions': 0,
        'last_session': None,
    }


def save_progress(data: dict):
    """Save lesson progress to persistent file."""
    os.makedirs(os.path.dirname(LESSON_PROGRESS_FILE), exist_ok=True)
    with open(LESSON_PROGRESS_FILE, 'w') as f:
        json.dump(data, f, indent=2, default=str)


# ─────────────────────────────────────────────
# Schedule parsing
# ─────────────────────────────────────────────

def get_schedule() -> list[dict]:
    """Parse 00-schedule.md and return all lessons with dates.

    Returns list of dicts:
        {'number': 1, 'date': '2026-03-17', 'tool': 'Wappalyzer', 'file': '01-wappalyzer.md'}
    """
    lessons = []
    if not os.path.exists(SCHEDULE_FILE):
        return lessons

    try:
        content = Path(SCHEDULE_FILE).read_text()
        # Match table rows: | 1 | Mar 17, 2026 | Tuesday | Wappalyzer | [01-wappalyzer.md](01-wappalyzer.md) |
        pattern = (
            r'\|\s*(\d+)\s*\|\s*'
            r'([A-Za-z]+ \d+, \d{4})\s*\|\s*'
            r'\w+\s*\|\s*'
            r'([^|]+?)\s*\|\s*'
            r'\[([^\]]+\.md)\]'
        )
        for m in re.finditer(pattern, content):
            num = int(m.group(1))
            date_str = m.group(2).strip()
            tool = m.group(3).strip()
            filename = m.group(4).strip()
            try:
                dt = datetime.strptime(date_str, '%b %d, %Y')
                iso_date = dt.strftime('%Y-%m-%d')
            except ValueError:
                iso_date = date_str
            lessons.append({
                'number': num,
                'date': iso_date,
                'tool': tool,
                'file': filename,
            })
    except Exception:
        pass

    return lessons


def get_todays_lesson() -> dict | None:
    """Return today's scheduled lesson if today is a class day."""
    today = datetime.now().strftime('%Y-%m-%d')
    for lesson in get_schedule():
        if lesson['date'] == today:
            return lesson
    return None


def get_next_lesson() -> dict | None:
    """Return the next lesson that hasn't been completed yet."""
    progress = load_progress()
    completed_nums = {l['number'] for l in progress.get('lessons_completed', [])}
    for lesson in get_schedule():
        if lesson['number'] not in completed_nums:
            return lesson
    return None


def get_all_lessons_with_status() -> list[dict]:
    """Return all lessons with completion status and date."""
    progress = load_progress()
    completed_nums = {l['number'] for l in progress.get('lessons_completed', [])}
    lessons = get_schedule()
    today = datetime.now().strftime('%Y-%m-%d')
    for lesson in lessons:
        lesson['completed'] = lesson['number'] in completed_nums
        lesson['is_today'] = lesson['date'] == today
    return lessons


# ─────────────────────────────────────────────
# Lesson file parsing
# ─────────────────────────────────────────────

class LessonSection:
    """A parsed section from a lesson markdown file."""

    def __init__(self, number: int, title: str, content: str):
        self.number = number
        self.title = title
        self.content = content

    def is_hands_on(self) -> bool:
        """True if this is a practical/hands-on section."""
        t = self.title.lower()
        return any(kw in t for kw in [
            'step-by-step', 'hands-on', 'practice', 'exercise',
            'installing', 'install', 'first launch', 'getting your bearings',
        ])

    def truncated(self, max_chars: int = 2500) -> str:
        """Return content truncated to max_chars."""
        if len(self.content) <= max_chars:
            return self.content
        return self.content[:max_chars] + '\n\n[...section continues...]'

    def __repr__(self):
        return f'Section({self.number}: {self.title})'


class StepBlock:
    """A single step chunk from a hands-on section (one Part or one Exercise)."""

    def __init__(self, title: str, content: str):
        self.title = title
        self.content = content.strip()

    def truncated(self, max_chars: int = 2000) -> str:
        if len(self.content) <= max_chars:
            return self.content
        return self.content[:max_chars] + '\n[...continues...]'

    def __repr__(self):
        return f'StepBlock({self.title[:40]})'


def parse_hands_on_chunks(section: LessonSection) -> list[StepBlock]:
    """Split a hands-on section into step chunks.

    Strategy:
    - Section 6 (Step-by-Step): split on '### Part N:' headers
    - Section 7 (Exercises): split on '**Exercise N:' pattern
    - Sections 3/4 (Install/First Launch): no sub-headers → return as one chunk
    """
    content = section.content

    # Try ### Part headers (section 6)
    parts = re.split(r'\n(?=### )', content)
    if len(parts) > 1 or (parts and re.match(r'^### ', content.strip())):
        blocks = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            m = re.match(r'^### (.+?)\n(.*)', part, re.DOTALL)
            if m:
                blocks.append(StepBlock(title=m.group(1).strip(), content=m.group(2).strip()))
            else:
                # Text before any ### header (rare — usually empty for these lessons)
                blocks.append(StepBlock(title='Overview', content=part))
        if len(blocks) > 1 or (blocks and '###' in content):
            return [b for b in blocks if b.content]

    # Try **Exercise N: pattern (section 7)
    parts = re.split(r'\n(?=\*\*Exercise \d+)', content)
    if len(parts) > 1:
        blocks = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            m = re.match(r'^\*\*Exercise (\d+): (.+?)\*\*\n?(.*)', part, re.DOTALL)
            if m:
                title = f"Exercise {m.group(1)}: {m.group(2).strip()}"
                blocks.append(StepBlock(title=title, content=m.group(3).strip()))
            else:
                # Setup text before Exercise 1
                blocks.append(StepBlock(title='Setup', content=part))
        filtered = [b for b in blocks if b.content]
        # Merge tiny setup/intro chunk into the first real chunk
        if (len(filtered) >= 2 and filtered[0].title in ('Setup', 'Overview')
                and len(filtered[0].content) < 150):
            filtered[1] = StepBlock(
                title=filtered[1].title,
                content=filtered[0].content + '\n\n' + filtered[1].content
            )
            filtered = filtered[1:]
        return filtered

    # No sub-structure — return whole section as one block
    return [StepBlock(title=section.title, content=section.content)]


def parse_lesson_file(file_path: str) -> tuple[str, list[LessonSection]]:
    """Parse a lesson markdown file.

    Returns (lesson_title, [LessonSection, ...])
    """
    content = Path(file_path).read_text()

    # Extract lesson title from first # heading
    title_match = re.match(r'^# (.+)', content, re.MULTILINE)
    lesson_title = title_match.group(1).strip() if title_match else Path(file_path).stem

    # Split on ## N. headers
    parts = re.split(r'\n(?=## \d+\.)', content)
    sections = []
    for part in parts:
        m = re.match(r'^## (\d+)\.\s+(.+?)\n(.*)', part.strip(), re.DOTALL)
        if m:
            sec_num = int(m.group(1))
            sec_title = m.group(2).strip()
            sec_content = m.group(3).strip()
            sections.append(LessonSection(sec_num, sec_title, sec_content))

    return lesson_title, sections


# ─────────────────────────────────────────────
# Teacher session
# ─────────────────────────────────────────────

class TeacherSession:
    """Manages a single lesson teaching session for Alice."""

    def __init__(self, lesson_info: dict):
        self.lesson_number = lesson_info['number']
        self.lesson_tool = lesson_info['tool']
        self.lesson_file = os.path.join(LESSONS_DIR, lesson_info['file'])

        # Load student profile
        self.progress = load_progress()

        # Parse lesson content
        self.lesson_title, self.sections = parse_lesson_file(self.lesson_file)

        # Session state
        self.current_idx = 0          # which section we're presenting
        self.phase = 'intro'          # intro → teaching → quiz → done
        self.quiz_round = 0           # 0-3, tracks quiz question count
        self.quiz_score = 0           # correct quiz answers
        self.questions_asked = []     # [{question, section, escalated}]
        self.weak_topics = []         # topics Glenn struggled with this session
        self.session_start = datetime.now().isoformat()

        # Step-by-step mode state (for hands-on sections)
        self.step_blocks: list[StepBlock] = []
        self.current_step_idx: int = 0
        self.in_step_mode: bool = False

    # ── Accessors ──

    @property
    def current_section(self) -> LessonSection | None:
        if 0 <= self.current_idx < len(self.sections):
            return self.sections[self.current_idx]
        return None

    @property
    def total_sections(self) -> int:
        return len(self.sections)

    def progress_str(self) -> str:
        """e.g. 'Section 3/10'"""
        return f'Section {self.current_idx + 1}/{self.total_sections}'

    def is_last_section(self) -> bool:
        return self.current_idx >= len(self.sections) - 1

    # ── Step mode accessors ──

    @property
    def current_step(self) -> StepBlock | None:
        if self.in_step_mode and 0 <= self.current_step_idx < len(self.step_blocks):
            return self.step_blocks[self.current_step_idx]
        return None

    def step_progress_str(self) -> str:
        """e.g. 'Step 2/5' within a section."""
        total = len(self.step_blocks)
        current = self.current_step_idx + 1
        return f'Step {current}/{total}'

    def full_progress_str(self) -> str:
        """Combined progress: 'Section 6/10 · Step 2/5' or just 'Section 3/10'."""
        base = self.progress_str()
        if self.in_step_mode and self.step_blocks:
            return f'{base} · {self.step_progress_str()}'
        return base

    def is_last_step(self) -> bool:
        return self.current_step_idx >= len(self.step_blocks) - 1

    def enter_step_mode(self):
        """Parse current section into chunks and enter step-by-step mode."""
        section = self.current_section
        if section:
            self.step_blocks = parse_hands_on_chunks(section)
            self.current_step_idx = 0
            self.in_step_mode = True

    def exit_step_mode(self):
        """Clear step state and return to normal section mode."""
        self.step_blocks = []
        self.current_step_idx = 0
        self.in_step_mode = False

    def advance_step(self) -> bool:
        """Move to next step. Returns False if already at last step."""
        if not self.is_last_step():
            self.current_step_idx += 1
            return True
        return False

    # ── Student context ──

    def student_context(self) -> str:
        """Build a brief student profile string for the LLM."""
        parts = []
        completed = self.progress.get('lessons_completed', [])
        if completed:
            parts.append(f"Lessons completed: {len(completed)}")

        weak = self.progress.get('weak_topics', {})
        if weak:
            top = sorted(weak.items(), key=lambda x: x[1], reverse=True)[:4]
            parts.append('Topics Glenn has struggled with: ' +
                         ', '.join(f'{t} ({n}x)' for t, n in top))

        notes = self.progress.get('session_notes', [])
        relevant = [n for n in notes if n.get('lesson_number') == self.lesson_number]
        if relevant:
            parts.append(f"Last attempt note: {relevant[-1].get('note', '')}")

        return '\n'.join(parts) if parts else 'First session — no prior history.'

    # ── LLM prompt builders ──

    def build_teacher_system_prompt(self) -> str:
        """Build the full teacher-mode system prompt (replaces normal Alice prompt)."""
        section = self.current_section
        section_context = ''
        if section:
            section_context = (
                f'\n\nCURRENT SECTION: {section.number}. {section.title}\n'
                f'SECTION CONTENT:\n{section.truncated(2500)}'
            )

        return (
            f"{config.SYSTEM_PROMPT}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "TEACHER MODE ACTIVE\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"You are teaching Glenn: {self.lesson_title} (Lesson {self.lesson_number} of 31)\n"
            f"Progress: {self.progress_str()}\n"
            f"Student profile:\n{self.student_context()}\n"
            f"{section_context}\n\n"
            "TEACHING RULES:\n"
            "- Stay focused on the current lesson material\n"
            "- Keep your Alice personality (swear naturally, be warm and direct)\n"
            "- Present sections in your own words — don't just paste the content verbatim\n"
            "- If Glenn asks a question, answer it using your knowledge + the section content\n"
            "- When Glenn says 'next', 'ready', 'got it', etc. — acknowledge and move forward\n"
            "- If you're genuinely unsure about something, say so honestly\n"
            "- Be encouraging but don't sugarcoat — tell him when he's wrong\n"
            "- After each section, remind him: ask questions or say 'next' to continue\n"
        )

    def build_intro_prompt(self) -> str:
        """Prompt for Alice's opening teacher message."""
        weak = self.progress.get('weak_topics', {})
        completed = len(self.progress.get('lessons_completed', []))
        first_section = self.sections[0] if self.sections else None

        prompt = (
            f"You're starting lesson {self.lesson_number}: {self.lesson_title}. "
            f"Glenn has completed {completed} lessons so far. "
        )
        if weak:
            top = sorted(weak.items(), key=lambda x: x[1], reverse=True)[:2]
            prompt += f"He's struggled with: {', '.join(t for t, _ in top)}. "

        prompt += (
            f"The lesson has {self.total_sections} sections. "
            "Give a short, engaging intro (under 100 words):\n"
            "1. Say what tool you're teaching and why it matters for hacking\n"
            "2. Mention the number of sections\n"
            "3. Tell him to say 'next' to advance through sections, ask questions anytime\n"
            "4. Ask if he's ready\n"
            "Keep your Alice personality.\n\n"
        )
        if first_section:
            prompt += f"First section preview:\n{first_section.truncated(600)}"

        return prompt

    def build_section_prompt(self) -> str:
        """Prompt for presenting the current section."""
        section = self.current_section
        if not section:
            return "No more sections."

        is_last = self.is_last_section()
        ending = (
            "This is the last section. After presenting it, let him know it's the end of "
            "the lesson content and you're going to do a quick 3-question quiz."
            if is_last else
            "After presenting, remind Glenn he can ask questions or say 'next' to continue."
        )

        return (
            f"Present section {section.number}: '{section.title}' ({self.progress_str()}).\n\n"
            "Rules:\n"
            "- Summarize and explain the key points in your own words (no verbatim paste)\n"
            "- Highlight anything security-relevant or practical\n"
            "- If it's hands-on, give clear step instructions and tell him to come back when done\n"
            "- Keep it under 150 words\n"
            f"- {ending}\n\n"
            f"SECTION CONTENT:\n{section.truncated(2500)}"
        )

    def build_step_intro_prompt(self) -> str:
        """Prompt for entering step mode — announces the section and presents step 1."""
        section = self.current_section
        step = self.current_step
        total = len(self.step_blocks)
        if not section or not step:
            return ""

        return (
            f"We're starting '{section.title}' in {self.lesson_title}.\n"
            f"This section has {total} part(s). Walk Glenn through them one at a time.\n\n"
            "Tell him:\n"
            "- You'll go through this step by step\n"
            "- Say 'done' when he's finished each part and you'll move to the next\n"
            "- Ask questions anytime\n\n"
            f"Then present the first part: '{step.title}'\n\n"
            f"CONTENT:\n{step.truncated(2000)}\n\n"
            "Be specific and actionable. Give him exact commands to run or actions to take. "
            "End by telling him to say 'done' when finished."
        )

    def build_step_prompt(self) -> str:
        """Prompt for presenting the current step (after user finishes previous)."""
        section = self.current_section
        step = self.current_step
        if not section or not step:
            return ""

        is_last = self.is_last_step()
        progress = self.step_progress_str()

        if is_last:
            ending = (
                "This is the last part of this section. After presenting it, "
                "tell Glenn that's all the hands-on steps done, "
                "and he can say 'next' to continue to the next lesson section."
            )
        else:
            ending = "End by telling him to say 'done' when finished with this part."

        return (
            f"STEP MODE — {progress} of '{section.title}' ({self.progress_str()})\n\n"
            f"Present this part: '{step.title}'\n\n"
            f"CONTENT:\n{step.truncated(2000)}\n\n"
            "Be specific and actionable. Give exact steps/commands to run. "
            f"Keep it concise and clear. {ending}"
        )

    def build_step_question_prompt(self, question: str, web_results: str = None) -> str:
        """Prompt for answering a question while Glenn is working through a step."""
        section = self.current_section
        step = self.current_step
        ctx = ''
        if step:
            ctx = f"Current step: {step.title}\nStep content:\n{step.truncated(1200)}"
        elif section:
            ctx = f"Current section: {section.title}"

        base = (
            f"STEP MODE — {self.step_progress_str()} of '{section.title if section else ''}'\n"
            f"Glenn is working through a hands-on step and asked: \"{question}\"\n\n"
            f"{ctx}"
        )
        if web_results:
            base += f"\n\nWeb search results:\n{web_results}"

        base += (
            "\n\nAnswer his question clearly and practically. "
            "After answering, remind him to say 'done' when he's finished the step."
        )
        return base

    def build_question_prompt(self, question: str, web_results: str = None) -> str:
        """Prompt for answering a student question."""
        section = self.current_section
        ctx = ''
        if section:
            ctx = f"Current section: {section.title}\n{section.truncated(1200)}"

        base = (
            f"Glenn asked (during lesson {self.lesson_number}: {self.lesson_title}):\n"
            f'"{question}"\n\n'
            f"{ctx}"
        )
        if web_results:
            base += f"\n\nWeb search results to help answer:\n{web_results}"

        base += (
            "\n\nAnswer his question. "
            "Relate it back to the lesson where possible. "
            "Stay in teacher mode. "
            "After answering, tell him to ask more or say 'next' to continue."
        )
        return base

    def build_quiz_start_prompt(self) -> str:
        """Prompt to start the quiz (generates first question)."""
        # Find key takeaways section
        takeaways = next(
            (s for s in self.sections if 'takeaway' in s.title.lower() or 'key' in s.title.lower()),
            self.sections[-1] if self.sections else None
        )
        content = takeaways.truncated(1500) if takeaways else ''

        return (
            f"The lesson '{self.lesson_title}' is done. "
            "Time for a 3-question quiz. "
            "Start it now:\n"
            "1. Tell Glenn it's quiz time (briefly)\n"
            "2. Ask question 1 — make it practical and test real understanding\n\n"
            "Base questions on these key takeaways:\n"
            f"{content}\n\n"
            "Keep your Alice personality."
        )

    def build_quiz_followup_prompt(self, student_answer: str) -> str:
        """Prompt to evaluate quiz answer and ask the next question (or wrap up)."""
        questions_left = 3 - self.quiz_round

        if questions_left <= 0:
            return (
                f"Glenn just answered the final quiz question with: '{student_answer}'\n"
                f"Quiz score so far: {self.quiz_score}/3\n\n"
                "Evaluate his answer, give the final score, and wrap up the lesson:\n"
                "- Tell him what he got right and what to review if needed\n"
                "- Give encouragement\n"
                "- Tell him the next lesson and when it is (if you know)\n"
                "- Say something like 'that's a wrap' to end\n"
                "Keep it brief and warm."
            )

        # Still have questions left
        takeaways = next(
            (s for s in self.sections if 'takeaway' in s.title.lower() or 'key' in s.title.lower()),
            self.sections[-1] if self.sections else None
        )
        content = takeaways.truncated(1500) if takeaways else ''

        return (
            f"Glenn answered: '{student_answer}'\n"
            f"Quiz round: {self.quiz_round}/3 done. {questions_left} question(s) left.\n\n"
            "1. Evaluate his answer (correct/wrong/partial) in 1-2 sentences\n"
            f"2. Ask question {self.quiz_round + 1} — different from previous ones\n\n"
            f"Base on key takeaways:\n{content}\n\n"
            "Keep it snappy and in character."
        )

    # ── State management ──

    def is_advance_command(self, text: str) -> bool:
        """True if the user wants to move to the next section."""
        t = text.lower().strip()
        return any(phrase in t for phrase in ADVANCE_PHRASES)

    def has_uncertainty(self, response: str) -> bool:
        """True if the LLM response admits it doesn't know something."""
        r = response.lower()
        return any(marker in r for marker in UNCERTAINTY_MARKERS)

    def advance(self) -> bool:
        """Move to next section. Returns False if already at last section."""
        if not self.is_last_section():
            self.current_idx += 1
            return True
        return False

    def record_question(self, question: str, escalated: bool = False):
        """Log a student question for session summary."""
        self.questions_asked.append({
            'question': question,
            'section': self.current_section.title if self.current_section else 'unknown',
            'escalated': escalated,
        })

    def record_weak_topic(self, topic: str):
        """Note a topic the student struggled with."""
        if topic not in self.weak_topics:
            self.weak_topics.append(topic)

    def increment_quiz(self, correct: bool):
        """Advance quiz round and optionally increment score."""
        self.quiz_round += 1
        if correct:
            self.quiz_score += 1

    # ── Session wrap-up ──

    def save_results(self, note: str = ''):
        """Persist session results to lesson_progress.json."""
        progress = load_progress()

        # Mark completed
        completed_nums = {l['number'] for l in progress.get('lessons_completed', [])}
        if self.lesson_number not in completed_nums:
            progress.setdefault('lessons_completed', []).append({
                'number': self.lesson_number,
                'tool': self.lesson_tool,
                'completed_date': datetime.now().isoformat(),
                'quiz_score': self.quiz_score,
                'quiz_total': self.quiz_round,
            })

        # Update weak topics
        weak = progress.setdefault('weak_topics', {})
        for topic in self.weak_topics:
            weak[topic] = weak.get(topic, 0) + 1

        # Track if escalation was needed a lot (signals weak area)
        escalated_count = sum(1 for q in self.questions_asked if q.get('escalated'))
        if escalated_count >= 3:
            key = f"{self.lesson_tool} (web escalation)"
            weak[key] = weak.get(key, 0) + 1

        # Session note
        if note or self.questions_asked:
            auto_note = note or (
                f"Asked {len(self.questions_asked)} question(s). "
                f"Quiz: {self.quiz_score}/{self.quiz_round}."
                + (f" Struggled with: {', '.join(self.weak_topics)}." if self.weak_topics else '')
            )
            progress.setdefault('session_notes', []).append({
                'lesson_number': self.lesson_number,
                'tool': self.lesson_tool,
                'date': datetime.now().isoformat(),
                'note': auto_note,
            })

        progress['total_sessions'] = progress.get('total_sessions', 0) + 1
        progress['last_session'] = datetime.now().isoformat()
        progress['current_lesson'] = None

        save_progress(progress)
