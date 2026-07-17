"""Backend tests for Website Editor (Wife To Be)."""
import os
import io
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://elementor-builder-4.preview.emergentagent.com"
# fallback: use the frontend .env value in preview
if not BASE.startswith("http"):
    BASE = "https://elementor-builder-4.preview.emergentagent.com"

ADMIN_EMAIL = "admin@wifetobe.org"
ADMIN_PW = "ChangeMe!2026"
SITE = "wifetobe"

EXPECTED_PAGES = {"home","about","contact","boutiques","bridal-collections","brides",
    "mens-formal-wear","big-screen-advertising","found-the-dress","bolton","wigan",
    "frodsham","newton-le-willows","404"}


@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


# --- auth ---
class TestAuth:
    def test_login_wrong_password(self):
        r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_login_success_and_me(self, admin):
        r = admin.get(f"{BASE}/api/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"

    def test_me_unauth(self):
        r = requests.get(f"{BASE}/api/auth/me")
        assert r.status_code == 401


# --- sites & pages ---
class TestSites:
    def test_list_sites(self, admin):
        r = admin.get(f"{BASE}/api/sites")
        assert r.status_code == 200
        sites = r.json()
        slugs = [s["slug"] for s in sites]
        assert SITE in slugs

    def test_list_pages_14(self, admin):
        r = admin.get(f"{BASE}/api/sites/{SITE}/pages")
        assert r.status_code == 200
        pages = r.json()
        assert len(pages) == 14, f"expected 14 pages, got {len(pages)}"
        slugs = {p["slug"] for p in pages}
        missing = EXPECTED_PAGES - slugs
        assert not missing, f"missing pages: {missing}"

    def test_get_page(self, admin):
        r = admin.get(f"{BASE}/api/pages/{SITE}/home")
        assert r.status_code == 200
        p = r.json()
        assert p["slug"] == "home"
        assert "regions" in p and len(p["regions"]) > 0
        assert "seo" in p


# --- region update ---
class TestRegionUpdate:
    def test_update_text_region_persists(self, admin):
        p = admin.get(f"{BASE}/api/pages/{SITE}/home").json()
        # find a text region
        text_eid = None
        original = None
        for eid, r in p["regions"].items():
            if r["type"] == "text":
                text_eid = eid
                original = r["value"]
                break
        assert text_eid, "no text region found"
        new_val = "TEST_updated_" + text_eid
        r = admin.put(f"{BASE}/api/pages/{SITE}/home/region", json={"eid": text_eid, "value": new_val})
        assert r.status_code == 200
        # verify
        p2 = admin.get(f"{BASE}/api/pages/{SITE}/home").json()
        assert p2["regions"][text_eid]["value"] == new_val
        # restore
        admin.put(f"{BASE}/api/pages/{SITE}/home/region", json={"eid": text_eid, "value": original})

    def test_unknown_region_400(self, admin):
        r = admin.put(f"{BASE}/api/pages/{SITE}/home/region", json={"eid": "does-not-exist", "value": "x"})
        assert r.status_code == 400


# --- media upload + image region ---
class TestMedia:
    def test_upload_and_apply(self, admin):
        # tiny PNG
        png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c626001000000050001"
                            "0d0a2db40000000049454e44ae426082")
        files = {"file": ("test.png", io.BytesIO(png), "image/png")}
        r = admin.post(f"{BASE}/api/media/{SITE}/upload", files=files)
        assert r.status_code == 200
        url = r.json()["url"]
        assert url.startswith("assets/uploads/")
        # apply to first image region
        p = admin.get(f"{BASE}/api/pages/{SITE}/home").json()
        img_eid = None; original = None
        for eid, reg in p["regions"].items():
            if reg["type"] == "image":
                img_eid = eid; original = reg["value"]; break
        assert img_eid, "no image region"
        r2 = admin.put(f"{BASE}/api/pages/{SITE}/home/region", json={"eid": img_eid, "value": url})
        assert r2.status_code == 200
        p2 = admin.get(f"{BASE}/api/pages/{SITE}/home").json()
        assert p2["regions"][img_eid]["value"] == url
        # restore
        admin.put(f"{BASE}/api/pages/{SITE}/home/region", json={"eid": img_eid, "value": original})


# --- SEO ---
class TestSeo:
    def test_seo_update_preserves_metas_and_jsonld(self, admin):
        p = admin.get(f"{BASE}/api/pages/{SITE}/home").json()
        seo = p["seo"]
        original_title = seo.get("title", "")
        original_metas = seo.get("metas", [])
        original_jsonld = seo.get("jsonld", [])
        assert len(original_metas) > 0, "expected non-empty metas from ingest"
        # Update title only, keep others
        new_seo = dict(seo); new_seo["title"] = "TEST_NEW_TITLE"
        r = admin.put(f"{BASE}/api/pages/{SITE}/home/seo", json={"seo": new_seo})
        assert r.status_code == 200
        p2 = admin.get(f"{BASE}/api/pages/{SITE}/home").json()
        assert p2["seo"]["title"] == "TEST_NEW_TITLE"
        assert len(p2["seo"]["metas"]) == len(original_metas)
        assert len(p2["seo"]["jsonld"]) == len(original_jsonld)
        # restore
        new_seo["title"] = original_title
        admin.put(f"{BASE}/api/pages/{SITE}/home/seo", json={"seo": new_seo})


# --- preview + dist ---
class TestPreview:
    def test_preview_builds_and_clean_output(self, admin):
        r = admin.post(f"{BASE}/api/sites/{SITE}/preview")
        assert r.status_code == 200
        data = r.json()
        assert data["pages"] == 14
        # fetch home
        r2 = admin.get(f"{BASE}/api/dist/{SITE}/index.html")
        assert r2.status_code == 200
        html = r2.text
        assert "data-eid" not in html, "dist HTML should NOT contain data-eid"
        assert "<html" in html.lower()

    def test_root_files_preserved(self, admin):
        # preview already built above; ensure files exist
        for f in ("robots.txt", "llms.txt", "llms-full.txt", "sitemap.xml"):
            r = admin.get(f"{BASE}/api/dist/{SITE}/{f}")
            assert r.status_code == 200, f"{f} not present in dist"
            assert len(r.text) > 0


# --- publish ---
class TestPublish:
    def test_publish_without_sftp(self, admin):
        r = admin.post(f"{BASE}/api/sites/{SITE}/publish")
        assert r.status_code == 200
        data = r.json()
        assert data["published"] is False
        assert "backup" in data and data["backup"]
        assert "SFTP" in data.get("message", "") or "sftp" in data.get("message", "").lower()


# --- editor iframe ---
class TestEditorIframe:
    def test_editor_page_html(self, admin):
        r = admin.get(f"{BASE}/api/editor/page/{SITE}/home")
        assert r.status_code == 200
        html = r.text
        assert "data-eid" in html, "editor html must contain data-eid"

    def test_editor_page_unauth(self):
        r = requests.get(f"{BASE}/api/editor/page/{SITE}/home")
        assert r.status_code == 401


# --- RBAC users ---
class TestRBAC:
    def test_editor_cannot_create_users(self, admin):
        import time
        email = f"TEST_editor_{int(time.time())}@example.com"
        pw = "EditorPass!123"
        # create editor as admin
        r = admin.post(f"{BASE}/api/users", json={"email": email, "password": pw, "name": "T", "role": "editor"})
        assert r.status_code == 200, r.text
        # login as editor
        s = requests.Session()
        r2 = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw})
        assert r2.status_code == 200
        # editor tries to create user -> 403
        r3 = s.post(f"{BASE}/api/users", json={"email": "TEST_x@x.com", "password": "p", "role": "editor"})
        assert r3.status_code == 403
        # editor tries GET /api/users -> 403
        r4 = s.get(f"{BASE}/api/users")
        assert r4.status_code == 403
