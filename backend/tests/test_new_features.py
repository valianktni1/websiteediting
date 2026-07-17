"""Backend tests for NEW features: user CRUD, SFTP get/set, ingest, page create/delete,
backups, restore, brute-force lockout."""
import os
import time
import pytest
import requests

def _load_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        # read from frontend/.env in preview
        try:
            for line in open("/app/frontend/.env"):
                if line.startswith("REACT_APP_BACKEND_URL="):
                    v = line.split("=",1)[1].strip(); break
        except Exception: pass
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")

BASE = _load_base()
ADMIN_EMAIL = "admin@wifetobe.org"
ADMIN_PW = "ChangeMe!2026"
SITE = "wifetobe"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return s


# --- Users CRUD (admin) ---
class TestUsersCRUD:
    def test_list_users(self, admin):
        r = admin.get(f"{BASE}/api/users")
        assert r.status_code == 200
        users = r.json()
        emails = [u["email"] for u in users]
        assert ADMIN_EMAIL in emails
        assert all("password_hash" not in u for u in users)

    def test_create_and_delete_editor_user(self, admin):
        email = f"test_newuser_{int(time.time())}@example.com"
        r = admin.post(f"{BASE}/api/users", json={
            "email": email, "password": "SomePass!123",
            "name": "New Editor", "role": "editor", "site_id": SITE
        })
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
        assert r.json()["email"] == email
        assert r.json()["role"] == "editor"

        # verify present in list
        listed = admin.get(f"{BASE}/api/users").json()
        assert any(u["id"] == uid for u in listed)

        # duplicate email -> 400
        r_dup = admin.post(f"{BASE}/api/users", json={
            "email": email, "password": "x", "role": "editor"})
        assert r_dup.status_code == 400

        # delete
        r_del = admin.delete(f"{BASE}/api/users/{uid}")
        assert r_del.status_code == 200

        # verify removed
        listed2 = admin.get(f"{BASE}/api/users").json()
        assert not any(u["id"] == uid for u in listed2)

    def test_admin_cannot_delete_self(self, admin):
        me = admin.get(f"{BASE}/api/auth/me").json()
        r = admin.delete(f"{BASE}/api/users/{me['id']}")
        assert r.status_code == 400


# --- SFTP get/set ---
class TestSftp:
    def test_get_sftp_initial(self, admin):
        r = admin.get(f"{BASE}/api/sites/{SITE}/sftp")
        assert r.status_code == 200
        d = r.json()
        assert "host" in d and "port" in d and "username" in d and "remote_path" in d and "has_password" in d

    def test_set_and_get_sftp_persists(self, admin):
        payload = {
            "host": "test.hostinger.com", "port": 22,
            "username": "testuser", "password": "TESTpw!",
            "remote_path": "/public_html_test"
        }
        r = admin.put(f"{BASE}/api/sites/{SITE}/sftp", json=payload)
        assert r.status_code == 200
        g = admin.get(f"{BASE}/api/sites/{SITE}/sftp").json()
        assert g["host"] == payload["host"]
        assert g["username"] == payload["username"]
        assert g["remote_path"] == payload["remote_path"]
        assert g["has_password"] is True
        # password should NOT be leaked in GET response
        assert "password" not in g

        # Setting with blank password overwrites password to blank per current impl (model default "").
        # This is a UX concern: "leaving blank keeps existing" is NOT implemented server-side.
        # Reset to blank and verify (documents current behavior).
        r2 = admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
            "host": "", "port": 22, "username": "", "password": "", "remote_path": "/public_html"
        })
        assert r2.status_code == 200
        g2 = admin.get(f"{BASE}/api/sites/{SITE}/sftp").json()
        assert g2["has_password"] is False


# --- Available sites + Re-ingest ---
class TestAvailableAndIngest:
    def test_available_sites(self, admin):
        r = admin.get(f"{BASE}/api/available-sites")
        assert r.status_code == 200
        arr = r.json()
        slugs = [s["slug"] for s in arr]
        assert SITE in slugs
        w = next(s for s in arr if s["slug"] == SITE)
        assert w["ingested"] is True
        assert w["pages"] >= 14

    def test_reingest(self, admin):
        r = admin.post(f"{BASE}/api/sites/{SITE}/ingest")
        assert r.status_code == 200
        assert r.json()["ingested"] >= 14


# --- Page create + delete ---
class TestPageCreateDelete:
    def test_create_page_from_home_and_delete(self, admin):
        slug = f"test-page-{int(time.time())}"
        r = admin.post(f"{BASE}/api/pages/{SITE}", json={"slug": slug, "title": "Test Page"})
        assert r.status_code == 200, r.text
        assert r.json()["slug"] == slug

        # It should appear in page list and be fetchable
        pages = admin.get(f"{BASE}/api/sites/{SITE}/pages").json()
        assert any(p["slug"] == slug for p in pages)

        got = admin.get(f"{BASE}/api/pages/{SITE}/{slug}")
        assert got.status_code == 200
        pdata = got.json()
        assert pdata["title"] == "Test Page"
        # must be a copy of home => regions exist
        home = admin.get(f"{BASE}/api/pages/{SITE}/home").json()
        assert len(pdata["regions"]) == len(home["regions"])

        # duplicate slug -> 400
        dup = admin.post(f"{BASE}/api/pages/{SITE}", json={"slug": slug, "title": "x"})
        assert dup.status_code == 400

        # slug=home -> 400
        h = admin.post(f"{BASE}/api/pages/{SITE}", json={"slug": "home", "title": "x"})
        assert h.status_code == 400

        # delete
        d = admin.delete(f"{BASE}/api/pages/{SITE}/{slug}")
        assert d.status_code == 200
        pages2 = admin.get(f"{BASE}/api/sites/{SITE}/pages").json()
        assert not any(p["slug"] == slug for p in pages2)

    def test_cannot_delete_home(self, admin):
        r = admin.delete(f"{BASE}/api/pages/{SITE}/home")
        assert r.status_code == 400


# --- Backups / restore ---
class TestBackupsRestore:
    def test_list_backups(self, admin):
        # trigger a publish to ensure at least one backup exists
        admin.post(f"{BASE}/api/sites/{SITE}/publish")
        r = admin.get(f"{BASE}/api/sites/{SITE}/backups")
        assert r.status_code == 200
        arr = r.json()
        assert len(arr) >= 1
        assert arr[0]["name"].startswith(f"{SITE}-") and arr[0]["name"].endswith(".zip")

    def test_restore_without_sftp_returns_message(self, admin):
        # ensure SFTP unconfigured
        admin.put(f"{BASE}/api/sites/{SITE}/sftp", json={
            "host": "", "port": 22, "username": "", "password": "", "remote_path": "/public_html"})
        backups = admin.get(f"{BASE}/api/sites/{SITE}/backups").json()
        assert len(backups) >= 1
        name = backups[0]["name"]
        r = admin.post(f"{BASE}/api/sites/{SITE}/restore", json={"name": name})
        assert r.status_code == 200
        d = r.json()
        assert d["restored"] is False
        assert "SFTP" in d["message"] or "sftp" in d["message"].lower()

    def test_restore_bad_name_404(self, admin):
        r = admin.post(f"{BASE}/api/sites/{SITE}/restore", json={"name": "does-not-exist.zip"})
        assert r.status_code == 404


# --- Brute-force login lockout ---
class TestBruteForce:
    def test_lockout_after_5_fails(self):
        # throwaway email to avoid locking real admin
        email = f"bruteforce_{int(time.time())}@example.com"
        for i in range(5):
            r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": "wrong"})
            assert r.status_code == 401, f"attempt {i+1} expected 401 got {r.status_code}"
        r6 = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": "wrong"})
        assert r6.status_code == 429
        assert "Too many" in r6.text or "too many" in r6.text.lower()


# --- RBAC on new endpoints ---
class TestRBACNew:
    def test_editor_forbidden_from_admin_endpoints(self, admin):
        email = f"test_rbac_{int(time.time())}@example.com"
        pw = "EditorPass!123"
        r = admin.post(f"{BASE}/api/users", json={
            "email": email, "password": pw, "role": "editor", "site_id": SITE})
        assert r.status_code == 200
        uid = r.json()["id"]
        try:
            s = requests.Session()
            login = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw})
            assert login.status_code == 200
            # admin-only endpoints
            assert s.get(f"{BASE}/api/users").status_code == 403
            assert s.post(f"{BASE}/api/users", json={"email":"x@x","password":"p"}).status_code == 403
            assert s.get(f"{BASE}/api/available-sites").status_code == 403
            assert s.post(f"{BASE}/api/sites/{SITE}/ingest").status_code == 403
            assert s.get(f"{BASE}/api/sites/{SITE}/sftp").status_code == 403
            assert s.put(f"{BASE}/api/sites/{SITE}/sftp", json={
                "host":"h","port":22,"username":"u","password":"p","remote_path":"/p"}).status_code == 403
            # editor CAN create+delete pages (per PRD)
            slug = f"test-editor-page-{int(time.time())}"
            cr = s.post(f"{BASE}/api/pages/{SITE}", json={"slug": slug, "title":"E"})
            assert cr.status_code == 200
            de = s.delete(f"{BASE}/api/pages/{SITE}/{slug}")
            assert de.status_code == 200
        finally:
            admin.delete(f"{BASE}/api/users/{uid}")
