"""Gemini-powered dataset generator for instructors."""

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


SIZE_LIMITS = {
    'small': 'about 10 rows per main table',
    'medium': 'about 50 rows per main table',
    'large': 'about 200 rows per main table',
}

DB_SYNTAX_HINTS = {
    'sqlite': (
        "Use SQLite syntax. Use INTEGER PRIMARY KEY AUTOINCREMENT for ids. "
        "TEXT for strings, REAL for decimals. No ENUM."
    ),
    'postgresql': (
        "Use PostgreSQL syntax. Use SERIAL or GENERATED for ids, VARCHAR(n) for strings, "
        "NUMERIC(p,s) for money, TIMESTAMP for datetimes. JSONB allowed."
    ),
    'mariadb': (
        "Use MariaDB/MySQL syntax. Use INT AUTO_INCREMENT PRIMARY KEY, VARCHAR(n), "
        "DECIMAL(p,s), DATETIME. Add FOREIGN KEY (col) REFERENCES tbl(col) lines."
    ),
    'mongodb': (
        "Use MongoDB shell syntax. Skip schema_sql (set it to empty string). "
        "Put db.collection.insertMany([...]) calls in seed_sql, separated by ; "
        "Use ISODate('YYYY-MM-DDTHH:mm:ss') for timestamps."
    ),
    'redis': (
        "Use Redis CLI command syntax. Skip schema_sql (set it to empty string). "
        "Put SET / HSET / LPUSH / ZADD / SADD commands in seed_sql, one per line."
    ),
}


@dataclass
class GenerationResult:
    success: bool
    name: str = ''
    description: str = ''
    schema_sql: str = ''
    seed_sql: str = ''
    error: str = ''


def _extract_json(text: str) -> Optional[dict]:
    """Extract the first JSON object from a Gemini response (it often wraps it in ```json fences)."""
    # Strip markdown code fences if present
    fenced = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    else:
        # Fallback: first {...} block
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end == -1 or end <= start:
            return None
        candidate = text[start:end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def generate_dataset(topic: str, size: str, database_type: str) -> GenerationResult:
    """Call Gemini to produce a dataset matching the given topic, size and DB type."""
    api_key = os.getenv('GEMINI_API_KEY', '').strip()
    if not api_key:
        return GenerationResult(success=False, error='GEMINI_API_KEY is not configured on the server.')

    if database_type not in DB_SYNTAX_HINTS:
        return GenerationResult(success=False, error=f'Unsupported database type: {database_type}')
    if size not in SIZE_LIMITS:
        return GenerationResult(success=False, error=f'Invalid size: {size}')

    try:
        import google.generativeai as genai
    except ImportError:
        return GenerationResult(success=False, error='google-generativeai package is not installed')

    genai.configure(api_key=api_key)

    prompt = f"""You are a database expert generating a teaching dataset.

Topic: {topic}
Database type: {database_type}
Size: {SIZE_LIMITS[size]}

Constraints:
- {DB_SYNTAX_HINTS[database_type]}
- Provide 3 to 5 related tables/collections that make joins/queries interesting.
- Use realistic but lighthearted data; avoid PII of real people.
- Foreign keys must reference existing rows (no broken relationships).
- All identifiers in lowercase_snake_case.
- For SQL dialects: schema_sql contains only DDL (CREATE TABLE...). seed_sql contains only DML (INSERT INTO...).
- Do not wrap statements in transactions.

Respond with ONLY a JSON object (no prose, no markdown fences) of this exact shape:
{{
  "name": "Short human-readable dataset name",
  "description": "One-sentence description of what's in this dataset",
  "schema_sql": "...",
  "seed_sql": "..."
}}
"""

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        text = (response.text or '').strip()
    except Exception as e:
        logger.exception('Gemini generation failed')
        return GenerationResult(success=False, error=f'Gemini API call failed: {e}')

    if not text:
        return GenerationResult(success=False, error='Gemini returned an empty response')

    parsed = _extract_json(text)
    if parsed is None:
        return GenerationResult(success=False, error='Gemini response was not valid JSON')

    return GenerationResult(
        success=True,
        name=str(parsed.get('name', '')).strip()[:255] or topic[:255],
        description=str(parsed.get('description', '')).strip(),
        schema_sql=str(parsed.get('schema_sql', '')).strip(),
        seed_sql=str(parsed.get('seed_sql', '')).strip(),
    )
