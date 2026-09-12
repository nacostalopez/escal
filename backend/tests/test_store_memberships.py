"""Tests for per-store role overrides (StoreMembership) — see
app/dependencies.py::require_store_role and app/routes/stores.py's
members endpoints.
"""
import pytest
from fastapi import status


def _login(client, email, password):
    response = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.db
class TestEffectiveRoleFallback:
    def test_admin_with_no_override_keeps_account_role(self, client, auth_header, test_store, admin_user):
        """Sanity check: no StoreMembership row means account role applies,
        unchanged from before this feature existed."""
        admin_header = _login(client, "admin@example.com", "adminpassword123")
        response = client.put(
            f"/stores/{test_store.id}/report-preferences", headers=admin_header, json={"enabled": True}
        )
        assert response.status_code == status.HTTP_200_OK

    def test_viewer_with_no_override_is_still_blocked(self, client, test_store, viewer_user):
        viewer_header = _login(client, "viewer@example.com", "viewerpassword123")
        response = client.put(
            f"/stores/{test_store.id}/report-preferences", headers=viewer_header, json={"enabled": True}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.db
class TestStoreOverrideChangesEffectiveRole:
    def test_override_to_viewer_blocks_an_account_admin_on_that_store(
        self, client, auth_header, test_store, admin_user
    ):
        set_response = client.put(
            f"/stores/{test_store.id}/members/{admin_user.id}",
            headers=auth_header,
            json={"role": "viewer"},
        )
        assert set_response.status_code == status.HTTP_200_OK
        assert set_response.json()["effective_role"] == "viewer"

        admin_header = _login(client, "admin@example.com", "adminpassword123")
        response = client.put(
            f"/stores/{test_store.id}/report-preferences", headers=admin_header, json={"enabled": True}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_override_to_admin_lets_an_account_viewer_manage_that_store(
        self, client, auth_header, test_store, viewer_user
    ):
        client.put(
            f"/stores/{test_store.id}/members/{viewer_user.id}",
            headers=auth_header,
            json={"role": "admin"},
        )

        viewer_header = _login(client, "viewer@example.com", "viewerpassword123")
        response = client.put(
            f"/stores/{test_store.id}/report-preferences", headers=viewer_header, json={"enabled": True}
        )
        assert response.status_code == status.HTTP_200_OK

    def test_clearing_override_falls_back_to_account_role(self, client, auth_header, test_store, admin_user):
        client.put(f"/stores/{test_store.id}/members/{admin_user.id}", headers=auth_header, json={"role": "viewer"})
        clear_response = client.put(
            f"/stores/{test_store.id}/members/{admin_user.id}", headers=auth_header, json={"role": None}
        )
        assert clear_response.json()["store_role"] is None
        assert clear_response.json()["effective_role"] == "admin"

        admin_header = _login(client, "admin@example.com", "adminpassword123")
        response = client.put(
            f"/stores/{test_store.id}/report-preferences", headers=admin_header, json={"enabled": True}
        )
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.db
class TestMembersEndpointGating:
    def test_list_members_shows_account_and_effective_roles(self, client, auth_header, test_store, admin_user):
        client.put(f"/stores/{test_store.id}/members/{admin_user.id}", headers=auth_header, json={"role": "viewer"})

        response = client.get(f"/stores/{test_store.id}/members", headers=auth_header)
        assert response.status_code == status.HTTP_200_OK
        by_email = {m["email"]: m for m in response.json()}
        assert by_email["admin@example.com"]["account_role"] == "admin"
        assert by_email["admin@example.com"]["store_role"] == "viewer"
        assert by_email["admin@example.com"]["effective_role"] == "viewer"

    def test_only_account_owner_can_set_overrides(self, client, test_store, admin_user, viewer_user):
        admin_header = _login(client, "admin@example.com", "adminpassword123")
        response = client.put(
            f"/stores/{test_store.id}/members/{viewer_user.id}",
            headers=admin_header,
            json={"role": "admin"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_by_override_still_cannot_grant_overrides(
        self, client, auth_header, test_store, admin_user, viewer_user
    ):
        """An override only ever grants store-scoped permissions
        (require_store_role) — granting overrides themselves stays gated
        to the account-wide owner role, so this can't be used to
        self-escalate."""
        client.put(f"/stores/{test_store.id}/members/{viewer_user.id}", headers=auth_header, json={"role": "admin"})

        viewer_header = _login(client, "viewer@example.com", "viewerpassword123")
        response = client.put(
            f"/stores/{test_store.id}/members/{admin_user.id}",
            headers=viewer_header,
            json={"role": "owner"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
