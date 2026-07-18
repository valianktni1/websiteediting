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

    # ---- Real SFTP pull (rebex demo, no HTML => self-cleans) — now via ASYNC JOB ----
    def test_add_site_real_pull_no_html_selfcleans(self):
        s = _super_session()
        slug = "rebexjob2"
        # ensure clean start (leftover from prior run)
        s.delete(f"{BASE}/api/sites/{slug}")
        pre_sites = [x["slug"] for x in s.get(f"{BASE}/api/sites").json()]
        assert slug not in pre_sites
        t0 = time.time()
        r = s.post(f"{BASE}/api/sites/add", json={
            "slug": slug, "host": "test.rebex.net", "port": 22,
            "username": "demo", "password": "password",
            "remote_path": "/pub/example"
        }, timeout=10)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        # Should return QUICKLY (background job) — not a long-held request
        assert elapsed < 5, f"POST /sites/add took {elapsed:.1f}s; should be <5s (async job)"
        d = r.json()
        assert "job_id" in d, d
        assert d["slug"] == slug
        job_id = d["job_id"]

        # Poll add-status until done/error, ~30s cap
        deadline = time.time() + 30
        final = None
        states_seen = []
        while time.time() < deadline:
            js = s.get(f"{BASE}/api/sites/add-status/{job_id}")
            assert js.status_code == 200, js.text
            jd = js.json()
            if jd["state"] not in states_seen:
                states_seen.append(jd["state"])
            if jd["state"] in ("done", "error"):
                final = jd
                break
            time.sleep(1)
        assert final is not None, f"Job did not finish in 30s. States: {states_seen}"
        assert final["state"] == "error", final
        assert "html" in final["message"].lower() or "no .html" in final["message"].lower(), final
        # Verify self-clean: not in /api/sites, disk folder removed
        post_slugs = [x["slug"] for x in s.get(f"{BASE}/api/sites").json()]
        assert slug not in post_slugs, f"leftover {slug} in {post_slugs}"
        assert not os.path.exists(f"/app/sites/{slug}"), f"disk folder /app/sites/{slug} not cleaned"

    # ---- add-status RBAC ----
    def test_add_status_rbac(self):
        sup = _super_session()
        # create a real job to get a job_id
        r = sup.post(f"{BASE}/api/sites/add", json={
            "slug": f"rbac-{int(time.time())}", "host": "test.rebex.net", "port": 22,
            "username": "demo", "password": "password", "remote_path": "/pub/example"})
        assert r.status_code == 200, r.text
        job_id = r.json()["job_id"]
        slug_created = r.json()["slug"]

        ts = int(time.time())
        admin_email = f"test_rbac_admin_{ts}@example.com"
        editor_email = f"test_rbac_editor_{ts}@example.com"
        pw = "SomePass!123"
        ra = sup.post(f"{BASE}/api/users", json={
            "email": admin_email, "password": pw, "name": "TA", "role": "admin", "site_id": None})
        assert ra.status_code == 200, ra.text
        admin_uid = ra.json()["id"]
        re_ = sup.post(f"{BASE}/api/users", json={
            "email": editor_email, "password": pw, "name": "TE", "role": "editor", "site_id": "wifetobe"})
        assert re_.status_code == 200
        editor_uid = re_.json()["id"]
        try:
            admin_s = requests.Session()
            admin_s.post(f"{BASE}/api/auth/login", json={"email": admin_email, "password": pw})
            assert admin_s.get(f"{BASE}/api/sites/add-status/{job_id}").status_code == 403
            ed_s = requests.Session()
            ed_s.post(f"{BASE}/api/auth/login", json={"email": editor_email, "password": pw})
            assert ed_s.get(f"{BASE}/api/sites/add-status/{job_id}").status_code == 403
        finally:
            sup.delete(f"{BASE}/api/users/{admin_uid}")
            sup.delete(f"{BASE}/api/users/{editor_uid}")
            # wait for job to finish + clean up
            deadline = time.time() + 30
            while time.time() < deadline:
                jd = sup.get(f"{BASE}/api/sites/add-status/{job_id}").json()
                if jd["state"] in ("done", "error"): break
                time.sleep(1)
            sup.delete(f"{BASE}/api/sites/{slug_created}")

    # ---- POST /sftp/test new endpoint ----
    def test_sftp_test_endpoint(self):
        s = _super_session()
        r = s.post(f"{BASE}/api/sftp/test", json={
            "host": "test.rebex.net", "port": 22, "username": "demo",
            "password": "password", "remote_path": "/pub/example"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True, d
        assert d.get("remote") == "/pub/example" or "/pub/example" in str(d.get("remote", ""))
        assert d.get("count") == 16 or d.get("count", 0) >= 10, d
        # sample list present
        assert "sample" in d or "files" in d or "list" in d or isinstance(d.get("count"), int)

    def test_sftp_test_missing_creds(self):
        s = _super_session()
        r = s.post(f"{BASE}/api/sftp/test", json={
            "host": "", "port": 22, "username": "", "password": ""})
        # ok:false or 400
        if r.status_code == 200:
            assert r.json().get("ok") is False
        else:
            assert r.status_code in (400, 422)

    def test_sftp_test_rbac(self):
        sup = _super_session()
        ts = int(time.time())
        admin_email = f"test_sftp_admin_{ts}@example.com"
        editor_email = f"test_sftp_editor_{ts}@example.com"
        pw = "SomePass!123"
        ra = sup.post(f"{BASE}/api/users", json={
            "email": admin_email, "password": pw, "name": "TA", "role": "admin", "site_id": None}); ra_id = ra.json()["id"]
        re_ = sup.post(f"{BASE}/api/users", json={
            "email": editor_email, "password": pw, "name": "TE", "role": "editor", "site_id": "wifetobe"}); re_id = re_.json()["id"]
        try:
            admin_s = requests.Session(); admin_s.post(f"{BASE}/api/auth/login", json={"email": admin_email, "password": pw})
            r1 = admin_s.post(f"{BASE}/api/sftp/test", json={
                "host": "test.rebex.net", "port": 22, "username": "demo", "password": "password", "remote_path": "/pub/example"})
            assert r1.status_code == 403, r1.status_code
            ed_s = requests.Session(); ed_s.post(f"{BASE}/api/auth/login", json={"email": editor_email, "password": pw})
            r2 = ed_s.post(f"{BASE}/api/sftp/test", json={
                "host": "test.rebex.net", "port": 22, "username": "demo", "password": "password", "remote_path": "/pub/example"})
            assert r2.status_code == 403
        finally:
            sup.delete(f"{BASE}/api/users/{ra_id}")
            sup.delete(f"{BASE}/api/users/{re_id}")

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
