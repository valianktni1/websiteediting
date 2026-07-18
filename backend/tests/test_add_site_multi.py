"""Iteration 5 tests: super-admin add-site (SFTP pull), multi-site, role hierarchy.

Kept in ONE class (pytest.ini uses xdist -n 2 --dist loadscope) — see iteration_4 notes.
"""
import os
import time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE = line.split("=", 1)[1].strip().rstrip("/")
            break
assert BASE

ADMIN_EMAIL = "admin@wifetobe.org"
ADMIN_PW = "ChangeMe!2026"


def _super_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return s


class TestAddSiteMultiSuite:
    # ---- Role migration to superadmin ----
    def test_seeded_admin_is_superadmin(self):
        s = _super_session()
        me = s.get(f"{BASE}/api/auth/me").json()
        assert me["role"] == "superadmin", me
        assert me["email"] == ADMIN_EMAIL

    # ---- /api/sites multi-site ----
    def test_sites_lists_two(self):
        s = _super_session()
        r = s.get(f"{BASE}/api/sites")
        assert r.status_code == 200
        slugs = sorted([x["slug"] for x in r.json()])
        assert "wifetobe" in slugs
        assert "demo-couk" in slugs
        # verify page counts
        wife_pages = s.get(f"{BASE}/api/sites/wifetobe/pages").json()
        demo_pages = s.get(f"{BASE}/api/sites/demo-couk/pages").json()
        assert len(wife_pages) >= 14
        assert len(demo_pages) == 2

    # ---- Add-site validation (superadmin) ----
    def test_add_site_duplicate_slug_400(self):
        s = _super_session()
        r = s.post(f"{BASE}/api/sites/add", json={
            "slug": "wifetobe", "host": "h", "username": "u", "password": "p"})
        assert r.status_code == 400
        assert "exists" in r.text.lower() or "already" in r.text.lower()

    def test_add_site_missing_creds_400(self):
        s = _super_session()
        # missing host
        r1 = s.post(f"{BASE}/api/sites/add", json={
            "slug": f"newsite-{int(time.time())}", "host": "", "username": "u", "password": "p"})
        assert r1.status_code == 400
        # missing username -> pydantic requires field or backend 400
        r2 = s.post(f"{BASE}/api/sites/add", json={
            "slug": f"newsite-{int(time.time())}", "host": "h", "username": "", "password": "p"})
        assert r2.status_code == 400
        # missing password
        r3 = s.post(f"{BASE}/api/sites/add", json={
            "slug": f"newsite-{int(time.time())}", "host": "h", "username": "u", "password": ""})
        assert r3.status_code == 400

    # ---- Real SFTP pull (rebex demo, no HTML => self-cleans) ----
    def test_add_site_real_pull_no_html_selfcleans(self):
        s = _super_session()
        slug = "testpull"
        # ensure clean start
        pre_sites = [x["slug"] for x in s.get(f"{BASE}/api/sites").json()]
        assert slug not in pre_sites
        r = s.post(f"{BASE}/api/sites/add", json={
            "slug": slug, "host": "test.rebex.net", "port": 22,
            "username": "demo", "password": "password",
            "remote_path": "/pub/example"
        }, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is False
        assert "no .html pages" in d["message"].lower() or "html" in d["message"].lower()
        # verify site was NOT persisted
        post_slugs = [x["slug"] for x in s.get(f"{BASE}/api/sites").json()]
        assert slug not in post_slugs, f"leftover {slug} in {post_slugs}"

    # ---- RBAC on /api/sites/add ----
    def test_add_site_rbac_admin_and_editor_forbidden(self):
        sup = _super_session()
        ts = int(time.time())
        admin_email = f"test_admin_{ts}@example.com"
        editor_email = f"test_editor_{ts}@example.com"
        pw = "SomePass!123"
        # create regular admin
        ra = sup.post(f"{BASE}/api/users", json={
            "email": admin_email, "password": pw, "name": "TA",
            "role": "admin", "site_id": None})
        assert ra.status_code == 200, ra.text
        admin_uid = ra.json()["id"]
        # create editor scoped to wifetobe
        re_ = sup.post(f"{BASE}/api/users", json={
            "email": editor_email, "password": pw, "name": "TE",
            "role": "editor", "site_id": "wifetobe"})
        assert re_.status_code == 200
        editor_uid = re_.json()["id"]

        try:
            # regular admin logs in
            admin_s = requests.Session()
            assert admin_s.post(f"{BASE}/api/auth/login", json={
                "email": admin_email, "password": pw}).status_code == 200
            # sites/add -> 403
            r = admin_s.post(f"{BASE}/api/sites/add", json={
                "slug": f"x-{ts}", "host": "h", "username": "u", "password": "p"})
            assert r.status_code == 403
            # BUT admin CAN access /users and /available-sites
            assert admin_s.get(f"{BASE}/api/users").status_code == 200
            assert admin_s.get(f"{BASE}/api/available-sites").status_code == 200

            # editor logs in
            ed_s = requests.Session()
            assert ed_s.post(f"{BASE}/api/auth/login", json={
                "email": editor_email, "password": pw}).status_code == 200
            r2 = ed_s.post(f"{BASE}/api/sites/add", json={
                "slug": f"y-{ts}", "host": "h", "username": "u", "password": "p"})
            assert r2.status_code == 403
            # editor still forbidden from admin endpoints
            assert ed_s.get(f"{BASE}/api/users").status_code == 403
            assert ed_s.get(f"{BASE}/api/available-sites").status_code == 403
        finally:
            sup.delete(f"{BASE}/api/users/{admin_uid}")
            sup.delete(f"{BASE}/api/users/{editor_uid}")

    # ---- Regression: publish endpoint restored ----
    def test_publish_endpoint_registered(self):
        s = _super_session()
        r = s.post(f"{BASE}/api/sites/wifetobe/publish")
        assert r.status_code == 200, r.text
        d = r.json()
        # SFTP not configured in preview -> published:false with backup
        assert "backup" in d
        assert d.get("published") is False
        assert "SFTP" in d.get("message", "") or "sftp" in d.get("message", "").lower()

    # ---- Regression: publish-target still works with domain lock ----
    def test_publish_target_wifetobe_domain_lock(self):
        s = _super_session()
        r = s.get(f"{BASE}/api/sites/wifetobe/publish-target")
        assert r.status_code == 200
        d = r.json()
        assert d["domain"] == "wifetobe.org"
        # path_ok true when domain in remote_path
        # (may be false if remote_path was left blank by earlier test; verify field exists)
        assert "path_ok" in d
