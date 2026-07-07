import pytest
from django.contrib.auth import get_user_model

from feature_flags.models import FeatureFlag
from feature_flags.services import get_all_flags, is_feature_enabled
from organizations.models import Membership, Organization

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    return User.objects.create_user(email="owner@acme.com", password="pass")


@pytest.fixture
def org(db, user):
    org = Organization.objects.create(name="Acme", owner=user)
    Membership.objects.create(user=user, organization=org, role="owner")
    return org


@pytest.fixture
def other_user(db):
    return User.objects.create_user(email="stranger@other.com", password="pass")


# is_feature_enabled — flag lookup priority


@pytest.mark.django_db
class TestIsFeatureEnabledLookup:
    def test_nonexistent_flag_returns_false(self, org, user):
        assert is_feature_enabled("no_such_flag", organization=org, user=user) is False

    def test_global_flag_enabled_no_org(self, db):
        FeatureFlag.objects.create(key="dark_mode", name="Dark Mode", enabled=True)
        assert is_feature_enabled("dark_mode") is True

    def test_global_flag_disabled_no_org(self, db):
        FeatureFlag.objects.create(key="dark_mode", name="Dark Mode", enabled=False)
        assert is_feature_enabled("dark_mode") is False

    def test_org_override_enabled_beats_disabled_global(self, org):
        FeatureFlag.objects.create(key="beta_ui", name="Beta UI", enabled=False)
        FeatureFlag.objects.create(
            key="beta_ui", name="Beta UI", enabled=True, organization=org
        )
        assert is_feature_enabled("beta_ui", organization=org) is True

    def test_org_override_disabled_beats_enabled_global(self, org):
        FeatureFlag.objects.create(key="beta_ui", name="Beta UI", enabled=True)
        FeatureFlag.objects.create(
            key="beta_ui", name="Beta UI", enabled=False, organization=org
        )
        assert is_feature_enabled("beta_ui", organization=org) is False

    def test_falls_back_to_global_when_no_org_flag(self, org):
        FeatureFlag.objects.create(key="reports", name="Reports", enabled=True)
        assert is_feature_enabled("reports", organization=org) is True

    def test_org_flag_not_visible_to_other_org(self, db, user, org):
        other_user = User.objects.create_user(email="b@b.com", password="pass")
        other_org = Organization.objects.create(name="Beta", owner=other_user)
        FeatureFlag.objects.create(
            key="exclusive", name="Exclusive", enabled=True, organization=org
        )
        # other_org has no flag for 'exclusive' and no global either
        assert is_feature_enabled("exclusive", organization=other_org) is False


# is_feature_enabled — rule evaluation


@pytest.mark.django_db
class TestIsFeatureEnabledRules:
    def test_whitelist_enables_for_listed_user(self, org, user):
        FeatureFlag.objects.create(
            key="vip",
            name="VIP",
            enabled=False,
            organization=org,
            rules={"whitelist": [user.id]},
        )
        assert is_feature_enabled("vip", organization=org, user=user) is True

    def test_whitelist_does_not_enable_for_unlisted_user(self, org, other_user):
        vip = User.objects.create_user(email="vip@x.com", password="pass")
        FeatureFlag.objects.create(
            key="vip",
            name="VIP",
            enabled=False,
            organization=org,
            rules={"whitelist": [vip.id]},
        )
        assert is_feature_enabled("vip", organization=org, user=other_user) is False

    def test_rollout_100_percent_always_true(self, org, user):
        FeatureFlag.objects.create(
            key="rollout",
            name="Rollout",
            enabled=True,
            organization=org,
            rules={"rollout_percentage": 100},
        )
        assert is_feature_enabled("rollout", organization=org, user=user) is True

    def test_rollout_0_percent_always_false(self, org, user):
        FeatureFlag.objects.create(
            key="rollout",
            name="Rollout",
            enabled=True,
            organization=org,
            rules={"rollout_percentage": 0},
        )
        assert is_feature_enabled("rollout", organization=org, user=user) is False

    def test_rollout_without_user_returns_false(self, org):
        FeatureFlag.objects.create(
            key="rollout",
            name="Rollout",
            enabled=True,
            organization=org,
            rules={"rollout_percentage": 100},
        )
        assert is_feature_enabled("rollout", organization=org, user=None) is False

    def test_rollout_is_deterministic_for_same_user(self, org, user):
        FeatureFlag.objects.create(
            key="rollout",
            name="Rollout",
            enabled=True,
            organization=org,
            rules={"rollout_percentage": 50},
        )
        results = {
            is_feature_enabled("rollout", organization=org, user=user)
            for _ in range(10)
        }
        assert len(results) == 1

    def test_flag_disabled_with_no_rules_returns_false(self, org):
        FeatureFlag.objects.create(
            key="off", name="Off", enabled=False, organization=org
        )
        assert is_feature_enabled("off", organization=org) is False

    def test_flag_enabled_with_no_rules_returns_true(self, org):
        FeatureFlag.objects.create(key="on", name="On", enabled=True, organization=org)
        assert is_feature_enabled("on", organization=org) is True


# get_all_flags


@pytest.mark.django_db
class TestGetAllFlags:
    def test_empty_when_no_flags(self, org):
        assert get_all_flags(org) == {}

    def test_returns_global_flags(self, org):
        FeatureFlag.objects.create(key="g", name="Global", enabled=True)
        flags = get_all_flags(org)
        assert "g" in flags
        assert flags["g"]["is_global"] is True
        assert flags["g"]["enabled"] is True

    def test_org_flag_overrides_global(self, org):
        FeatureFlag.objects.create(key="feat", name="Feature", enabled=False)
        FeatureFlag.objects.create(
            key="feat", name="Feature Override", enabled=True, organization=org
        )
        flags = get_all_flags(org)
        assert flags["feat"]["enabled"] is True
        assert flags["feat"]["is_global"] is False

    def test_returns_both_org_and_global_flags(self, org):
        FeatureFlag.objects.create(key="global_feat", name="Global", enabled=True)
        FeatureFlag.objects.create(
            key="org_feat", name="Org Only", enabled=False, organization=org
        )
        flags = get_all_flags(org)
        assert "global_feat" in flags
        assert "org_feat" in flags

    def test_org_only_flags_not_in_other_org(self, db, user, org):
        other_user = User.objects.create_user(email="c@c.com", password="pass")
        other_org = Organization.objects.create(name="Other", owner=other_user)
        FeatureFlag.objects.create(
            key="exclusive", name="Exclusive", enabled=True, organization=org
        )
        flags = get_all_flags(other_org)
        assert "exclusive" not in flags
