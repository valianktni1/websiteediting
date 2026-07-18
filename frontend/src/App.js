import React, { useState, useEffect, useRef, createContext, useContext, useCallback } from "react";
import axios from "axios";
import "./App.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
axios.defaults.withCredentials = true;

const Auth = createContext(null);
const useAuth = () => useContext(Auth);

function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    axios.get(`${API}/auth/me`).then(r => setUser(r.data)).catch(() => setUser(false)).finally(() => setLoading(false));
  }, []);
  const login = async (email, password) => {
    const { data } = await axios.post(`${API}/auth/login`, { email, password });
    setUser(data); return data;
  };
  const logout = async () => { await axios.post(`${API}/auth/logout`); setUser(false); };
  return <Auth.Provider value={{ user, loading, login, logout }}>{children}</Auth.Provider>;
}

function Footer() {
  return (
    <footer className="site-footer" data-testid="app-footer">
      Hosted &amp; powered by <b>Ivory Digital</b> · Weddings by Mark
    </footer>
  );
}

function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState(""); const [pw, setPw] = useState("");
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { await login(email, pw); }
    catch (e) { setErr(e.response?.data?.detail || "Login failed"); }
    finally { setBusy(false); }
  };
  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit} data-testid="login-form">
        <div className="brand">Ivory Digital <span>Editor</span></div>
        <p className="sub">Sign in to edit your site</p>
        <input data-testid="login-email" placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)} />
        <input data-testid="login-password" type="password" placeholder="Password" value={pw} onChange={e=>setPw(e.target.value)} />
        {err && <div className="err" data-testid="login-error">{err}</div>}
        <button data-testid="login-submit" disabled={busy}>{busy ? "Signing in…" : "Sign In"}</button>
      </form>
      <Footer />
    </div>
  );
}

function Modal({ title, onClose, children, wide }) {
  return (
    <div className="modal-overlay" onClick={onClose} data-testid="modal-overlay">
      <div className={`modal ${wide ? "wide" : ""}`} onClick={e => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="modal-x" onClick={onClose} data-testid="modal-close">×</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

function AddPageModal({ site, onClose, onDone, flash }) {
  const [title, setTitle] = useState(""); const [slug, setSlug] = useState("");
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const slugFromTitle = (t) => t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const submit = async () => {
    setErr(""); setBusy(true);
    try {
      const finalSlug = (slug || slugFromTitle(title));
      await axios.post(`${API}/pages/${site}`, { slug: finalSlug, title });
      flash("Page created"); onDone();
    } catch (e) { setErr(e.response?.data?.detail || "Could not create page"); }
    finally { setBusy(false); }
  };
  return (
    <Modal title="Add a new page" onClose={onClose}>
      <p className="hint">A new page is created as a copy of your Home page so it already has your header, footer and styling — just edit the content.</p>
      <label>Page title</label>
      <input data-testid="addpage-title" value={title} placeholder="e.g. Our Services"
        onChange={e => { setTitle(e.target.value); setSlug(slugFromTitle(e.target.value)); }} />
      <label>Page URL</label>
      <div className="slug-row"><span>/</span>
        <input data-testid="addpage-slug" value={slug} placeholder="our-services"
          onChange={e => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))} />
        <span>/</span>
      </div>
      {err && <div className="err" data-testid="addpage-error">{err}</div>}
      <div className="modal-actions">
        <button className="btn ghost" onClick={onClose}>Cancel</button>
        <button className="btn primary" data-testid="addpage-submit" disabled={busy || !title} onClick={submit}>
          {busy ? "Creating…" : "Create page"}
        </button>
      </div>
    </Modal>
  );
}

function VersionHistory({ site, onClose, flash }) {
  const [backups, setBackups] = useState(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => {
    axios.get(`${API}/sites/${site}/backups`).then(r => setBackups(r.data));
  }, [site]);
  useEffect(() => { load(); }, [load]);
  const restore = async (name) => {
    if (!window.confirm(`Roll back the live site to this version?\n${name}`)) return;
    setBusy(name);
    try {
      const { data } = await axios.post(`${API}/sites/${site}/restore`, { name });
      flash(data.message || "Restore complete");
    } catch (e) { flash("Restore failed"); }
    finally { setBusy(""); }
  };
  const fmt = (iso) => new Date(iso).toLocaleString();
  const kb = (b) => `${(b / 1024).toFixed(0)} KB`;
  return (
    <Modal title="Version history" onClose={onClose} wide>
      <p className="hint">Every time you publish, a full backup is saved. Roll back to any earlier version to restore it live.</p>
      {backups === null && <div className="muted">Loading…</div>}
      {backups && backups.length === 0 && <div className="muted" data-testid="no-backups">No backups yet — publish once to create your first restore point.</div>}
      <div className="version-list" data-testid="version-list">
        {backups && backups.map(b => (
          <div className="version-row" key={b.name} data-testid={`version-${b.name}`}>
            <div>
              <div className="version-date">{fmt(b.created)}</div>
              <div className="version-meta">{b.name} · {kb(b.size)}</div>
            </div>
            <button className="btn" disabled={busy === b.name} data-testid={`restore-${b.name}`} onClick={() => restore(b.name)}>
              {busy === b.name ? "Restoring…" : "Restore"}
            </button>
          </div>
        ))}
      </div>
    </Modal>
  );
}

function AdminSettings({ onClose, flash, onSitesChanged }) {
  const [tab, setTab] = useState("users");
  return (
    <Modal title="Admin settings" onClose={onClose} wide>
      <div className="tabs">
        <button className={`tab ${tab === "users" ? "on" : ""}`} data-testid="tab-users" onClick={() => setTab("users")}>Users</button>
        <button className={`tab ${tab === "sftp" ? "on" : ""}`} data-testid="tab-sftp" onClick={() => setTab("sftp")}>Hostinger SFTP</button>
        <button className={`tab ${tab === "sites" ? "on" : ""}`} data-testid="tab-sites" onClick={() => setTab("sites")}>Sites</button>
      </div>
      {tab === "users" && <UsersTab flash={flash} />}
      {tab === "sftp" && <SftpTab flash={flash} />}
      {tab === "sites" && <SitesTab flash={flash} onSitesChanged={onSitesChanged} />}
    </Modal>
  );
}

function UsersTab({ flash }) {
  const [users, setUsers] = useState([]);
  const [sites, setSites] = useState([]);
  const [f, setF] = useState({ email: "", password: "", name: "", role: "editor", site_id: "" });
  const [err, setErr] = useState("");
  const load = () => axios.get(`${API}/users`).then(r => setUsers(r.data));
  useEffect(() => { load(); axios.get(`${API}/sites`).then(r => setSites(r.data)); }, []);
  const create = async () => {
    setErr("");
    try {
      await axios.post(`${API}/users`, { ...f, site_id: f.site_id || null });
      setF({ email: "", password: "", name: "", role: "editor", site_id: "" });
      flash("User created"); load();
    } catch (e) { setErr(e.response?.data?.detail || "Could not create user"); }
  };
  const del = async (id) => {
    if (!window.confirm("Remove this user?")) return;
    await axios.delete(`${API}/users/${id}`); flash("User removed"); load();
  };
  return (
    <div>
      <div className="admin-list" data-testid="users-list">
        {users.map(u => (
          <div className="admin-row" key={u.id} data-testid={`user-${u.email}`}>
            <div>
              <div className="admin-title">{u.email}</div>
              <div className="admin-meta">{u.role}{u.site_id ? ` · ${u.site_id}` : ""}</div>
            </div>
            {u.role !== "admin" && <button className="btn danger" data-testid={`del-user-${u.email}`} onClick={() => del(u.id)}>Remove</button>}
          </div>
        ))}
      </div>
      <div className="admin-form">
        <h4>Add a client user</h4>
        <label>Email</label>
        <input data-testid="nu-email" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} />
        <label>Name</label>
        <input data-testid="nu-name" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} />
        <label>Temporary password</label>
        <input data-testid="nu-password" value={f.password} onChange={e => setF({ ...f, password: e.target.value })} />
        <label>Role</label>
        <select data-testid="nu-role" value={f.role} onChange={e => setF({ ...f, role: e.target.value })}>
          <option value="editor">Editor (client)</option>
          <option value="admin">Admin</option>
        </select>
        <label>Assign to site (optional)</label>
        <select data-testid="nu-site" value={f.site_id} onChange={e => setF({ ...f, site_id: e.target.value })}>
          <option value="">— none —</option>
          {sites.map(s => <option key={s.slug} value={s.slug}>{s.name || s.slug}</option>)}
        </select>
        {err && <div className="err">{err}</div>}
        <button className="btn primary" data-testid="nu-submit" disabled={!f.email || !f.password} onClick={create}>Create user</button>
      </div>
    </div>
  );
}

function SftpTab({ flash }) {
  const [sites, setSites] = useState([]);
  const [slug, setSlug] = useState("");
  const [f, setF] = useState({ host: "", port: 22, username: "", password: "", remote_path: "public_html", domain: "" });
  const [hasPw, setHasPw] = useState(false);
  useEffect(() => { axios.get(`${API}/sites`).then(r => { setSites(r.data); if (r.data[0]) setSlug(r.data[0].slug); }); }, []);
  useEffect(() => {
    if (!slug) return;
    axios.get(`${API}/sites/${slug}/sftp`).then(r => {
      setF({ host: r.data.host, port: r.data.port, username: r.data.username, password: "", remote_path: r.data.remote_path, domain: r.data.domain || "" });
      setHasPw(r.data.has_password);
    });
  }, [slug]);
  const save = async () => {
    await axios.put(`${API}/sites/${slug}/sftp`, f);
    flash("SFTP settings saved"); setHasPw(!!f.password || hasPw);
  };
  const [testMsg, setTestMsg] = useState(""); const [testing, setTesting] = useState(false);
  const test = async () => {
    setTesting(true); setTestMsg("");
    try { const { data } = await axios.post(`${API}/sites/${slug}/sftp/test`, f); setTestMsg((data.ok ? "✓ " : "✗ ") + data.message); }
    catch (e) { setTestMsg("✗ " + (e.response?.data?.detail || "Test failed")); }
    finally { setTesting(false); }
  };
  return (
    <div className="admin-form">
      <label>Site</label>
      <select data-testid="sftp-site" value={slug} onChange={e => setSlug(e.target.value)}>
        {sites.map(s => <option key={s.slug} value={s.slug}>{s.name || s.slug}</option>)}
      </select>
      <label>Locked domain 🔒</label>
      <input data-testid="sftp-domain" value={f.domain} placeholder="wifetobe.org" onChange={e => setF({ ...f, domain: e.target.value.trim().toLowerCase() })} />
      <div className="hint" style={{marginTop:6}}>Safety lock: the app will <b>refuse to publish</b> unless the remote path below contains this domain — so this site can never overwrite another.</div>
      <label>Host</label>
      <input data-testid="sftp-host" value={f.host} placeholder="ftp.yourdomain.com" onChange={e => setF({ ...f, host: e.target.value })} />
      <label>Port</label>
      <input data-testid="sftp-port" type="number" value={f.port} onChange={e => setF({ ...f, port: parseInt(e.target.value || "22") })} />
      <label>Username</label>
      <input data-testid="sftp-user" value={f.username} onChange={e => setF({ ...f, username: e.target.value })} />
      <label>Password {hasPw && <span className="muted">(saved — leave blank to keep)</span>}</label>
      <input data-testid="sftp-pass" type="password" value={f.password} onChange={e => setF({ ...f, password: e.target.value })} />
      <label>Remote path</label>
      <input data-testid="sftp-path" value={f.remote_path} onChange={e => setF({ ...f, remote_path: e.target.value })} />
      <div className="hint" style={{marginTop:8}}>⚠️ Use the <b>full path to this site's own folder</b>, e.g.<br/>
        <code>/home/USERNAME/domains/DOMAIN.com/public_html</code><br/>
        A bare <code>public_html</code> points at your account's <b>primary</b> domain and can overwrite the wrong site. Always run <b>Test connection</b> and check the folder it reports before publishing.</div>
      {testMsg && <div className={`test-msg ${testMsg.startsWith("✓") ? "ok" : "bad"}`} data-testid="sftp-test-result">{testMsg}</div>}
      <div className="sftp-btns">
        <button className="btn" data-testid="sftp-test" disabled={!slug || testing} onClick={test}>{testing ? "Testing…" : "Test connection"}</button>
        <button className="btn primary" data-testid="sftp-save" disabled={!slug} onClick={save}>Save SFTP settings</button>
      </div>
    </div>
  );
}

function SitesTab({ flash, onSitesChanged }) {
  const { user } = useAuth();
  const [avail, setAvail] = useState([]);
  const [busy, setBusy] = useState("");
  const load = () => axios.get(`${API}/available-sites`).then(r => setAvail(r.data));
  useEffect(() => { load(); }, []);
  const ingest = async (slug) => {
    setBusy(slug);
    try { const { data } = await axios.post(`${API}/sites/${slug}/ingest`); flash(`Ingested ${data.ingested} pages`); load(); onSitesChanged && onSitesChanged(); }
    catch (e) { flash("Ingest failed"); }
    finally { setBusy(""); }
  };

  const [f, setF] = useState({ slug: "", name: "", domain: "", host: "", port: 65002, username: "", password: "", remote_path: "" });
  const [adding, setAdding] = useState(false);
  const [addMsg, setAddMsg] = useState("");
  const [testing, setTesting] = useState(false);
  const testAdd = async () => {
    setTesting(true); setAddMsg("");
    try {
      const { data } = await axios.post(`${API}/sftp/test`, f, { timeout: 60000 });
      setAddMsg((data.ok ? "✓ " : "✗ ") + data.message);
    } catch (e) { setAddMsg("✗ " + (e.response?.data?.detail || e.message || "Test failed")); }
    finally { setTesting(false); }
  };
  const addSite = async () => {
    setAdding(true); setAddMsg("Connecting and pulling files… this can take up to a minute.");
    try {
      const { data } = await axios.post(`${API}/sites/add`, f, { timeout: 180000 });
      if (data.ok) {
        setAddMsg(`✓ Pulled ${data.pulled} files and ingested ${data.ingested} pages as "${data.slug}".`);
        setF({ slug: "", name: "", domain: "", host: "", port: 65002, username: "", password: "", remote_path: "" });
        load(); onSitesChanged && onSitesChanged();
      } else {
        setAddMsg("✗ " + data.message);
      }
    } catch (e) { setAddMsg("✗ " + (e.response?.data?.detail || e.message || "Could not add site")); }
    finally { setAdding(false); }
  };
  const missing = [!f.slug && "Short ID", !f.host && "Host", !f.username && "Username", !f.password && "Password"].filter(Boolean);

  return (
    <div>
      {user.role === "superadmin" && (
        <div className="admin-form" style={{ borderTop: "none", paddingTop: 0, marginBottom: 24 }}>
          <h4>Add a new site (pull from your server)</h4>
          <p className="hint">Enter the site's SFTP details. The app connects, downloads every file already on that server, and ingests the pages — ready to edit and publish. No uploads or redeploys.</p>
          <label>Site name</label>
          <input data-testid="as-name" value={f.name} placeholder="Wife To Be (co.uk)" onChange={e => setF({ ...f, name: e.target.value, slug: f.slug || e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") })} />
          <label>Short ID (URL-safe)</label>
          <input data-testid="as-slug" value={f.slug} placeholder="wifetobe-couk" onChange={e => setF({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") })} />
          <label>Locked domain 🔒</label>
          <input data-testid="as-domain" value={f.domain} placeholder="wifetobe.co.uk" onChange={e => setF({ ...f, domain: e.target.value.trim().toLowerCase() })} />
          <label>SFTP host</label>
          <input data-testid="as-host" value={f.host} placeholder="77.37.37.182" onChange={e => setF({ ...f, host: e.target.value })} />
          <label>Port</label>
          <input data-testid="as-port" type="number" value={f.port} onChange={e => setF({ ...f, port: parseInt(e.target.value || "65002") })} />
          <label>Username</label>
          <input data-testid="as-user" value={f.username} onChange={e => setF({ ...f, username: e.target.value })} />
          <label>Password</label>
          <input data-testid="as-pass" type="password" value={f.password} onChange={e => setF({ ...f, password: e.target.value })} />
          <label>Remote path (this site's own folder)</label>
          <input data-testid="as-path" value={f.remote_path} placeholder="/home/USER/domains/wifetobe.co.uk/public_html" onChange={e => setF({ ...f, remote_path: e.target.value })} />
          {addMsg && <div className={`test-msg ${addMsg.startsWith("✓") ? "ok" : addMsg.startsWith("✗") ? "bad" : ""}`} data-testid="as-result">{addMsg}</div>}
          <div className="sftp-btns">
            <button className="btn" data-testid="as-test" disabled={testing || adding || missing.length > 0} onClick={testAdd}>
              {testing ? "Testing…" : "Test connection"}
            </button>
            <button className="btn primary" data-testid="as-submit" disabled={adding || testing || missing.length > 0} onClick={addSite}>
              {adding ? "Pulling & ingesting…" : "Add site & pull from server"}
            </button>
          </div>
          {missing.length > 0 && <div className="hint" style={{ marginTop: 8 }}>Fill in: <b>{missing.join(", ")}</b> to enable the buttons.</div>}
        </div>
      )}
      <h4 style={{ marginBottom: 10 }}>Sites on this app</h4>
      <div className="admin-list" data-testid="available-sites">
        {avail.length === 0 && <div className="muted">No sites yet.</div>}
        {avail.map(s => (
          <div className="admin-row" key={s.slug} data-testid={`avail-${s.slug}`}>
            <div>
              <div className="admin-title">{s.slug}</div>
              <div className="admin-meta">{s.pages} pages · {s.ingested ? "ingested" : "not ingested"}</div>
            </div>
            <button className="btn" disabled={busy === s.slug} data-testid={`ingest-${s.slug}`} onClick={() => ingest(s.slug)}>
              {busy === s.slug ? "Ingesting…" : s.ingested ? "Re-ingest" : "Ingest"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function PublishConfirm({ site, onClose, flash }) {
  const [t, setT] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { axios.get(`${API}/sites/${site}/publish-target`).then(r => setT(r.data)); }, [site]);
  const go = async () => {
    setBusy(true); flash("Publishing…");
    try {
      const { data } = await axios.post(`${API}/sites/${site}/publish`);
      flash(data.message || (data.published ? "Published!" : "Done"));
    } catch (e) { flash("Publish failed"); }
    finally { setBusy(false); onClose(); }
  };
  return (
    <Modal title="Publish to Hostinger" onClose={onClose}>
      {!t && <div className="muted">Checking target…</div>}
      {t && !t.configured && (
        <>
          <p className="hint">SFTP isn't set up yet, so this will only <b>render your site and save a backup</b> — nothing is pushed live. Add your SFTP details in Admin settings to go live.</p>
          <div className="modal-actions">
            <button className="btn ghost" onClick={onClose}>Cancel</button>
            <button className="btn primary" data-testid="publish-confirm" disabled={busy} onClick={go}>{busy ? "Working…" : "Render & back up"}</button>
          </div>
        </>
      )}
      {t && t.configured && (
        <>
          <p className="hint">You're about to push <b>{t.pages} page(s)</b> live to:</p>
          <div className={`target-box ${t.path_ok ? "" : "blocked"}`} data-testid="publish-target-path">
            <div className="target-host">{t.host}{t.domain ? ` · 🔒 ${t.domain}` : ""}</div>
            <div className="target-path">{t.remote_path || "(account home)"}</div>
          </div>
          {t.path_ok ? (
            <p className="hint" style={{marginTop:12}}>⚠️ Files with the same names in that folder will be <b>overwritten</b>. Confirm this is <b>{site}</b>'s own folder. If unsure, cancel and run <b>Test connection</b> first.</p>
          ) : (
            <p className="hint bad-hint" style={{marginTop:12}} data-testid="publish-blocked">🛑 <b>Blocked:</b> the remote path does not contain this site's locked domain <b>{t.domain}</b>. Publishing is disabled to protect your other sites. Fix the path in <b>Admin → Hostinger SFTP</b> to <code>.../domains/{t.domain}/public_html</code>.</p>
          )}
          <div className="modal-actions">
            <button className="btn ghost" data-testid="publish-cancel" onClick={onClose}>Cancel</button>
            <button className="btn primary" data-testid="publish-confirm" disabled={busy || !t.path_ok} onClick={go}>{busy ? "Publishing…" : "Yes, publish to this folder"}</button>
          </div>
        </>
      )}
    </Modal>
  );
}

function Dashboard() {
  const { user, logout } = useAuth();
  const [sites, setSites] = useState([]);
  const [site, setSite] = useState(null);
  const [pages, setPages] = useState([]);
  const [editing, setEditing] = useState(null);
  const [toast, setToast] = useState("");
  const [modal, setModal] = useState(null);

  const loadSites = useCallback((preferSlug) => {
    axios.get(`${API}/sites`).then(r => {
      let list = r.data;
      if (user.role === "editor" && user.site_id) list = list.filter(s => s.slug === user.site_id);
      setSites(list);
      setSite(prev => {
        const want = preferSlug || prev?.slug;
        const found = list.find(s => s.slug === want) || list[0] || null;
        setPages(found ? found.order : []);
        return found;
      });
    });
  }, [user]);
  useEffect(() => { loadSites(); }, [loadSites]);

  const switchSite = (slug) => {
    const s = sites.find(x => x.slug === slug);
    setSite(s); setPages(s ? s.order : []);
  };

  const flash = (m) => { setToast(m); setTimeout(() => setToast(""), 4000); };

  const preview = async () => {
    flash("Building preview…");
    const { data } = await axios.post(`${API}/sites/${site.slug}/preview`);
    window.open(`${API}/dist/${site.slug}/index.html`, "_blank");
    flash(`Preview ready (${data.pages} pages)`);
  };
  const delPage = async (slug, e) => {
    e.stopPropagation();
    if (!window.confirm(`Delete the "${slug}" page? This can't be undone.`)) return;
    await axios.delete(`${API}/pages/${site.slug}/${slug}`);
    flash("Page deleted"); loadSites(site.slug);
  };
  const isAdmin = user.role === "admin" || user.role === "superadmin";

  if (editing) return <Editor site={site.slug} page={editing} onBack={() => setEditing(null)} flash={flash} />;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Ivory Digital <span>Editor</span></div>
        <div className="topbar-right">
          {isAdmin && <button className="btn ghost" data-testid="admin-settings-btn" onClick={() => setModal("admin")}>Admin settings</button>}
          <span className="who" data-testid="current-user">{user.email} · {user.role}</span>
          <button className="btn ghost" data-testid="logout-btn" onClick={logout}>Logout</button>
        </div>
      </header>
      <div className="dash">
        <div className="dash-head">
          <div>
            <div className="site-select-row">
              <h1>{site?.name || site?.slug || "No site yet"}</h1>
              {sites.length > 1 && (
                <select className="site-switcher" data-testid="site-switcher" value={site?.slug || ""} onChange={e => switchSite(e.target.value)}>
                  {sites.map(s => <option key={s.slug} value={s.slug}>{s.name || s.slug}</option>)}
                </select>
              )}
            </div>
            <p className="muted">{site?.domain ? `${site.domain} · ` : ""}{pages.length} pages · click a page to edit it live</p>
          </div>
          {site && (
            <div className="actions">
              <button className="btn" data-testid="add-page-btn" onClick={() => setModal("addpage")}>+ New page</button>
              <button className="btn" data-testid="version-history-btn" onClick={() => setModal("versions")}>Version history</button>
              <button className="btn" data-testid="preview-btn" onClick={preview}>Preview</button>
              <button className="btn primary" data-testid="publish-btn" onClick={() => setModal("publish")}>Publish to Hostinger</button>
            </div>
          )}
        </div>
        {!site && (
          <div className="empty-state" data-testid="no-site">
            <p className="muted">No sites yet.{user.role === "superadmin" ? " Open Admin settings → Sites to add one by pulling it from your server." : " Ask your administrator to set up your site."}</p>
          </div>
        )}
        <div className="page-grid">
          {pages.map(p => (
            <div key={p.slug} className="page-card" data-testid={`page-${p.slug}`} onClick={() => setEditing(p.slug)}>
              {p.slug !== "home" && (
                <button className="page-del" data-testid={`del-page-${p.slug}`} title="Delete page" onClick={(e) => delPage(p.slug, e)}>×</button>
              )}
              <div className="page-title">{p.title?.split("|")[0] || p.slug}</div>
              <div className="page-slug">/{p.slug === "home" ? "" : p.slug + "/"}</div>
              <div className="edit-cta">Edit page →</div>
            </div>
          ))}
        </div>
      </div>
      {modal === "addpage" && site && <AddPageModal site={site.slug} flash={flash} onClose={() => setModal(null)} onDone={() => { setModal(null); loadSites(site.slug); }} />}
      {modal === "versions" && site && <VersionHistory site={site.slug} flash={flash} onClose={() => setModal(null)} />}
      {modal === "admin" && <AdminSettings flash={flash} onClose={() => setModal(null)} onSitesChanged={() => loadSites()} />}
      {modal === "publish" && site && <PublishConfirm site={site.slug} flash={flash} onClose={() => setModal(null)} />}
      {toast && <div className="toast" data-testid="toast">{toast}</div>}
      <Footer />
    </div>
  );
}

function Editor({ site, page, onBack, flash }) {
  const iframeRef = useRef(null);
  const fileRef = useRef(null);
  const pendingEid = useRef(null);
  const [seo, setSeo] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    axios.get(`${API}/pages/${site}/${page}`).then(r => setSeo(r.data.seo));
  }, [site, page]);

  const onMessage = useCallback(async (ev) => {
    const d = ev.data || {};
    if (d.t === "text") {
      await axios.put(`${API}/pages/${site}/${page}/region`, { eid: d.eid, value: d.value });
      setDirty(true); flash("Saved");
    } else if (d.t === "image") {
      pendingEid.current = d.eid;
      fileRef.current?.click();
    }
  }, [site, page, flash]);

  useEffect(() => {
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [onMessage]);

  const onFile = async (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    const { data } = await axios.post(`${API}/media/${site}/upload`, fd);
    await axios.put(`${API}/pages/${site}/${page}/region`, { eid: pendingEid.current, value: data.url });
    setDirty(true); flash("Image replaced");
    setNonce(n => n + 1); // reload iframe
    e.target.value = "";
  };

  const saveSeo = async () => {
    await axios.put(`${API}/pages/${site}/${page}/seo`, { seo });
    flash("SEO saved");
  };

  return (
    <div className="editor">
      <header className="topbar">
        <button className="btn ghost" data-testid="editor-back" onClick={onBack}>← All pages</button>
        <div className="editing-label">Editing: <b>/{page === "home" ? "" : page + "/"}</b></div>
        <div className="topbar-right">
          {dirty && <span className="dirty">● unsaved changes will publish on next Publish</span>}
        </div>
      </header>
      <div className="editor-body">
        <iframe
          key={nonce}
          ref={iframeRef}
          title="page"
          className="page-frame"
          data-testid="page-frame"
          src={`${API}/editor/page/${site}/${page}?v=${nonce}`}
        />
        <aside className="panel">
          <h3>SEO</h3>
          {seo && (
            <>
              <label>Page title</label>
              <input value={seo.title || ""} onChange={e => setSeo({ ...seo, title: e.target.value })} data-testid="seo-title" />
              <label>Meta tags ({(seo.metas || []).length}) & schema preserved</label>
              <div className="hint">Meta description, Open Graph, Twitter cards and JSON-LD are kept exactly and shipped on publish.</div>
              <button className="btn" onClick={saveSeo} data-testid="save-seo">Save SEO</button>
            </>
          )}
          <div className="tips">
            <h4>How to edit</h4>
            <ul>
              <li>Click any <b>text</b> on the page and type.</li>
              <li>Click any <b>image</b> to replace it.</li>
              <li>Changes save automatically.</li>
              <li>Hit <b>Publish</b> on the dashboard to go live.</li>
            </ul>
          </div>
        </aside>
      </div>
      <input ref={fileRef} type="file" accept="image/*" hidden onChange={onFile} data-testid="image-input" />
    </div>
  );
}

function Shell() {
  const { user, loading } = useAuth();
  if (loading) return <div className="center">Loading…</div>;
  if (!user) return <Login />;
  return <Dashboard />;
}

export default function App() {
  return <AuthProvider><Shell /></AuthProvider>;
}
