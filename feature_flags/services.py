"""
Feature flag service functions for checking feature flag states and retrieving flags.
"""

import hashlib

from .models import FeatureFlag


def is_feature_enabled(key, organization=None, user=None):
    """
    Check if a feature flag is enabled for a given organization and/or user.

    Priority order:
    1. Organization-specific override (if organization is provided)
    2. Global flag (organization=None)
    3. Rules evaluation (percentage rollout, user whitelist, etc.)

    Args:
        key: Feature flag key identifier (e.g., 'new_dashboard')
        organization: Optional Organization instance
        user: Optional User instance for rule evaluation

    Returns:
        bool: True if the feature is enabled, False otherwise
    """
    # Check for organization-specific override first
    if organization:
        org_flag = FeatureFlag.objects.filter(
            key=key, organization=organization
        ).first()

        if org_flag:
            # If org flag exists, evaluate it (including rules)
            return _evaluate_flag(org_flag, user)

    # Check for global flag
    global_flag = FeatureFlag.objects.filter(key=key, organization__isnull=True).first()

    if global_flag:
        return _evaluate_flag(global_flag, user)

    # Step 3: If no flag exists, return False (feature disabled by default)
    return False


def _evaluate_flag(flag, user=None):
    """
    Evaluate a feature flag, considering its enabled state and rules.

    Priority:
    1. User whitelist (if user is whitelisted, always enabled)
    2. Base enabled state
    3. Percentage rollout (if enabled and rollout is configured)

    Args:
        flag: FeatureFlag instance
        user: Optional User instance for rule evaluation

    Returns:
        bool: True if the feature should be enabled, False otherwise
    """
    # If no rules are defined, return the enabled state
    if not flag.rules or not isinstance(flag.rules, dict):
        return flag.enabled

    rules = flag.rules

    # Step 1: Check for user whitelist first (whitelist overrides everything)
    if "whitelist" in rules and user:
        whitelist = rules.get("whitelist", [])
        if isinstance(whitelist, list) and user.id in whitelist:
            return True

    # Step 2: If flag is disabled, return False (unless whitelisted above)
    if not flag.enabled:
        return False

    # Step 3: Check for percentage rollout (only if flag is enabled)
    if "rollout_percentage" in rules:
        rollout_percentage = rules.get("rollout_percentage", 0)

        # Clamp rollout percentage to 0-100
        rollout_percentage = max(0, min(100, rollout_percentage))

        # If user is provided, use deterministic hashing for consistent rollout
        if user:
            # Create a deterministic hash based on flag key and user id
            hash_input = f"{flag.key}:{user.id}"
            hash_value = int(
                hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest(), 16
            )
            # Get a value between 0-99
            user_hash = hash_value % 100

            return user_hash < rollout_percentage
        # If no user provided, can't evaluate rollout, return False
        return False

    # If flag is enabled and no matching rules, return True
    return flag.enabled


def get_all_flags(organization):
    """
    Get all feature flags for a given organization.

    Returns both organization-specific flags and global flags,
    with organization-specific flags taking precedence for the same key.

    Args:
        organization: Organization instance

    Returns:
        dict: Dictionary mapping flag keys to their enabled state and metadata
              Format: {
                  'flag_key': {
                      'enabled': bool,
                      'name': str,
                      'description': str,
                      'is_global': bool,
                      'rules': dict
                  },
                  ...
              }
    """
    flags_dict = {}

    # Step 1: Get all global flags
    global_flags = FeatureFlag.objects.filter(organization__isnull=True)
    for flag in global_flags:
        flags_dict[flag.key] = {
            "enabled": flag.enabled,
            "name": flag.name,
            "description": flag.description,
            "is_global": True,
            "rules": flag.rules or {},
        }

    # Step 2: Override with organization-specific flags
    if organization:
        org_flags = FeatureFlag.objects.filter(organization=organization)
        for flag in org_flags:
            flags_dict[flag.key] = {
                "enabled": flag.enabled,
                "name": flag.name,
                "description": flag.description,
                "is_global": False,
                "rules": flag.rules or {},
            }

    return flags_dict
