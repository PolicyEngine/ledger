"""Validate that data files don't contain policy calculations.

Run this as a pre-commit hook or CI check to prevent policy rules
from leaking into data processing code.
"""

import ast
import sys
from pathlib import Path

# Variables that are POLICY (must be in .rac files, not data builders)
POLICY_VARIABLES = {
    # 26 USC § 62 - Adjusted Gross Income
    "adjusted_gross_income",
    "agi",
    # 26 USC § 63 - Taxable Income
    "taxable_income",
    "standard_deduction",
    "itemized_deduction",
    # 26 USC § 2(b) - Filing Status
    "is_head_of_household",
    # 26 USC § 32 - EITC
    "eitc",
    "earned_income_credit",
    # 26 USC § 24 - CTC
    "child_tax_credit",
    "ctc",
    "refundable_ctc",
    "non_refundable_ctc",
    # 26 USC § 1 - Income Tax
    "income_tax",
    "income_tax_before_credits",
    "tax_liability",
    # Self-employment tax
    "self_employment_tax",
    "se_tax",
    # Other policy variables
    "niit",
    "amt",
    "taxable_social_security",
}

# Files that should NOT contain policy calculations
DATA_FILES = [
    "tax_unit_builder.py",
    "cps_loader.py",
    "person_builder.py",
]


def check_file_for_policy_variables(filepath: Path) -> list[str]:
    """Check if a Python file assigns any policy variables."""
    violations = []

    with open(filepath) as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return [f"Could not parse {filepath}"]

    for node in ast.walk(tree):
        # Check df['variable'] = ... assignments
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Constant):
                var_name = node.slice.value
                if var_name in POLICY_VARIABLES:
                    violations.append(
                        f"{filepath}: assigns policy variable '{var_name}' "
                        f"(belongs in .rac file)"
                    )

    return violations


def main():
    """Check all data files for policy variable violations."""
    data_dir = Path(__file__).parent

    all_violations = []

    for filename in DATA_FILES:
        filepath = data_dir / filename
        if filepath.exists():
            violations = check_file_for_policy_variables(filepath)
            all_violations.extend(violations)

    if all_violations:
        print("POLICY/DATA SEPARATION VIOLATIONS:")
        print("=" * 60)
        for v in all_violations:
            print(f"  - {v}")
        print()
        print("These variables are POLICY RULES and must be in .rac files,")
        print("not in data processing code.")
        sys.exit(1)
    else:
        print("No policy/data separation violations found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
