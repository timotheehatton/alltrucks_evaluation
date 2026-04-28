"""Convert the raw hotline CSV into a Markdown knowledge base for OpenAI file_search.

Steps:
- Read the raw CSV directly (Ticket ID / Created / Customer / Customer Number columns are simply ignored)
- Drop rows where Resolution Details is empty or too short (< 50 chars)
- Drop rows where the resolution is a trivial "document sent" boilerplate
- Normalize brand names (Mercedes-Benz, IVECO, MAN, ...)
- Emit one Markdown section per case with `## Case ...` heading; metadata is inlined
  as bullet lines so it's both human-readable and semantically searchable

Usage:
    python scripts/build_hotline_kb.py
"""
import csv
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_PATH = SCRIPT_DIR / 'alltrucks_hoteline_data.csv'
OUTPUT_PATH = SCRIPT_DIR / 'alltrucks_hotline_kb.md'

MIN_RESOLUTION_LEN = 50

# We mirror the production-side rule that documentation-only requests don't
# get an AI answer, so they shouldn't pollute the retrieval space either.
# Their resolutions are typically "Document envoyé" / "siehe Anhang" — short,
# generic, and produce embedding outliers that match unrelated queries.
EXCLUDED_REQUEST_TYPES = {
    'Technische Dokumentation',
}

# Patterns that indicate the case is administrative noise (not a real Q&A).
TRIVIAL_PATTERNS = [
    r'^\s*nicht zust[äa]ndig\.?\s*$',
    r'^\s*kein fall f[üu]r\s+',
    r'^\s*ok\.?\s*$',
    r'^\s*erledigt\.?\s*$',
    r'^\s*r[ée]solu\.?\s*$',
    r'^\s*risolto\.?\s*$',
]
TRIVIAL_REGEX = [re.compile(p, re.IGNORECASE) for p in TRIVIAL_PATTERNS]

# Normalize brand: lowercase + strip punctuation/spaces, then map to canonical
BRAND_CANONICAL = {
    'man': 'MAN',
    'mercedes': 'Mercedes-Benz',
    'mercedesbenz': 'Mercedes-Benz',
    'mercdesbenz': 'Mercedes-Benz',
    'iveco': 'Iveco',
    'renault': 'Renault',
    'rvi': 'Renault',
    'daf': 'DAF',
    'volvo': 'Volvo',
    'scania': 'Scania',
    'fiat': 'Fiat',
    'ford': 'Ford',
    'nissan': 'Nissan',
    'mitsubishi': 'Mitsubishi',
    'mitsubishifuso': 'Mitsubishi Fuso',
    'mitsubishifusotruckbusco': 'Mitsubishi Fuso',
    'vw': 'Volkswagen',
    'vwvolkswagen': 'Volkswagen',
    'volkswagen': 'Volkswagen',
    'peugeot': 'Peugeot',
    'citroen': 'Citroen',
    'opel': 'Opel',
    'isuzu': 'Isuzu',
    'setra': 'Setra',
    'irisbus': 'Irisbus',
    'bosch': 'Bosch',
    'wabco': 'Wabco',
    'knorr': 'Knorr-Bremse',
    'trailers': 'Trailer (generic)',
    'remorque': 'Trailer (generic)',
}


def normalize_brand(raw):
    if not raw or not raw.strip():
        return ''
    key = re.sub(r'[^a-z]', '', raw.lower())
    return BRAND_CANONICAL.get(key, raw.strip().title())


def is_trivial_resolution(text):
    return any(rx.match(text) for rx in TRIVIAL_REGEX)


def clean(value):
    return (value or '').strip()


def build_case_markdown(row, case_index):
    """Compose a Markdown section for one case."""
    brand = normalize_brand(row['Vehicle Manufacturer'])
    series = clean(row['Series'])
    engine_code = clean(row['Engine Code'])
    engine_capacity = clean(row['Engine Capacity'])
    engine_power = clean(row['Engine Power'])
    reg_date = clean(row['Registration Date'])
    vin = clean(row['VIN'])
    mileage = clean(row['Kilometrage'])
    axle = clean(row['Axle Configuration'])
    abs_cfg = clean(row['ABS Configuration'])
    installed = ' / '.join(filter(None, [
        clean(row['Installed System']),
        clean(row['Installed System_1']),
        clean(row['Installed System_2']),
        clean(row['Installed System_3']),
        clean(row['Installed System_4']),
    ]))
    system_desc = clean(row['System Description'])
    country = clean(row['Country '])
    request_type = clean(row['Type of Request '])

    subject = clean(row['Subject'])
    description = clean(row['Description'])
    resolution_summary = clean(row['Resolution Summary'])
    resolution_details = clean(row['Resolution Details'])

    # Heading: include the most discriminating identifiers
    heading_parts = []
    if brand:
        heading_parts.append(brand)
    if series:
        heading_parts.append(series)
    if subject:
        heading_parts.append(f'— {subject}')
    heading = ' '.join(heading_parts) if heading_parts else 'Untitled'
    heading = heading[:160]  # keep headings reasonable

    lines = [f'## Case {case_index}: {heading}', '']

    # Metadata block (inline so it remains searchable)
    if brand:
        lines.append(f'- **Manufacturer:** {brand}')
    if series:
        lines.append(f'- **Series:** {series}')
    engine_parts = [p for p in [engine_code, engine_capacity, engine_power] if p]
    if engine_parts:
        lines.append(f'- **Engine:** {", ".join(engine_parts)}')
    if reg_date:
        lines.append(f'- **Registration date:** {reg_date}')
    if vin:
        lines.append(f'- **VIN:** {vin}')
    if mileage:
        lines.append(f'- **Mileage:** {mileage}')
    if axle:
        lines.append(f'- **Axle configuration:** {axle}')
    if abs_cfg:
        lines.append(f'- **ABS configuration:** {abs_cfg}')
    if installed:
        lines.append(f'- **Installed system:** {installed}')
    if system_desc:
        lines.append(f'- **System:** {system_desc}')
    if country:
        lines.append(f'- **Country:** {country}')
    if request_type:
        lines.append(f'- **Request type:** {request_type}')

    lines.append('')
    lines.append('### Issue')
    if subject:
        lines.append(f'**Subject:** {subject}')
    if description:
        lines.append(description)

    lines.append('')
    lines.append('### Resolution')
    if resolution_summary:
        lines.append(f'**Summary:** {resolution_summary}')
    if resolution_details:
        lines.append(resolution_details)

    return '\n'.join(lines)


def main():
    with INPUT_PATH.open('r', encoding='utf-8-sig') as src:
        reader = csv.DictReader(src, delimiter=';')
        rows = list(reader)

    total = len(rows)
    written = dropped_short = dropped_trivial = dropped_doc = 0

    with OUTPUT_PATH.open('w', encoding='utf-8') as dst:
        dst.write('# Alltrucks Hotline Knowledge Base\n\n')
        dst.write(f'_{total} historical hotline cases — high-quality resolutions only._\n\n')
        dst.write('---\n\n')

        for row in rows:
            request_type = clean(row['Type of Request '])
            if request_type in EXCLUDED_REQUEST_TYPES:
                dropped_doc += 1
                continue
            resolution = clean(row['Resolution Details'])
            if len(resolution) < MIN_RESOLUTION_LEN:
                dropped_short += 1
                continue
            if is_trivial_resolution(resolution):
                dropped_trivial += 1
                continue

            written += 1
            dst.write(build_case_markdown(row, written))
            dst.write('\n\n---\n\n')

    print(f'Total rows:            {total}')
    print(f'Dropped (doc request): {dropped_doc}')
    print(f'Dropped (short):       {dropped_short}')
    print(f'Dropped (boilerplate): {dropped_trivial}')
    print(f'Written:               {written}')
    print(f'Output:                {OUTPUT_PATH}')


if __name__ == '__main__':
    main()