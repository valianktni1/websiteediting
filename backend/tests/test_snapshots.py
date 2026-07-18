"""Content snapshot/rollback tests for Ivory CMS.

Runs against demo-couk (small, disposable). All destructive rollback tests
here — wifetobe is only touched at the very end for regression re-ingest.
"""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://elementor-builder-4.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@wifetobe.org"
ADMIN_PW = "ChangeMe!2026"
SITE = "demo-couk"
OTHER = "wifetobe"


def _login(session, email, pw):
    r = session.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    _login(s, ADMIN_EMAIL, ADMIN_PW)
    return s


@pytest.fixture(scope="module")
def editor(admin):
    # create an editor scoped to demo-couk (idempotent, ignore duplicate)
    email = "editor_demo_couk@test.local"
    pw = "EditorPass!2026"
    admin.post(f"{BASE}/api/users", json={
        "email": email, "password": pw, "name": "Demo Editor",
        "role": "editor", "site_id": SITE,
    })
    s = requests.Session()
    _login(s, email, pw)
    return s


# Keep state across tests in this class
class TestSnapshots:
    state = {}

    def test_00_ingest_demo_and_baseline(self, admin):
        r = admin.post(f"{BASE}/api/sites/{SITE}/ingest")
        assert r.status_code == 200, r.text
        assert r.json()["ingested"] >= 1
        # list snapshots
        r = admin.get(f"{BASE}/api/sites/{SITE}/snapshots")
        assert r.status_code == 200
        snaps = r.json()
        imports = [s for s in snaps if s["kind"] == "import"]
        assert len(imports) == 1, f"expected exactly one import baseline, got {len(imports)}"
        assert imports[0]["label"] == "Original (as imported)"
        TestSnapshots.state["import_id"] = imports[0]["id"]

    def test_01_reingest_does_not_duplicate_import(self, admin):
        r = admin.post(f"{BASE}/api/sites/{SITE}/ingest")
        assert r.status_code == 200
        r = admin.get(f"{BASE}/api/sites/{SITE}/snapshots")
        imports = [s for s in r.json() if s["kind"] == "import"]
        assert len(imports) == 1, f"re-ingest created extra import: {len(imports)}"

    def test_02_manual_snapshot(self, admin):
        r = admin.post(f"{BASE}/api/sites/{SITE}/snapshots", json={"label": "My checkpoint"})
        assert r.status_code == 200, r.text
        sid = r.json()["id"]
        assert sid
        r = admin.get(f"{BASE}/api/sites/{SITE}/snapshots")
        found = [s for s in r.json() if s["id"] == sid]
        assert found and found[0]["kind"] == "manual"
        assert found[0]["label"] == "My checkpoint"

    def test_03_auto_snapshot_throttled(self, admin):
        # capture snapshot count
        r = admin.get(f"{BASE}/api/sites/{SITE}/snapshots")
        before = len(r.json())
        # Get home page and its first text region eid
        r = admin.get(f"{BASE}/api/pages/{SITE}/home")
        assert r.status_code == 200
        page = r.json()
        text_eids = [eid for eid, reg in page["regions"].items() if reg.get("type") == "text"]
        assert text_eids, "no text regions on demo-couk/home"
        eid = text_eids[0]
        TestSnapshots.state["home_text_eid"] = eid
        TestSnapshots.state["home_original_value"] = page["regions"][eid]["value"]
        # Do 3 quick edits back-to-back
        for i in range(3):
            r = admin.put(f"{BASE}/api/pages/{SITE}/home/region",
                          json={"eid": eid, "value": f"quick edit {i} {uuid.uuid4().hex[:6]}"})
            assert r.status_code == 200
        # Should NOT add multiple auto snapshots — throttled to one per 10 min
        r = admin.get(f"{BASE}/api/sites/{SITE}/snapshots")
        after = len(r.json())
        added = after - before
        # 0 or 1 new auto snapshot is acceptable; more = throttle broken
        assert added <= 1, f"throttle broken: {added} snapshots added for 3 quick edits"

    def test_04_prepublish_snapshot(self, admin):
        r = admin.get(f"{BASE}/api/sites/{SITE}/snapshots")
        before_ids = {s["id"] for s in r.json()}
        r = admin.post(f"{BASE}/api/sites/{SITE}/publish")
        # publish returns normally even if SFTP not configured
        assert r.status_code == 200, r.text
        r = admin.get(f"{BASE}/api/sites/{SITE}/snapshots")
        new = [s for s in r.json() if s["id"] not in before_ids]
        pre = [s for s in new if s["kind"] == "pre-publish"]
        assert pre, f"pre-publish snapshot not created; new snaps={new}"
        assert pre[0]["label"] == "Before publishing"

    def test_05_rollback_reverts_text_edit(self, admin):
        # Restore snapshot to Original baseline
        import_id = TestSnapshots.state["import_id"]
        # First, alter the home text to a distinct value
        eid = TestSnapshots.state["home_text_eid"]
        marker = f"CHANGED_{uuid.uuid4().hex[:8]}"
        r = admin.put(f"{BASE}/api/pages/{SITE}/home/region", json={"eid": eid, "value": marker})
        assert r.status_code == 200
        r = admin.get(f"{BASE}/api/pages/{SITE}/home")
        assert r.json()["regions"][eid]["value"] == marker

        # snapshots before restore
        r = admin.get(f"{BASE}/api/sites/{SITE}/snapshots")
        before_ids = {s["id"] for s in r.json()}

        # Restore
        r = admin.post(f"{BASE}/api/sites/{SITE}/snapshots/{import_id}/restore")
        assert r.status_code == 200, r.text

        # Home should now equal original value
        r = admin.get(f"{BASE}/api/pages/{SITE}/home")
        assert r.status_code == 200
        val = r.json()["regions"][eid]["value"]
        assert val == TestSnapshots.state["home_original_value"], \
            f"rollback did not revert: got {val!r}"

        # "Before restore" auto snapshot must have been created
        r = admin.get(f"{BASE}/api/sites/{SITE}/snapshots")
        new = [s for s in r.json() if s["id"] not in before_ids]
        before_restore = [s for s in new if s.get("label") == "Before restore"]
        assert before_restore, f"'Before restore' snapshot not created; new={new}"
        TestSnapshots.state["before_restore_id"] = before_restore[0]["id"]
        TestSnapshots.state["marker"] = marker

    def test_06_rollback_is_undoable(self, admin):
        # Roll forward using "Before restore"
        br_id = TestSnapshots.state["before_restore_id"]
        r = admin.post(f"{BASE}/api/sites/{SITE}/snapshots/{br_id}/restore")
        assert r.status_code == 200
        eid = TestSnapshots.state["home_text_eid"]
        r = admin.get(f"{BASE}/api/pages/{SITE}/home")
        val = r.json()["regions"][eid]["value"]
        assert val == TestSnapshots.state["marker"], \
            f"undo rollback failed: expected {TestSnapshots.state['marker']}, got {val}"

    def test_07_structural_rollback_page_count(self, admin):
        # Baseline page count
        r = admin.get(f"{BASE}/api/sites/{SITE}/pages")
        base_pages = r.json()
        base_count = len(base_pages)
        assert base_count >= 2

        # take a snapshot as a checkpoint
        r = admin.post(f"{BASE}/api/sites/{SITE}/snapshots", json={"label": "pre-structural"})
        cp_id = r.json()["id"]

        # add a new page
        new_slug = f"tmp-{uuid.uuid4().hex[:6]}"
        r = admin.post(f"{BASE}/api/pages/{SITE}",
                       json={"slug": new_slug, "title": "Temp Page", "from_slug": "home"})
        assert r.status_code == 200
        r = admin.get(f"{BASE}/api/sites/{SITE}/pages")
        assert len(r.json()) == base_count + 1

        # rollback
        r = admin.post(f"{BASE}/api/sites/{SITE}/snapshots/{cp_id}/restore")
        assert r.status_code == 200
        r = admin.get(f"{BASE}/api/sites/{SITE}/pages")
        after = r.json()
        assert len(after) == base_count, f"page count mismatch after structural rollback: {len(after)} vs {base_count}"
        slugs = [p["slug"] for p in after]
        assert new_slug not in slugs, "new page not removed on rollback"

    def test_08_structural_rollback_addimage(self, admin):
        # snapshot before add-image
        r = admin.post(f"{BASE}/api/sites/{SITE}/snapshots", json={"label": "pre-addimage"})
        cp_id = r.json()["id"]
        r = admin.get(f"{BASE}/api/pages/{SITE}/home")
        page = r.json()
        img_eids = [eid for eid, reg in page["regions"].items() if reg.get("type") == "image"]
        if not img_eids:
            pytest.skip("no image region on home to duplicate")
        eid = img_eids[0]
        before_img_count = len(img_eids)
        r = admin.post(f"{BASE}/api/pages/{SITE}/home/op",
                       json={"op": "add-image", "eid": eid})
        assert r.status_code == 200, r.text
        r = admin.get(f"{BASE}/api/pages/{SITE}/home")
        after_img_count = len([e for e, reg in r.json()["regions"].items() if reg.get("type") == "image"])
        assert after_img_count > before_img_count, "add-image did not add an image region"

        # rollback
        r = admin.post(f"{BASE}/api/sites/{SITE}/snapshots/{cp_id}/restore")
        assert r.status_code == 200
        r = admin.get(f"{BASE}/api/pages/{SITE}/home")
        restored = len([e for e, reg in r.json()["regions"].items() if reg.get("type") == "image"])
        assert restored == before_img_count, f"image not removed on rollback: {restored} vs {before_img_count}"

    def test_09_rbac_editor_scope(self, editor):
        # editor scoped to demo-couk can list demo snapshots
        r = editor.get(f"{BASE}/api/sites/{SITE}/snapshots")
        assert r.status_code == 200, r.text
        # can create manual snapshot
        r = editor.post(f"{BASE}/api/sites/{SITE}/snapshots", json={"label": "editor cp"})
        assert r.status_code == 200
        sid = r.json()["id"]
        # can restore on demo
        r = editor.post(f"{BASE}/api/sites/{SITE}/snapshots/{sid}/restore")
        assert r.status_code == 200
        # 403 on wifetobe list/create/restore
        r = editor.get(f"{BASE}/api/sites/{OTHER}/snapshots")
        assert r.status_code == 403, f"editor should not list {OTHER}: {r.status_code}"
        r = editor.post(f"{BASE}/api/sites/{OTHER}/snapshots", json={"label": "x"})
        assert r.status_code == 403
        r = editor.post(f"{BASE}/api/sites/{OTHER}/snapshots/anyid/restore")
        assert r.status_code == 403

    def test_10_snapshot_endpoints_require_auth(self):
        r = requests.get(f"{BASE}/api/sites/{SITE}/snapshots")
        assert r.status_code == 401
        r = requests.post(f"{BASE}/api/sites/{SITE}/snapshots", json={})
        assert r.status_code == 401
        r = requests.post(f"{BASE}/api/sites/{SITE}/snapshots/whatever/restore")
        assert r.status_code == 401

    def test_99_teardown_reingest_both(self, admin):
        """Restore both sites to pristine content on disk."""
        for slug in (SITE, OTHER):
            r = admin.post(f"{BASE}/api/sites/{slug}/ingest")
            assert r.status_code == 200, f"{slug} re-ingest failed: {r.text}"
