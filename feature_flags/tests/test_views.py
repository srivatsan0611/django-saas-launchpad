import pytest
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory

from feature_flags.decorators import require_feature
from feature_flags.models import FeatureFlag
from organizations.models import Membership, Organization

User = get_user_model()


# Fixtures


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def owner(db):
    return User.objects.create_user(email="owner@acme.com", password="pass")


@pytest.fixture
def member(db):
    return User.objects.create_user(email="member@acme.com", password="pass")


@pytest.fixture
def outsider(db):
    return User.objects.create_user(email="outsider@other.com", password="pass")


@pytest.fixture
def org(db, owner, member):
    org = Organization.objects.create(name="Acme", owner=owner)
    Membership.objects.create(user=owner, organization=org, role="owner")
    Membership.objects.create(user=member, organization=org, role="member")
    return org


@pytest.fixture
def auth_owner(api_client, owner):
    api_client.force_authenticate(user=owner)
    return api_client


@pytest.fixture
def auth_member(api_client, member):
    api_client.force_authenticate(user=member)
    return api_client


@pytest.fixture
def global_flag(db):
    return FeatureFlag.objects.create(key="new_ui", name="New UI", enabled=True)


@pytest.fixture
def org_flag(db, org):
    return FeatureFlag.objects.create(
        key="reports", name="Reports", enabled=False, organization=org
    )


# ---------------------------------------------------------------------------
# GET /api/feature-flags/ — list
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFeatureFlagList:
    URL = "/api/feature-flags/"

    def test_unauthenticated_returns_401(self, api_client, org):
        resp = api_client.get(self.URL, {"organization_id": str(org.id)})
        assert resp.status_code == 401

    def test_missing_org_id_returns_400(self, auth_owner):
        resp = auth_owner.get(self.URL)
        assert resp.status_code == 400

    def test_non_member_returns_404(self, api_client, outsider, org):
        api_client.force_authenticate(user=outsider)
        resp = api_client.get(self.URL, {"organization_id": str(org.id)})
        assert resp.status_code == 404

    def test_returns_global_and_org_flags(self, auth_owner, org, global_flag, org_flag):
        resp = auth_owner.get(self.URL, {"organization_id": str(org.id)})
        assert resp.status_code == 200
        keys = [f["key"] for f in resp.data]
        assert "new_ui" in keys
        assert "reports" in keys

    def test_member_can_list_flags(self, auth_member, org, global_flag):
        resp = auth_member.get(self.URL, {"organization_id": str(org.id)})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/feature-flags/{key}/ — retrieve
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFeatureFlagRetrieve:
    def url(self, key):
        return f"/api/feature-flags/{key}/"

    def test_returns_flag_with_enabled_for_user(self, auth_owner, org, global_flag):
        resp = auth_owner.get(self.url("new_ui"), {"organization_id": str(org.id)})
        assert resp.status_code == 200
        assert "enabled_for_user" in resp.data
        assert resp.data["key"] == "new_ui"

    def test_nonexistent_key_returns_disabled(self, auth_owner, org):
        resp = auth_owner.get(self.url("ghost_flag"), {"organization_id": str(org.id)})
        assert resp.status_code == 200
        assert resp.data["enabled"] is False
        assert resp.data["enabled_for_user"] is False

    def test_missing_org_id_returns_400(self, auth_owner):
        resp = auth_owner.get(self.url("new_ui"))
        assert resp.status_code == 400

    def test_non_member_returns_404(self, api_client, outsider, org, global_flag):
        api_client.force_authenticate(user=outsider)
        resp = api_client.get(self.url("new_ui"), {"organization_id": str(org.id)})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/feature-flags/{key}/ — partial_update
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFeatureFlagPartialUpdate:
    def url(self, key):
        return f"/api/feature-flags/{key}/"

    def test_non_admin_member_returns_403(self, auth_member, org, global_flag):
        resp = auth_member.patch(
            self.url("new_ui"),
            {"enabled": True},
            format="json",
            QUERY_STRING=f"organization_id={org.id}",
        )
        assert resp.status_code == 403

    def test_owner_can_toggle_existing_flag(self, auth_owner, org, org_flag):
        resp = auth_owner.patch(
            self.url("reports"),
            {"enabled": True},
            format="json",
            QUERY_STRING=f"organization_id={org.id}",
        )
        assert resp.status_code == 200
        org_flag.refresh_from_db()
        assert org_flag.enabled is True

    def test_owner_creates_org_override_from_global(self, auth_owner, org, global_flag):
        assert not FeatureFlag.objects.filter(key="new_ui", organization=org).exists()
        resp = auth_owner.patch(
            self.url("new_ui"),
            {"enabled": False},
            format="json",
            QUERY_STRING=f"organization_id={org.id}",
        )
        assert resp.status_code == 200
        assert FeatureFlag.objects.filter(key="new_ui", organization=org).exists()
        override = FeatureFlag.objects.get(key="new_ui", organization=org)
        assert override.enabled is False

    def test_nonexistent_key_returns_404(self, auth_owner, org):
        resp = auth_owner.patch(
            self.url("ghost_flag"),
            {"enabled": True},
            format="json",
            QUERY_STRING=f"organization_id={org.id}",
        )
        assert resp.status_code == 404

    def test_missing_org_id_returns_400(self, auth_owner):
        resp = auth_owner.patch(self.url("new_ui"), {"enabled": True}, format="json")
        assert resp.status_code == 400

    def test_non_member_returns_404(self, api_client, outsider, org, global_flag):
        api_client.force_authenticate(user=outsider)
        resp = api_client.patch(
            self.url("new_ui"),
            {"enabled": True},
            format="json",
            QUERY_STRING=f"organization_id={org.id}",
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/feature-flags/evaluate/ — evaluate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEvaluateFeatureView:
    URL = "/api/feature-flags/evaluate/"

    def test_missing_key_returns_400(self, auth_owner, org):
        resp = auth_owner.post(self.URL, {"org_id": str(org.id)}, format="json")
        assert resp.status_code == 400

    def test_missing_org_id_returns_400(self, auth_owner):
        resp = auth_owner.post(self.URL, {"key": "new_ui"}, format="json")
        assert resp.status_code == 400

    def test_non_member_returns_404(self, api_client, outsider, org):
        api_client.force_authenticate(user=outsider)
        resp = api_client.post(
            self.URL, {"key": "new_ui", "org_id": str(org.id)}, format="json"
        )
        assert resp.status_code == 404

    def test_returns_enabled_true_for_active_flag(self, auth_owner, org, global_flag):
        resp = auth_owner.post(
            self.URL, {"key": "new_ui", "org_id": str(org.id)}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["enabled"] is True

    def test_returns_enabled_false_for_nonexistent_flag(self, auth_owner, org):
        resp = auth_owner.post(
            self.URL, {"key": "ghost", "org_id": str(org.id)}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["enabled"] is False

    def test_returns_enabled_false_for_disabled_flag(self, auth_owner, org, org_flag):
        resp = auth_owner.post(
            self.URL, {"key": "reports", "org_id": str(org.id)}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["enabled"] is False

    def test_unauthenticated_returns_401(self, api_client, org):
        resp = api_client.post(
            self.URL, {"key": "new_ui", "org_id": str(org.id)}, format="json"
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# @require_feature decorator
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRequireFeatureDecorator:
    def _make_request(self, user, org, method="get"):
        factory = APIRequestFactory()
        make = getattr(factory, method)
        request = make("/", {"organization_id": str(org.id)})
        request.user = user
        return request

    def test_returns_403_when_feature_disabled(self, owner, org):
        FeatureFlag.objects.create(
            key="locked", name="Locked", enabled=False, organization=org
        )

        @require_feature("locked")
        def my_view(request):
            return Response({"ok": True})

        request = self._make_request(owner, org)
        resp = my_view(request)
        assert resp.status_code == 403

    def test_passes_through_when_feature_enabled(self, owner, org):
        FeatureFlag.objects.create(
            key="open", name="Open", enabled=True, organization=org
        )

        @require_feature("open")
        def my_view(request):
            return Response({"ok": True}, status=200)

        request = self._make_request(owner, org)
        resp = my_view(request)
        assert resp.status_code == 200

    def test_returns_400_when_org_id_missing(self, owner, org):
        FeatureFlag.objects.create(
            key="feat", name="Feat", enabled=True, organization=org
        )

        @require_feature("feat")
        def my_view(request):
            return Response({"ok": True})

        factory = APIRequestFactory()
        request = factory.get("/")  # no organization_id
        request.user = owner
        resp = my_view(request)
        assert resp.status_code == 400

    def test_returns_404_for_non_member_org(self, outsider, org):
        FeatureFlag.objects.create(
            key="feat", name="Feat", enabled=True, organization=org
        )

        @require_feature("feat")
        def my_view(request):
            return Response({"ok": True})

        request = self._make_request(outsider, org)
        resp = my_view(request)
        assert resp.status_code == 404

    def test_uses_org_from_middleware_context(self, owner, org):
        FeatureFlag.objects.create(
            key="ctx", name="Ctx", enabled=True, organization=org
        )

        @require_feature("ctx")
        def my_view(request):
            return Response({"ok": True}, status=200)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = owner
        request.organization = org  # simulates middleware injection
        resp = my_view(request)
        assert resp.status_code == 200
