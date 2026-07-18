"""Backend tests for SAFETY-CRITICAL domain-lock feature (publish guardrails)."""
import os
import time
import pytest
import requests

def _load_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        for line in open("/app/frontend/.env"):
            if line.startswith("REACT_APP_BACKEND_URL="):
                v = line.split("=", 1)[1].strip(); break
    assert v
    return v.rstrip("/")

BASE = _load_base()
ADMIN_EMAIL = "admin@wifetobe.org"
ADMIN_PW = "ChangeMe!2026"
SITE = "wifetobe"
GOOD_PATH = "/home/u897891218/domains/wifetobe.org/public_html"
LOCKED_DOMAIN = "wifetobe.org"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module", autouse=True)
def _preserve_state(admin):
    """Snapshot & restore wifetobe sftp/domain around the test module."""
    before = admin.get(f"{BASE}/api/sites/{SITE}/sftp").json()
    yield
    # Reset to preview-clean: host blank, correct path, domain locked
    admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
        "host": "", "port": before.get("port", 65002),
        "username": "", "password": "",
        "remote_path": GOOD_PATH,
        "domain": LOCKED_DOMAIN,
    })


# All classes below share wifetobe SFTP DB state. Merged into ONE class so xdist
# loadscope keeps them on a single worker (avoids inter-class state races).
class TestDomainLockSuite:
    # ---- domain set/get ----
    def test_put_sftp_stores_domain(self, admin):
        r = admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
            "host": "", "port": 65002, "username": "", "password": "",
            "remote_path": GOOD_PATH, "domain": LOCKED_DOMAIN,
        })
        assert r.status_code == 200
        g = admin.get(f"{BASE}/api/sites/{SITE}/sftp").json()
        assert g["domain"] == LOCKED_DOMAIN
        assert "has_password" in g

    def test_get_sftp_case_insensitive_stored(self, admin):
        r = admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
            "host": "", "port": 65002, "username": "", "password": "",
            "remote_path": GOOD_PATH, "domain": "  WifeToBe.Org  ",
        })
        assert r.status_code == 200
        g = admin.get(f"{BASE}/api/sites/{SITE}/sftp").json()
        # backend lowercases + strips
        assert g["domain"] == LOCKED_DOMAIN


    # ----
    # publish-target
    def test_path_ok_true_when_domain_in_path(self, admin):
        admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
            "host": "", "port": 65002, "username": "", "password": "",
            "remote_path": GOOD_PATH, "domain": LOCKED_DOMAIN,
        })
        r = admin.get(f"{BASE}/api/sites/{SITE}/publish-target")
        assert r.status_code == 200
        d = r.json()
        assert d["domain"] == LOCKED_DOMAIN
        assert d["path_ok"] is True
        assert d["remote_path"] == GOOD_PATH
        assert "pages" in d and d["pages"] >= 14
        assert d["configured"] is False  # host blank

    def test_path_ok_false_bare_public_html(self, admin):
        admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
            "host": "", "port": 65002, "username": "", "password": "",
            "remote_path": "public_html", "domain": LOCKED_DOMAIN,
        })
        d = admin.get(f"{BASE}/api/sites/{SITE}/publish-target").json()
        assert d["path_ok"] is False
        assert d["domain"] == LOCKED_DOMAIN

    def test_path_ok_false_wrong_domain_path(self, admin):
        admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
            "host": "", "port": 65002, "username": "", "password": "",
            "remote_path": "/home/u897891218/domains/someothersite.com/public_html",
            "domain": LOCKED_DOMAIN,
        })
        d = admin.get(f"{BASE}/api/sites/{SITE}/publish-target").json()
        assert d["path_ok"] is False


    # ----
    # publish block
    def test_publish_blocked_bare_public_html_fast(self, admin):
        # Set fake host + BAD path (bare public_html). Guard must short-circuit
        # BEFORE any SFTP attempt.
        admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
            "host": "fake.invalid.host", "port": 65002,
            "username": "u", "password": "p",
            "remote_path": "public_html", "domain": LOCKED_DOMAIN,
        })
        start = time.time()
        r = admin.post(f"{BASE}/api/sites/{SITE}/publish", timeout=10)
        elapsed = time.time() - start
        assert r.status_code == 400, r.text
        body = r.text.lower()
        assert "blocked for safety" in body
        assert elapsed < 5, f"Guard should short-circuit but took {elapsed:.1f}s"

    def test_publish_blocked_wrong_domain_fast(self, admin):
        admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
            "host": "fake.invalid.host", "port": 65002,
            "username": "u", "password": "p",
            "remote_path": "/home/u897891218/domains/otherdomain.com/public_html",
            "domain": LOCKED_DOMAIN,
        })
        start = time.time()
        r = admin.post(f"{BASE}/api/sites/{SITE}/publish", timeout=10)
        elapsed = time.time() - start
        assert r.status_code == 400
        assert "blocked for safety" in r.text.lower()
        assert elapsed < 5

    def test_publish_allowed_when_path_contains_domain(self, admin):
        # With a bogus host but correct path — guard passes, connection fails.
        # Publish returns 200 with published=false (render+backup ok, sftp push failed).
        admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
            "host": "fake.invalid.host", "port": 65002,
            "username": "u", "password": "p",
            "remote_path": GOOD_PATH, "domain": LOCKED_DOMAIN,
        })
        r = admin.post(f"{BASE}/api/sites/{SITE}/publish", timeout=30)
        # Guard passes -> connection attempt fails but request completes 200
        assert r.status_code == 200
        d = r.json()
        assert d.get("published") is False
        assert "backup" in d


    # ----
    # restore block
    def test_restore_admin_only(self, admin):
        # Create editor user, try to hit restore
        email = f"test_restore_rbac_{int(time.time())}@example.com"
        r = admin.post(f"{BASE}/api/users", json={
            "email": email, "password": "Pw!12345", "role": "editor", "site_id": SITE})
        assert r.status_code == 200
        uid = r.json()["id"]
        try:
            s = requests.Session()
            s.post(f"{BASE}/api/auth/login", json={"email": email, "password": "Pw!12345"})
            resp = s.post(f"{BASE}/api/sites/{SITE}/restore", json={"name": "whatever.zip"})
            assert resp.status_code == 403
        finally:
            admin.delete(f"{BASE}/api/users/{uid}")

    def test_restore_domain_guard_blocks(self, admin):
        # Ensure at least one backup exists
        admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
            "host": "", "port": 65002, "username": "", "password": "",
            "remote_path": GOOD_PATH, "domain": LOCKED_DOMAIN,
        })
        admin.post(f"{BASE}/api/sites/{SITE}/publish")
        backups = admin.get(f"{BASE}/api/sites/{SITE}/backups").json()
        assert len(backups) >= 1
        name = backups[0]["name"]

        # Now set BAD path and try restore
        admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
            "host": "fake.invalid.host", "port": 65002,
            "username": "u", "password": "p",
            "remote_path": "public_html", "domain": LOCKED_DOMAIN,
        })
        start = time.time()
        r = admin.post(f"{BASE}/api/sites/{SITE}/restore", json={"name": name}, timeout=10)
        elapsed = time.time() - start
        assert r.status_code == 400
        assert "blocked for safety" in r.text.lower()
        assert elapsed < 5


    # ----
    # white-label regression
    def test_sites_lists_wifetobe(self, admin):
        r = admin.get(f"{BASE}/api/sites")
        assert r.status_code == 200
        slugs = [s["slug"] for s in r.json()]
        assert SITE in slugs

    def test_14_pages(self, admin):
        r = admin.get(f"{BASE}/api/sites/{SITE}/pages")
        assert r.status_code == 200
        assert len(r.json()) >= 14

    def test_editor_iframe_renders(self, admin):
        r = admin.get(f"{BASE}/api/editor/page/{SITE}/home")
        assert r.status_code == 200
        assert "data-eid" in r.text
