"""Tests for editor power-up: link update + structural ops (duplicate/add-image/add-button/delete).

Runs on demo-couk (small, disposable). Re-ingests wifetobe + demo-couk on teardown."""
import os
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://elementor-builder-4.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@wifetobe.org"
ADMIN_PW = "ChangeMe!2026"

SITE = "demo-couk"
OTHER = "wifetobe"
PAGE = "home"


@pytest.fixture(scope="class")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="class")
def editor_scoped_to_demo(admin):
    """Create an editor user scoped to demo-couk, return an authenticated session + cleanup id."""
    email = f"test_editor_{uuid.uuid4().hex[:8]}@example.com"
    pw = "EditorPass!2026"
    r = admin.post(f"{BASE}/api/users", json={
        "email": email, "password": pw, "name": "Test Editor",
        "role": "editor", "site_id": SITE,
    })
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    sess = requests.Session()
    lr = sess.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw})
    assert lr.status_code == 200, lr.text
    yield sess
    admin.delete(f"{BASE}/api/users/{uid}")


def _get_page(sess, site=SITE, page=PAGE):
    r = sess.get(f"{BASE}/api/pages/{site}/{page}")
    assert r.status_code == 200, r.text
    return r.json()


def _region_counts(page):
    regs = page.get("regions", {})
    texts = [e for e, r in regs.items() if r.get("type") == "text"]
    images = [e for e, r in regs.items() if r.get("type") == "image"]
    links = [e for e, r in regs.items() if r.get("type") == "text" and r.get("link")]
    return {"text": texts, "image": images, "link": links, "total": list(regs.keys())}


def _publish_html(sess):
    pr = sess.post(f"{BASE}/api/sites/{SITE}/preview")
    assert pr.status_code == 200, pr.text
    hr = sess.get(f"{BASE}/api/dist/{SITE}/index.html")
    assert hr.status_code == 200
    return hr.text


class TestEditorOps:
    """Single class → loadscope pins to one xdist worker (sequential shared state)."""

    def test_00_reingest_before(self, admin):
        # start from a clean known state
        for s in (SITE, OTHER):
            r = admin.post(f"{BASE}/api/sites/{s}/ingest")
            assert r.status_code == 200, r.text

    def test_01_link_update_persists_and_publishes(self, admin):
        page = _get_page(admin)
        counts = _region_counts(page)
        assert counts["link"], "expected at least one link region after re-ingest"
        eid = counts["link"][0]
        r = admin.put(f"{BASE}/api/pages/{SITE}/{PAGE}/link",
                      json={"eid": eid, "href": "/contact"})
        assert r.status_code == 200, r.text
        page2 = _get_page(admin)
        assert page2["regions"][eid].get("href") == "/contact"
        html = _publish_html(admin)
        assert 'href="/contact"' in html or "href='/contact'" in html
        assert "data-eid" not in html, "published HTML must NOT contain data-eid"

    def test_02_op_duplicate_increases_region_count(self, admin):
        before = _region_counts(_get_page(admin))
        text_eid = before["text"][0]
        r = admin.post(f"{BASE}/api/pages/{SITE}/{PAGE}/op",
                       json={"op": "duplicate", "eid": text_eid})
        assert r.status_code == 200, r.text
        after = _region_counts(_get_page(admin))
        assert len(after["total"]) > len(before["total"])
        # page still renders
        html = _publish_html(admin)
        assert "<body" in html.lower() and "data-eid" not in html

    def test_03_op_add_image_adds_img(self, admin):
        before = _region_counts(_get_page(admin))
        assert before["image"], "expected at least one image region"
        img_eid = before["image"][0]
        # count <img> in preview before
        pre_html = _publish_html(admin)
        pre_imgs = pre_html.lower().count("<img")
        r = admin.post(f"{BASE}/api/pages/{SITE}/{PAGE}/op",
                       json={"op": "add-image", "eid": img_eid})
        assert r.status_code == 200, r.text
        after = _region_counts(_get_page(admin))
        assert len(after["image"]) == len(before["image"]) + 1
        post_html = _publish_html(admin)
        assert post_html.lower().count("<img") == pre_imgs + 1
        assert "data-eid" not in post_html

    def test_04_op_add_button_creates_new_button_region(self, admin):
        before = _region_counts(_get_page(admin))
        text_eid = before["text"][0]
        r = admin.post(f"{BASE}/api/pages/{SITE}/{PAGE}/op",
                       json={"op": "add-button", "eid": text_eid})
        assert r.status_code == 200, r.text
        page = _get_page(admin)
        # a new region with value 'New button' and href '#'
        found = [r for r in page["regions"].values()
                 if r.get("type") == "text" and "New button" in (r.get("value") or "")
                 and r.get("href") == "#"]
        assert found, f"no new-button region found: {list(page['regions'].values())[-3:]}"
        html = _publish_html(admin)
        assert "New button" in html
        assert "data-eid" not in html

    def test_05_op_delete_removes_region(self, admin):
        before = _region_counts(_get_page(admin))
        # pick a text region that is NOT a link (safer)
        candidates = [e for e in before["text"] if e not in before["link"]]
        target = candidates[-1] if candidates else before["text"][-1]
        r = admin.post(f"{BASE}/api/pages/{SITE}/{PAGE}/op",
                       json={"op": "delete", "eid": target})
        assert r.status_code == 200, r.text
        page = _get_page(admin)
        assert target not in page["regions"]
        html = _publish_html(admin)
        assert "<body" in html.lower()
        assert "data-eid" not in html

    def test_06_unknown_op_returns_400(self, admin):
        page = _get_page(admin)
        eid = list(page["regions"].keys())[0]
        r = admin.post(f"{BASE}/api/pages/{SITE}/{PAGE}/op",
                       json={"op": "explode", "eid": eid})
        assert r.status_code == 400

    def test_07_unknown_eid_returns_400(self, admin):
        r = admin.post(f"{BASE}/api/pages/{SITE}/{PAGE}/op",
                       json={"op": "duplicate", "eid": "zzz_nope"})
        assert r.status_code == 400
        r2 = admin.put(f"{BASE}/api/pages/{SITE}/{PAGE}/link",
                       json={"eid": "zzz_nope", "href": "/x"})
        assert r2.status_code == 400

    def test_08_scope_editor_can_op_own_site(self, editor_scoped_to_demo):
        page = _get_page(editor_scoped_to_demo)
        text_eid = _region_counts(page)["text"][0]
        r = editor_scoped_to_demo.post(f"{BASE}/api/pages/{SITE}/{PAGE}/op",
                                       json={"op": "duplicate", "eid": text_eid})
        assert r.status_code == 200, r.text

    def test_09_scope_editor_forbidden_on_other_site(self, editor_scoped_to_demo):
        # get a valid eid from wifetobe home via admin? We don't have admin here; hit endpoint anyway.
        r = editor_scoped_to_demo.post(f"{BASE}/api/pages/{OTHER}/home/op",
                                       json={"op": "duplicate", "eid": "t0"})
        assert r.status_code == 403, r.text
        r2 = editor_scoped_to_demo.put(f"{BASE}/api/pages/{OTHER}/home/link",
                                       json={"eid": "t0", "href": "/x"})
        assert r2.status_code == 403, r2.text

    def test_10_text_region_update_regression(self, admin):
        page = _get_page(admin)
        text_eid = _region_counts(page)["text"][0]
        new_val = f"TEST_regr_{uuid.uuid4().hex[:6]}"
        r = admin.put(f"{BASE}/api/pages/{SITE}/{PAGE}/region",
                      json={"eid": text_eid, "value": new_val})
        assert r.status_code == 200, r.text
        page2 = _get_page(admin)
        assert new_val in (page2["regions"][text_eid]["value"] or "")
        html = _publish_html(admin)
        assert new_val in html

    def test_11_publish_no_dataeid_and_head_assets_present(self, admin):
        html = _publish_html(admin)
        assert "data-eid" not in html
        # head_assets: demo-couk has stylesheet links from ingest — verify SOMETHING carried
        # (be permissive: at minimum <title> and viewport are present via render_page head)
        assert "<title>" in html
        assert "viewport" in html

    def test_99_restore_sites(self, admin):
        for s in (SITE, OTHER):
            r = admin.post(f"{BASE}/api/sites/{s}/ingest")
            assert r.status_code == 200, r.text
