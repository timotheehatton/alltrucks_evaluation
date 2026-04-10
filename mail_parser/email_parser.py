import re
from html.parser import HTMLParser


class _HTMLTextExtractor(HTMLParser):
    """Simple HTML to text converter."""

    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self._skip = True
        if tag in ('br', 'p', 'h1', 'h2', 'h3', 'h4', 'tr', 'div'):
            self._text.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

    def get_text(self):
        return ''.join(self._text).strip()


def _html_to_text(html):
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def _extract_email_address(text):
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    return match.group(0) if match else None


def parse_portal_email(webhook):
    """
    Parse emails from portal@alltrucks.com.
    Extracts the real user email and structured content from HTML body.

    Returns: (user_email, content, error)
    """
    html = webhook.body_html
    if not html:
        return None, None, 'No HTML body in portal email'

    text = _html_to_text(html)

    # Extract user email from the HTML table (look for Email row)
    email_match = re.search(
        r'Email\s*\n?\s*([\w.+-]+@[\w-]+\.[\w.-]+)',
        text
    )
    user_email = email_match.group(1) if email_match else None

    if not user_email:
        # Fallback: try to find any email that is not the platform email
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
        for e in emails:
            if e not in ('portal@alltrucks.com', 'hotlinetickets@alltrucks.com',
                         'truckhotline@de.bosch.com', 'info@alltrucks-amcat.com'):
                user_email = e
                break

    if not user_email:
        return None, None, 'Could not extract user email from portal email'

    return user_email, text, None


def parse_forum_email(webhook):
    """
    Parse emails from technic.forum@alltrucks.com.
    These are forum notification emails — skip them.

    Returns: (user_email, content, error)
    """
    return None, None, 'Forum notification emails are not processed'


def parse_inbound_email(webhook):
    """
    Main parsing function. Detects the email type based on sender
    and routes to the appropriate parser.

    Returns: (user_email, content, error)
        - user_email: the real end-user email to reply to
        - content: the meaningful text content to send to AI
        - error: error message if parsing failed (None on success)
    """
    sender_email = webhook.sender_email.lower()

    if sender_email == 'portal@alltrucks.com':
        return parse_portal_email(webhook)

    if sender_email == 'technic.forum@alltrucks.com':
        return parse_forum_email(webhook)

    # Unknown sender pattern — cannot parse
    return None, None, f'Unrecognized sender pattern: {sender_email}'
