"""
llm_parser.py
Parses any integration requirement into canonical JSON via Groq (free LLM API).
All template knowledge, anti-hallucination rules, and classification logic
are embedded in the system prompt — sent with every request.
"""

import json
import re
import os
from groq import Groq

MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-70b-versatile")

# ════════════════════════════════════════
#  SYSTEM PROMPT — This IS the knowledge
# ════════════════════════════════════════
SYSTEM_PROMPT = """You are a senior integration architect. Your ONLY job is to parse an integration requirement into a structured JSON object.

CRITICAL RULES — VIOLATIONS WILL CAUSE REJECTION:

1. NEVER invent information not stated or safely derivable from the requirement.
2. Every field MUST have a "tag" indicating confidence:
   - EXPLICIT = directly stated in the requirement
   - DERIVED = safely and logically inferred from explicit info
   - STANDARD_DEFAULT = an approved organizational default (ONLY the approved list below)
   - ASSUMPTION = reasonable assumption needing confirmation — MUST be flagged
   - TBD = information not provided and cannot be inferred
   - HUMAN_REQUIRED = must be filled by a human (author, reviewer, contacts)

3. If authentication is not mentioned → TBD. Do NOT invent OAuth, API keys, etc.
4. If database tables are not mentioned → TBD. Do NOT invent table names.
5. If field mappings are not provided → TBD. Do NOT invent field names.
6. If frequency/schedule is not mentioned → TBD. Do NOT assume daily/hourly.
7. If API endpoints are not mentioned → TBD. Do NOT invent URLs.
8. If OpCo, contacts, reviewer are not mentioned → TBD or HUMAN_REQUIRED.

WORK TYPE CLASSIFICATION (deterministic — use these rules exactly):
- Source=File AND Target=Database → T1 (File to Database)
- Source=API AND Target=Database → T2 (API to Database)
- Source=Database AND Target=Database → T3 (Database to Database)
- Source=Database AND Target=File → T4 (Database to File)
- Source=Database AND Target=API → T5 (Database to API)
- If source/target types are unclear → TBD

APPROVED STANDARD DEFAULTS (ONLY these — nothing else):
- Middleware: Dell Boomi
- Encryption: TLS 1.2 or above for data in transit
- Logging: Standard Boomi logging framework
- Error handling: Standard Boomi error handling framework
- Retry: Yes
- Version: 1.0

Respond with ONLY valid JSON. No markdown backticks. No explanation before or after. Just the raw JSON object."""


SCHEMA_PROMPT = """Parse the following integration requirement into this EXACT JSON structure.

{
  "project": {
    "name": {"value": "<descriptive name from entities+source+target>", "tag": "DERIVED", "note": "<why>"},
    "opco": {"value": "TBD", "tag": "TBD", "note": null},
    "businessFunction": {"value": "<or TBD>", "tag": "<tag>", "note": null},
    "businessContacts": {"value": "TBD", "tag": "HUMAN_REQUIRED", "note": null},
    "classification": {"value": "New Project", "tag": "ASSUMPTION", "note": "Assumed new unless stated"},
    "version": {"value": "1.0", "tag": "STANDARD_DEFAULT", "note": null},
    "author": {"value": "TBD", "tag": "HUMAN_REQUIRED", "note": null},
    "reviewer": {"value": "TBD", "tag": "HUMAN_REQUIRED", "note": null}
  },
  "requirement": {
    "statement": {"value": "<verbatim requirement text>", "tag": "EXPLICIT", "note": null},
    "businessObjective": {"value": "<1-2 sentence goal>", "tag": "DERIVED", "note": null}
  },
  "source": {
    "system": {"value": "<source system>", "tag": "<tag>", "note": null},
    "interfaceType": {"value": "<file|api|database>", "tag": "<tag>", "note": null},
    "protocol": {"value": "<SFTP|REST|SOAP|JDBC|FTP|TBD>", "tag": "<tag>", "note": null},
    "authentication": {"value": "<or TBD>", "tag": "<tag>", "note": null},
    "dataFormat": {"value": "<JSON|XML|CSV|Relational|TBD>", "tag": "<tag>", "note": null},
    "volume": {"value": "<or TBD>", "tag": "<tag>", "note": null},
    "frequency": {"value": "<or TBD>", "tag": "<tag>", "note": null}
  },
  "target": {
    "system": {"value": "<target system>", "tag": "<tag>", "note": null},
    "interfaceType": {"value": "<file|api|database>", "tag": "<tag>", "note": null},
    "protocol": {"value": "<or TBD>", "tag": "<tag>", "note": null},
    "authentication": {"value": "<or TBD>", "tag": "<tag>", "note": null},
    "dataFormat": {"value": "<or TBD>", "tag": "<tag>", "note": null},
    "targetTable": {"value": "<or TBD>", "tag": "<tag>", "note": null},
    "volume": {"value": "<or TBD>", "tag": "<tag>", "note": null}
  },
  "integration": {
    "workType": {"value": "<full label e.g. T1 - File to Database>", "tag": "DERIVED", "note": "<classification reasoning>"},
    "workTypeCode": {"value": "<T1|T2|T3|T4|T5|TBD>", "tag": "DERIVED", "note": null},
    "direction": {"value": "<Unidirectional|Bidirectional|TBD>", "tag": "<tag>", "note": null},
    "pattern": {"value": "<File-Based Batch Processing|API Batch Processing|Real-Time API|Event Driven|TBD>", "tag": "<tag>", "note": null},
    "middleware": {"value": "Dell Boomi", "tag": "STANDARD_DEFAULT", "note": "Default per TDD standard template"},
    "trigger": {"value": "<Scheduled|On-Demand|Event|TBD>", "tag": "<tag>", "note": null},
    "schedule": {"value": "<Daily|Hourly|Weekly|TBD>", "tag": "<tag>", "note": null},
    "sla": {"value": "TBD", "tag": "TBD", "note": null}
  },
  "entities": [
    {"value": "<business entity>", "tag": "EXPLICIT", "note": null}
  ],
  "mappings": {
    "status": {"value": "TBD", "tag": "TBD", "note": "No mapping provided"},
    "fields": []
  },
  "transformations": {"value": "TBD", "tag": "TBD", "note": null},
  "businessRules": [
    {"value": "<rule>", "tag": "<tag>", "note": null}
  ],
  "validationRules": {"value": "TBD", "tag": "TBD", "note": null},
  "errorHandling": {
    "strategy": {"value": "Standard error handling per Boomi framework", "tag": "STANDARD_DEFAULT", "note": null},
    "retryApplicable": {"value": "Yes", "tag": "STANDARD_DEFAULT", "note": null}
  },
  "security": {
    "sourceAuth": {"value": "<or TBD>", "tag": "<tag>", "note": null},
    "targetAuth": {"value": "<or TBD>", "tag": "<tag>", "note": null},
    "encryption": {"value": "TLS 1.2 or above for data in transit", "tag": "STANDARD_DEFAULT", "note": null}
  },
  "assumptions": [
    {"value": "<text>", "tag": "ASSUMPTION", "note": null}
  ],
  "dependencies": [
    {"value": "<text>", "tag": "<tag>", "note": null}
  ],
  "outOfScope": [
    {"value": "<text>", "tag": "<tag>", "note": null}
  ],
  "acceptanceCriteria": [
    {"value": "<criterion>", "tag": "<tag>", "note": null}
  ],
  "unresolvedItems": [
    "<string for each TBD item>"
  ]
}

REQUIREMENT:
"""


def extract_json(raw_text):
    """Extract and parse JSON from LLM response, handling common issues."""
    text = raw_text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    first = text.find('{')
    last = text.rfind('}')
    if first == -1 or last == -1 or last <= first:
        raise ValueError("No JSON object found in LLM response")

    json_str = text[first:last + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        fixed = json_str
        fixed = re.sub(r',\s*}', '}', fixed)
        fixed = re.sub(r',\s*\]', ']', fixed)
        fixed = re.sub(r'[\x00-\x1f]', ' ', fixed)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON: {e}\n\nFirst 500 chars:\n{raw_text[:500]}")


def validate_llm_output(parsed, requirement):
    """Anti-hallucination validation."""
    issues = []
    req_lower = requirement.lower()

    def v(field):
        if not field:
            return None
        if isinstance(field, str):
            return field
        if isinstance(field, dict) and 'value' in field:
            return str(field['value'])
        return None

    # Check EXPLICIT tags have basis in requirement
    def check_explicits(obj, path):
        if not isinstance(obj, dict):
            return
        if obj.get('tag') == 'EXPLICIT' and obj.get('value') and obj['value'] != 'TBD':
            words = [w for w in str(obj['value']).lower().split() if len(w) > 3]
            matches = sum(1 for w in words if w in req_lower)
            if words and matches == 0:
                issues.append(f"HALLUCINATION: '{path}' tagged EXPLICIT but not found in requirement: \"{obj['value']}\"")
        for key, val in obj.items():
            if key == 'note':
                continue
            if isinstance(val, dict):
                check_explicits(val, f"{path}.{key}")
            elif isinstance(val, list):
                for i, item in enumerate(val):
                    if isinstance(item, dict):
                        check_explicits(item, f"{path}.{key}[{i}]")

    check_explicits(parsed, 'root')

    # Check TBD-tagged fields don't have concrete values
    def check_tbds(obj, path):
        if not isinstance(obj, dict):
            return
        if obj.get('tag') == 'TBD' and obj.get('value') and obj['value'] != 'TBD' and not str(obj['value']).startswith('TBD'):
            issues.append(f"INCONSISTENCY: '{path}' tagged TBD but has value: \"{obj['value']}\"")
        for key, val in obj.items():
            if key == 'note':
                continue
            if isinstance(val, dict):
                check_tbds(val, f"{path}.{key}")
            elif isinstance(val, list):
                for i, item in enumerate(val):
                    if isinstance(item, dict):
                        check_tbds(item, f"{path}.{key}[{i}]")

    check_tbds(parsed, 'root')

    # Verify work type consistency
    src_type = v(parsed.get('source', {}).get('interfaceType'))
    tgt_type = v(parsed.get('target', {}).get('interfaceType'))
    wt_code = v(parsed.get('integration', {}).get('workTypeCode'))

    expected = {
        'T1': ('file', 'database'), 'T2': ('api', 'database'),
        'T3': ('database', 'database'), 'T4': ('database', 'file'),
        'T5': ('database', 'api'),
    }
    if wt_code and wt_code in expected:
        exp_src, exp_tgt = expected[wt_code]
        if src_type and src_type.lower() != exp_src:
            issues.append(f"WORK TYPE MISMATCH: {wt_code} expects source='{exp_src}' but got '{src_type}'")
        if tgt_type and tgt_type.lower() != exp_tgt:
            issues.append(f"WORK TYPE MISMATCH: {wt_code} expects target='{exp_tgt}' but got '{tgt_type}'")

    # Check STANDARD_DEFAULT values
    approved = {
        'dell boomi', 'tls 1.2 or above for data in transit',
        'standard error handling per boomi framework',
        'standard boomi logging framework', 'yes', '1.0',
    }

    def check_defaults(obj, path):
        if not isinstance(obj, dict):
            return
        if obj.get('tag') == 'STANDARD_DEFAULT' and obj.get('value'):
            if str(obj['value']).lower().strip() not in approved:
                issues.append(f"UNAPPROVED DEFAULT: '{path}' = \"{obj['value']}\" — changed to ASSUMPTION")
                obj['tag'] = 'ASSUMPTION'
        for key, val in obj.items():
            if key == 'note':
                continue
            if isinstance(val, dict):
                check_defaults(val, f"{path}.{key}")
            elif isinstance(val, list):
                for i, item in enumerate(val):
                    if isinstance(item, dict):
                        check_defaults(item, f"{path}.{key}[{i}]")

    check_defaults(parsed, 'root')

    has_critical = any(i.startswith('HALLUCINATION') or i.startswith('MISSING') for i in issues)
    return {
        'valid': not has_critical,
        'issues': issues,
        'data': parsed,
    }


def cross_validate(canonical):
    """Cross-document validation between BRD and TDD content."""
    issues = []
    warnings = []

    def v(field):
        if not field:
            return 'TBD'
        if isinstance(field, str):
            return field
        if isinstance(field, dict) and 'value' in field:
            return str(field['value'])
        return 'TBD'

    src = v(canonical.get('source', {}).get('system'))
    tgt = v(canonical.get('target', {}).get('system'))
    if src == 'TBD':
        issues.append('Source system is TBD')
    if tgt == 'TBD':
        issues.append('Target system is TBD')

    src_freq = v(canonical.get('source', {}).get('frequency'))
    int_sched = v(canonical.get('integration', {}).get('schedule'))
    if src_freq != 'TBD' and int_sched != 'TBD' and src_freq != int_sched:
        issues.append(f'Frequency mismatch: source="{src_freq}" vs schedule="{int_sched}"')

    pattern = v(canonical.get('integration', {}).get('pattern'))
    trigger = v(canonical.get('integration', {}).get('trigger'))
    if pattern and 'real-time' in pattern.lower() and trigger and 'scheduled' in trigger.lower():
        issues.append('Pattern is real-time but trigger is scheduled — incompatible')

    if not canonical.get('acceptanceCriteria'):
        warnings.append('No acceptance criteria defined')

    status = 'REVIEW_REQUIRED' if issues else 'PASS'
    return {'status': status, 'issues': issues, 'warnings': warnings}


def parse_requirement(requirement_text, api_key):
    """Main function: parse requirement via Groq LLM."""
    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": SCHEMA_PROMPT + requirement_text},
        ],
        temperature=0.1,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content
    parsed = extract_json(raw)

    # Anti-hallucination validation
    validation = validate_llm_output(parsed, requirement_text)
    canonical = validation['data']

    # Add date
    from datetime import datetime
    date_str = datetime.now().strftime("%b %d, %Y")
    if 'project' in canonical and 'date' not in canonical['project']:
        canonical['project']['date'] = {"value": date_str, "tag": "DERIVED", "note": None}

    # Cross-validation
    cross = cross_validate(canonical)

    return {
        'canonical': canonical,
        'validation': validation,
        'crossValidation': cross,
    }
