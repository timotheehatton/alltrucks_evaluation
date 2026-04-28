import re
from html.parser import HTMLParser

# Languages we ship localized email content for. Anything detected outside
# this set is collapsed to 'en' as the safe default.
SUPPORTED_LANGUAGES = {'en', 'fr', 'de', 'it', 'es', 'pl'}


def detect_language(text):
    """Return a 2-letter language code from `text` (one of SUPPORTED_LANGUAGES) or ''.

    Uses langdetect for short prose. Returns '' if the text is too short
    or detection fails — callers should fall back to a default.
    """
    if not text or len(text.strip()) < 20:
        return ''
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0  # deterministic across runs
        code = detect(text).lower()
    except Exception:
        return ''
    if code not in SUPPORTED_LANGUAGES:
        return 'en'
    return code


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


def _extract_table_value(text, label):
    """Extract value next to a label in the converted HTML text."""
    match = re.search(rf'{label}\s*\n\s*(.+)', text)
    if not match:
        return ''
    value = match.group(1).strip()
    # Don't return section headers as values
    if re.match(r'^\d+\s*-\s*', value):
        return ''
    return value


def parse_portal_email(webhook):
    """
    Parse emails from portal@alltrucks.com.
    Extracts user email, vehicle info, and issue from HTML body.

    Returns: (user_email, content, vehicle_data, issue, error)
    """
    html = webhook.body_html
    if not html:
        return None, None, None, None, 'No HTML body in portal email'

    text = _html_to_text(html)

    # Extract user email
    email_match = re.search(r'Email\s*\n?\s*([\w.+-]+@[\w-]+\.[\w.-]+)', text)
    user_email = email_match.group(1) if email_match else None

    if not user_email:
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
        for e in emails:
            if e not in ('portal@alltrucks.com', 'hotlinetickets@alltrucks.com',
                         'truckhotline@de.bosch.com', 'info@alltrucks-amcat.com'):
                user_email = e
                break

    if not user_email:
        return None, None, None, None, 'Could not extract user email from portal email'

    # Extract vehicle information
    vehicle_data = {
        'brand': _extract_table_value(text, 'Brand'),
        'model': _extract_table_value(text, 'Model'),
        'vin': _extract_table_value(text, 'VIN'),
        'year': _extract_table_value(text, 'Year'),
        'mileage': _extract_table_value(text, 'Mileage'),
        'axle_config': _extract_table_value(text, 'Axle configuration'),
    }

    # Extract the full problem section between "3 - The problem" and "4 - Request"
    problem_match = re.search(r'3 - The problem(.*?)(?:4 - Request|$)', text, re.DOTALL)
    issue = ''
    default_code = ''
    if problem_match:
        problem_block = problem_match.group(1)

        # Extract the issue description (between "Issue description..." and "Default code")
        desc_match = re.search(
            r'Issue description or support requested\s*\n+(.*?)(?:\n\s*Default code|\Z)',
            problem_block,
            re.DOTALL,
        )
        issue = desc_match.group(1).strip() if desc_match else ''

        # Extract default code if present
        code_match = re.search(r'Default code:\s*(.+)', problem_block)
        default_code = code_match.group(1).strip() if code_match else ''

    # Extract "4 - Request" checked items
    request_nature = _extract_request_nature(text)

    return user_email, text, vehicle_data, issue, default_code, request_nature, None


_CHECKED_MARKERS = ('☑', '☒', '✓', '✔', '[x]', '[X]')


def _extract_request_nature(text):
    """Return the labels of checked items in the '4 - Request' section."""
    request_match = re.search(r'4\s*-\s*Request[^\n]*\n(.*?)(?:\n\s*\d+\s*-\s*|\Z)', text, re.DOTALL)
    if not request_match:
        return []

    checked = []
    for line in request_match.group(1).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(m) for m in _CHECKED_MARKERS):
            label = stripped
            for m in _CHECKED_MARKERS:
                if label.startswith(m):
                    label = label[len(m):].strip()
                    break
            if label:
                checked.append(label)
    return checked


def parse_forum_email(webhook):
    """
    Parse emails from technic.forum@alltrucks.com.
    Extracts the forum post subject, author and message from body_text.

    Returns: (user_email, content, vehicle_data, issue, error)
    """
    text = webhook.body_text
    if not text:
        return None, None, None, None, 'No text body in forum email'

    block_match = re.search(
        r'_{5,}\s*\n(.*?)\n_{5,}',
        text,
        re.DOTALL,
    )

    if not block_match:
        return None, None, None, None, 'Could not extract forum post content'

    block = block_match.group(1).strip()

    subject_match = re.search(r'Sujet\s*:\s*(.+)', block)
    author_match = re.search(r'Auteur\s*:\s*(.+)', block)
    message_match = re.search(r'Message\s*:\s*\n(.*)', block, re.DOTALL)

    subject = subject_match.group(1).strip() if subject_match else ''
    author = author_match.group(1).strip() if author_match else ''
    message = message_match.group(1).strip() if message_match else ''

    if not message:
        return None, None, None, None, 'Could not extract message from forum post'

    content = f"Forum post by {author}\nSubject: {subject}\n\n{message}"
    issue = f"{subject}\n\n{message}"

    return None, content, None, issue, None


def parse_inbound_email(webhook):
    """
    Main parsing function. Detects the email type based on sender
    and routes to the appropriate parser. Saves parsed data on the webhook.

    Returns: (user_email, content, error)
    """
    from .models import InboundWebhook

    sender_email = webhook.sender_email.lower()

    if sender_email == 'portal@alltrucks.com':
        webhook.category = InboundWebhook.CATEGORY_HOTLINE
        user_email, content, vehicle_data, issue, default_code, request_nature, error = parse_portal_email(webhook)

        if error:
            webhook.save(update_fields=['category'])
            return None, None, error

        # Save vehicle info
        if vehicle_data:
            webhook.vehicle_brand = vehicle_data.get('brand', '')
            webhook.vehicle_model = vehicle_data.get('model', '')
            webhook.vehicle_vin = vehicle_data.get('vin', '')
            webhook.vehicle_year = vehicle_data.get('year', '')
            webhook.vehicle_mileage = vehicle_data.get('mileage', '')
            webhook.vehicle_axle_config = vehicle_data.get('axle_config', '')

        webhook.parsed_issue = issue or ''
        webhook.default_code = default_code or ''
        webhook.request_nature = request_nature or []
        webhook.language = detect_language(issue or '') or 'en'
        webhook.save(update_fields=[
            'category', 'vehicle_brand', 'vehicle_model', 'vehicle_vin',
            'vehicle_year', 'vehicle_mileage', 'vehicle_axle_config',
            'parsed_issue', 'default_code', 'request_nature', 'language',
        ])

        return user_email, content, None

    if sender_email == 'technic.forum@alltrucks.com':
        webhook.category = InboundWebhook.CATEGORY_FORUM
        user_email, content, vehicle_data, issue, error = parse_forum_email(webhook)

        if error:
            webhook.save(update_fields=['category'])
            return None, None, error

        webhook.parsed_issue = issue or ''
        webhook.language = detect_language(issue or '') or 'en'
        webhook.save(update_fields=['category', 'parsed_issue', 'language'])

        return user_email, content, None

    return None, None, f'Unrecognized sender pattern: {sender_email}'
