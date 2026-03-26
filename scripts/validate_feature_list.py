#!/usr/bin/env python3
"""
ADDS Feature List Validator

Validates feature_list.md against JSON Schema.
Usage:
    python scripts/validate_feature_list.py --project-dir .
    python scripts/validate_feature_list.py --file .ai/feature_list.md
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


def parse_feature_list(content: str) -> dict:
    """
    Parse feature_list.md markdown into structured data.
    """
    features = []
    current_feature = None
    current_section = None

    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]

        # Feature header: ## F001: Title
        feature_match = re.match(r'^## (F\d{3}):\s*(.+)$', line)
        if feature_match:
            if current_feature:
                features.append(current_feature)
            current_feature = {
                'id': feature_match.group(1),
                'title': feature_match.group(2).strip(),
                'dependencies': [],
                'steps': [],
                'test_cases': [],
                'acceptance_criteria': [],
                'security_checks': []
            }
            current_section = None
            i += 1
            continue

        if not current_feature:
            i += 1
            continue

        # Metadata: - **Category**: core
        meta_match = re.match(r'^-\s*\*\*(\w+)\*\*:\s*(.+)$', line)
        if meta_match:
            key = meta_match.group(1).lower()
            value = meta_match.group(2).strip()

            if key == 'category':
                current_feature['category'] = value
            elif key == 'priority':
                current_feature['priority'] = value
            elif key == 'status':
                current_feature['status'] = value
            elif key == 'dependencies':
                if value and value != '-':
                    deps = [d.strip() for d in value.split(',')]
                    current_feature['dependencies'] = deps
            elif key == 'complexity':
                current_feature['complexity'] = value
            i += 1
            continue

        # Section headers
        if line.startswith('### Steps'):
            current_section = 'steps'
            i += 1
            continue
        elif line.startswith('### Test Cases'):
            current_section = 'test_cases'
            i += 1
            continue
        elif line.startswith('### Acceptance Criteria'):
            current_section = 'acceptance_criteria'
            i += 1
            continue
        elif line.startswith('### Security Checks'):
            current_section = 'security_checks'
            i += 1
            continue

        # Parse section content
        if current_section == 'steps':
            step_match = re.match(r'^\d+\.\s*(.+)$', line)
            if step_match:
                current_feature['steps'].append(step_match.group(1).strip())

        elif current_section == 'test_cases':
            # Table row: | T001-01 | desc | type | status |
            test_match = re.match(r'^\|\s*(T\d{3}-\d{2})\s*\|\s*([^|]+)\|\s*(\w+)\s*\|\s*(\w+)?\s*\|', line)
            if test_match and test_match.group(1) != 'ID':
                current_feature['test_cases'].append({
                    'id': test_match.group(1).strip(),
                    'description': test_match.group(2).strip(),
                    'type': test_match.group(3).strip(),
                    'status': test_match.group(4).strip() if test_match.group(4) else 'pending'
                })

        elif current_section == 'acceptance_criteria':
            # Checkbox: - [ ] criterion
            criteria_match = re.match(r'^-\s*\[\s*([ x])\s*\]\s*(.+)$', line)
            if criteria_match:
                current_feature['acceptance_criteria'].append(criteria_match.group(2).strip())

        elif current_section == 'security_checks':
            # List item: - check description
            if line.startswith('- ') and not line.startswith('- **'):
                check = line[2:].strip()
                if check and check != '(none)':
                    current_feature['security_checks'].append(check)

        i += 1

    # Don't forget the last feature
    if current_feature:
        features.append(current_feature)

    return {'features': features}


def validate_against_schema(data: dict, schema_path: Path) -> list:
    """
    Validate data against JSON Schema.
    Returns list of validation errors.
    """
    with open(schema_path) as f:
        schema = json.load(f)

    errors = []

    # Check required fields at root
    if 'features' not in data:
        errors.append("Missing required field: features")
        return errors

    if not isinstance(data['features'], list):
        errors.append("Field 'features' must be an array")
        return errors

    # Validate each feature
    for idx, feature in enumerate(data['features']):
        prefix = f"Feature[{idx}]"

        if not isinstance(feature, dict):
            errors.append(f"{prefix}: Must be an object")
            continue

        # Required fields
        required = ['id', 'title', 'category', 'priority', 'status']
        for field in required:
            if field not in feature:
                errors.append(f"{prefix}: Missing required field '{field}'")

        # Validate id format
        if 'id' in feature:
            if not re.match(r'^F\d{3}$', feature['id']):
                errors.append(f"{prefix}: Invalid id format '{feature['id']}', expected F###")

        # Validate category
        if 'category' in feature:
            valid_categories = ['core', 'feature', 'fix', 'refactor', 'chore', 'test', 'docs']
            if feature['category'] not in valid_categories:
                errors.append(f"{prefix}: Invalid category '{feature['category']}'")

        # Validate priority
        if 'priority' in feature:
            valid_priorities = ['high', 'medium', 'low']
            if feature['priority'] not in valid_priorities:
                errors.append(f"{prefix}: Invalid priority '{feature['priority']}'")

        # Validate status
        if 'status' in feature:
            valid_statuses = ['pending', 'in_progress', 'testing', 'completed', 'blocked', 'regression']
            if feature['status'] not in valid_statuses:
                errors.append(f"{prefix}: Invalid status '{feature['status']}'")

        # Validate dependencies
        if 'dependencies' in feature:
            for dep in feature['dependencies']:
                if not re.match(r'^F\d{3}$', dep):
                    errors.append(f"{prefix}: Invalid dependency format '{dep}'")

        # Validate test cases
        if 'test_cases' in feature:
            for tc_idx, tc in enumerate(feature['test_cases']):
                tc_prefix = f"{prefix}.test_cases[{tc_idx}]"
                if 'id' in tc and not re.match(r'^T\d{3}-\d{2}$', tc['id']):
                    errors.append(f"{tc_prefix}: Invalid test id format '{tc['id']}'")
                if 'type' in tc:
                    valid_types = ['unit', 'integration', 'e2e']
                    if tc['type'] not in valid_types:
                        errors.append(f"{tc_prefix}: Invalid test type '{tc['type']}'")

    return errors


def main():
    parser = argparse.ArgumentParser(description='Validate ADDS feature_list.md')
    parser.add_argument('--project-dir', type=str, help='Project directory containing .ai/feature_list.md')
    parser.add_argument('--file', type=str, help='Direct path to feature_list.md')
    parser.add_argument('--schema', type=str, help='Path to JSON schema (optional)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable debug output')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress info output')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else (logging.WARNING if args.quiet else logging.INFO),
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )

    # Determine feature_list.md path
    if args.file:
        feature_file = Path(args.file)
    elif args.project_dir:
        feature_file = Path(args.project_dir) / '.ai' / 'feature_list.md'
    else:
        feature_file = Path('.ai') / 'feature_list.md'

    if not feature_file.exists():
        logger.error(f"Feature list not found: {feature_file}")
        sys.exit(1)

    # Determine schema path
    if args.schema:
        schema_path = Path(args.schema)
    else:
        # Look for schema: first in project's schemas/ directory, then alongside script
        candidates = [
            Path("schemas") / "feature_list.schema.json",
            Path(__file__).parent.parent / "schemas" / "feature_list.schema.json",
        ]
        schema_path = None
        for candidate in candidates:
            if candidate.exists():
                schema_path = candidate
                break
        if schema_path is None:
            schema_path = candidates[0]  # report the expected default path

    if not schema_path.exists():
        logger.error(f"Schema not found: {schema_path}")
        sys.exit(1)

    # Parse and validate
    logger.info(f"Validating: {feature_file}")
    logger.info(f"Schema: {schema_path}")
    logger.info("")

    with open(feature_file, 'r', encoding='utf-8') as f:
        content = f.read()

    data = parse_feature_list(content)
    errors = validate_against_schema(data, schema_path)

    if errors:
        logger.error(f"Validation failed with {len(errors)} error(s):")
        for error in errors:
            logger.error(f"   - {error}")
        sys.exit(1)
    else:
        logger.info(f"Validation passed!")
        logger.info(f"   Found {len(data['features'])} feature(s)")
        for f in data['features']:
            logger.info(f"   - {f['id']}: {f['title']} [{f['status']}]")
        sys.exit(0)


if __name__ == '__main__':
    main()
