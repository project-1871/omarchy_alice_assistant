"""Gmail tool — read and send emails via IMAP/SMTP with App Password."""

import imaplib
import smtplib
import email
import re
from email.mime.text import MIMEText
from email.header import decode_header
from tools.base import Tool
import config


def _decode_header(value: str) -> str:
    """Decode email header (handles encoded words like =?utf-8?...)."""
    parts = decode_header(value)
    result = []
    for raw, charset in parts:
        if isinstance(raw, bytes):
            result.append(raw.decode(charset or 'utf-8', errors='replace'))
        else:
            result.append(raw)
    return ''.join(result)


class GmailTool(Tool):
    name = "gmail"
    description = "Read and send Gmail emails"
    triggers = [
        "email", "emails", "gmail", "inbox", "new email", "new emails",
        "unread", "unread emails", "any emails", "check email", "check my email",
        "read my email", "read my emails", "do i have email", "send email",
        "send an email", "email to", "write an email", "reply to",
        "emails from", "message from",
    ]

    # ── IMAP helpers ─────────────────────────────────────────────────

    def _connect_imap(self):
        mail = imaplib.IMAP4_SSL(config.GMAIL_IMAP)
        mail.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASS)
        return mail

    def _get_unread(self) -> list[dict]:
        """Fetch unread emails. Returns list of {from, subject, snippet}."""
        mail = self._connect_imap()
        mail.select('INBOX')
        _, data = mail.search(None, 'UNSEEN')
        ids = data[0].split()
        results = []
        for uid in ids[-config.GMAIL_MAX_READ:]:   # most recent N
            _, msg_data = mail.fetch(uid, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            sender  = _decode_header(msg.get('From', ''))
            subject = _decode_header(msg.get('Subject', '(no subject)'))
            snippet = self._get_body_snippet(msg)
            results.append({'from': sender, 'subject': subject, 'snippet': snippet})
        mail.logout()
        return results

    def _get_body_snippet(self, msg, max_chars=120) -> str:
        """Extract clean plain text snippet from email body."""
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='replace')
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode('utf-8', errors='replace')
        # Strip URLs, markdown links, HTML entities, tracking junk, zero-width chars
        body = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', body)   # [text](url) → text
        body = re.sub(r'https?://\S+', '', body)
        body = re.sub(r'&[a-z]+;', ' ', body)                  # &nbsp; etc
        body = re.sub(r'[\u200b-\u200f\u00ad\u200c\u2028\u2029]', '', body)
        body = re.sub(r'[*_~`]{1,3}', '', body)                # markdown emphasis
        body = re.sub(r'\s+', ' ', body).strip()
        # Keep only lines with real words
        lines = [l.strip() for l in re.split(r'[.\n]', body) if len(l.strip()) > 12]
        body = '. '.join(lines[:2])
        return body[:max_chars] + '...' if len(body) > max_chars else body

    def _get_recent(self, n: int = 5) -> list[dict]:
        """Fetch most recent N emails (read or unread)."""
        mail = self._connect_imap()
        mail.select('INBOX')
        _, data = mail.search(None, 'ALL')
        ids = data[0].split()
        results = []
        for uid in ids[-n:]:
            _, msg_data = mail.fetch(uid, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            sender  = _decode_header(msg.get('From', ''))
            subject = _decode_header(msg.get('Subject', '(no subject)'))
            results.append({'from': sender, 'subject': subject})
        mail.logout()
        return list(reversed(results))

    def _search_from(self, sender_query: str) -> list[dict]:
        """Search inbox for emails from a specific sender."""
        mail = self._connect_imap()
        mail.select('INBOX')
        _, data = mail.search(None, f'FROM "{sender_query}"')
        ids = data[0].split()
        results = []
        for uid in ids[-config.GMAIL_MAX_READ:]:
            _, msg_data = mail.fetch(uid, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            sender  = _decode_header(msg.get('From', ''))
            subject = _decode_header(msg.get('Subject', '(no subject)'))
            results.append({'from': sender, 'subject': subject})
        mail.logout()
        return list(reversed(results))

    # ── SMTP helpers ─────────────────────────────────────────────────

    def _send(self, to: str, subject: str, body: str) -> bool:
        """Send an email. Returns True on success."""
        msg = MIMEText(body, 'plain')
        msg['From']    = config.GMAIL_ADDRESS
        msg['To']      = to
        msg['Subject'] = subject
        with smtplib.SMTP(config.GMAIL_SMTP, config.GMAIL_SMTP_PORT) as server:
            server.starttls()
            server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASS)
            server.sendmail(config.GMAIL_ADDRESS, to, msg.as_string())
        return True

    # ── Parse send intent ────────────────────────────────────────────

    def _parse_send(self, query: str):
        """
        Try to extract (to, subject, body) from query like:
        'send email to bob@example.com saying hello'
        'email john saying subject hello body how are you'
        Returns (to, subject, body) or None if can't parse.
        """
        q = query.lower()
        # Extract recipient
        to_match = re.search(r'to ([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]+)', query, re.I)
        if not to_match:
            # Try name-only e.g. "email myself" → own address
            if 'myself' in q or 'me' in q:
                to = config.GMAIL_ADDRESS
            else:
                return None
        else:
            to = to_match.group(1)

        # Extract body after "saying" or "that"
        body_match = re.search(r'(?:saying|that says?|body)\s+(.+)', query, re.I)
        body = body_match.group(1).strip() if body_match else ''

        # Extract subject after "subject"
        subj_match = re.search(r'subject\s+(.+?)(?:\s+body\s+|\s+saying\s+|$)', query, re.I)
        subject = subj_match.group(1).strip() if subj_match else 'Message from Alice'

        return to, subject, body

    # ── Execute ──────────────────────────────────────────────────────

    def execute(self, query: str, **kwargs) -> str:
        q = query.lower()

        # SEND
        if any(w in q for w in ['send', 'write an email', 'email to', 'email myself']):
            parsed = self._parse_send(query)
            if not parsed:
                return "I need a recipient. Try: 'send email to someone@gmail.com saying hello'."
            to, subject, body = parsed
            if not body:
                return f"What do you want to say in the email to {to}?"
            try:
                self._send(to, subject, body)
                return f"Email sent to {to}."
            except Exception as e:
                return f"Failed to send email: {e}"

        # SEARCH FROM
        if 'from' in q or 'emails from' in q:
            from_match = re.search(r'from\s+(\S+)', query, re.I)
            if from_match:
                sender = from_match.group(1)
                try:
                    emails = self._search_from(sender)
                    if not emails:
                        return f"No emails found from {sender}."
                    lines = [f"{i+1}. From {e['from']} — {e['subject']}" for i, e in enumerate(emails)]
                    return f"Emails from {sender}: " + '. '.join(lines)
                except Exception as e:
                    return f"Couldn't search emails: {e}"

        # UNREAD / NEW
        if any(w in q for w in ['unread', 'new email', 'new emails', 'any email', 'check email',
                                  'do i have', 'any new']):
            try:
                emails = self._get_unread()
                if not emails:
                    return "No unread emails. Inbox is clean."
                count = len(emails)
                lines = []
                for e in emails:
                    lines.append(f"From {e['from']} — {e['subject']}")
                    if e['snippet']:
                        lines[-1] += f". {e['snippet']}"
                return f"You have {count} unread email{'s' if count > 1 else ''}. " + '. '.join(lines)
            except Exception as e:
                return f"Couldn't check emails: {e}"

        # READ RECENT (default)
        try:
            emails = self._get_recent(5)
            if not emails:
                return "Your inbox is empty."
            lines = [f"{i+1}. From {e['from']} — {e['subject']}" for i, e in enumerate(emails)]
            return "Here are your latest emails: " + '. '.join(lines)
        except Exception as e:
            return f"Couldn't read emails: {e}"
