"""
Variable entity resolution using a RuleSpec engine package when available.

Resolves fully qualified variable references to their entity type
(person, tax_unit, household, family) by parsing the source .rac file.

Example:
    >>> get_entity("us:statute/26/32#eitc")
    "tax_unit"
    >>> get_entity("us-ca:statute/ca/rtc/17041#ca_agi")
    "tax_unit"
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

# Try to import a legacy RuleSpec engine API.
try:
    from policyengine.dependency_resolver import PackageRegistry, ModuleResolver
    from policyengine.dsl_parser import parse_file

    POLICYENGINE_AVAILABLE = True
except ImportError:
    POLICYENGINE_AVAILABLE = False


# Default workspace path (can be overridden)
DEFAULT_WORKSPACE = Path.home() / "PolicyEngine"

# Fallback entity mapping for common variables when a RuleSpec engine is not available.
FALLBACK_ENTITIES = {
    # Person-level
    "age": "person",
    "is_male": "person",
    "employment_income": "person",
    "is_snap_recipient": "person",
    "is_medicaid_enrolled": "person",
    "is_ssi_recipient": "person",
    # Tax unit level
    "agi": "tax_unit",
    "adjusted_gross_income": "tax_unit",
    "filing_status": "tax_unit",
    "eitc": "tax_unit",
    "earned_income_credit": "tax_unit",
    "ctc": "tax_unit",
    "child_tax_credit": "tax_unit",
    "tax_unit_count": "tax_unit",
    # Household level
    "household_size": "household",
    "tenure": "household",
    "state_fips": "household",
    "snap_allotment": "household",
}


class VariableNotFoundError(Exception):
    """Raised when a variable cannot be found in the referenced file."""

    pass


class InvalidVariableRefError(Exception):
    """Raised when a variable reference is malformed."""

    pass


def parse_variable_ref(variable_ref: str) -> tuple[str, str, str]:
    """
    Parse a fully qualified variable reference.

    Args:
        variable_ref: Reference like "us:statute/26/32#eitc"

    Returns:
        Tuple of (package, path, variable_name)

    Raises:
        InvalidVariableRefError: If reference is malformed
    """
    if ":" not in variable_ref or "#" not in variable_ref:
        raise InvalidVariableRefError(
            f"Invalid variable reference: {variable_ref}. "
            "Expected format: 'package:path#variable' (e.g., 'us:statute/26/32#eitc')"
        )

    package, rest = variable_ref.split(":", 1)

    if "#" not in rest:
        raise InvalidVariableRefError(
            f"Invalid variable reference: {variable_ref}. "
            "Missing '#' separator between path and variable name."
        )

    path, var_name = rest.rsplit("#", 1)

    return package, path, var_name


@lru_cache(maxsize=256)
def get_entity(
    variable_ref: str,
    workspace: Optional[Path] = None,
) -> str:
    """
    Get the entity type for a fully qualified variable reference.

    Parses the source .rac file to extract the variable's entity attribute.
    Results are cached for performance.

    Args:
        variable_ref: Fully qualified reference like "us:statute/26/32#eitc"
        workspace: Optional workspace path (defaults to ~/PolicyEngine)

    Returns:
        Entity type: "person", "tax_unit", "household", or "family"

    Raises:
        VariableNotFoundError: If variable not found in the .rac file
        InvalidVariableRefError: If reference is malformed

    Example:
        >>> get_entity("us:statute/26/32#eitc")
        "tax_unit"
    """
    package, path, var_name = parse_variable_ref(variable_ref)

    # Try the RuleSpec engine first.
    if POLICYENGINE_AVAILABLE:
        try:
            return _get_entity_from_rac(package, path, var_name, workspace)
        except Exception:
            # Fall through to fallback
            pass

    # Fallback to static mapping
    if var_name in FALLBACK_ENTITIES:
        return FALLBACK_ENTITIES[var_name]

    # Default to person level (most common)
    return "person"


def _get_entity_from_rac(
    package: str,
    path: str,
    var_name: str,
    workspace: Optional[Path] = None,
) -> str:
    """
    Get entity by parsing the actual .rac file.

    Uses the legacy RuleSpec engine's PackageRegistry to resolve paths.
    """
    if workspace is None:
        workspace = DEFAULT_WORKSPACE

    # Map short package name to repo name
    # us → policyengine-us, us-ca → policyengine-us-ca, uk → policyengine-uk
    repo_name = f"policyengine-{package}"

    # Get package registry
    registry = PackageRegistry.from_workspace(workspace)

    try:
        root = registry.get_root(repo_name)
    except Exception as e:
        raise VariableNotFoundError(
            f"Package '{repo_name}' not found in workspace {workspace}: {e}"
        )

    # Resolve file path
    resolver = ModuleResolver(root)
    try:
        rac_path = resolver.resolve(path)
    except Exception as e:
        raise VariableNotFoundError(
            f"Cannot resolve path '{path}' in package '{repo_name}': {e}"
        )

    # Parse the .rac file
    module = parse_file(str(rac_path))

    # Find the variable
    for var in module.variables:
        if var.name == var_name:
            # Entity is stored as an enum or string
            entity = var.entity
            if hasattr(entity, "value"):
                return entity.value.lower()
            return str(entity).lower()

    raise VariableNotFoundError(f"Variable '{var_name}' not found in {rac_path}")


def get_entity_for_constraint_var(var_name: str) -> str:
    """
    Get entity for a constraint variable (not a full reference).

    Used when processing stratum constraints like (age, >=, 65).
    Falls back to static mapping.

    Args:
        var_name: Simple variable name like "age" or "state_fips"

    Returns:
        Entity type (defaults to "person" if unknown)
    """
    return FALLBACK_ENTITIES.get(var_name, "person")


def infer_target_level(constraints: list[tuple[str, str, str]]) -> str:
    """
    Infer the most granular level needed based on constraint variables.

    If any constraint uses a person-level variable, the target needs
    person-level filtering before aggregation to household.

    Args:
        constraints: List of (variable, operator, value) tuples

    Returns:
        Most granular level: "person", "tax_unit", or "household"
    """
    levels = []
    for var, _, _ in constraints:
        entity = get_entity_for_constraint_var(var)
        levels.append(entity)

    # Return most granular level
    if "person" in levels:
        return "person"
    if "tax_unit" in levels:
        return "tax_unit"
    return "household"
