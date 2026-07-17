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
        <div className="brand">Website <span>Editor</span></div>
        <p className="sub">Sign in to edit your site</p>
        <input data-testid="login-email" placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)} />
        <input data-testid="login-password" type="password" placeholder="Password" value={pw} onChange={e=>setPw(e.target.value)} />
        {err && <div className="err" data-testid="login-error">{err}</div>}
        <button data-testid="login-submit" disabled={busy}>{busy ? "Signing in…" : "Sign In"}</button>
      </form>
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

function AdminSettings({ onClose, flash }) {
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
      {tab === "sites" && <SitesTab flash={flash} />}
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
  const [f, setF] = useState({ host: "", port: 22, username: "", password: "", remote_path: "/public_html" });
  const [hasPw, setHasPw] = useState(false);
  useEffect(() => { axios.get(`${API}/sites`).then(r => { setSites(r.data); if (r.data[0]) setSlug(r.data[0].slug); }); }, []);
  useEffect(() => {
    if (!slug) return;
    axios.get(`${API}/sites/${slug}/sftp`).then(r => {
      setF({ host: r.data.host, port: r.data.port, username: r.data.username, password: "", remote_path: r.data.remote_path });
      setHasPw(r.data.has_password);
    });
  }, [slug]);
  const save = async () => {
    await axios.put(`${API}/sites/${slug}/sftp`, f);
    flash("SFTP settings saved"); setHasPw(!!f.password || hasPw);
  };
  return (
    <div className="admin-form">
      <label>Site</label>
      <select data-testid="sftp-site" value={slug} onChange={e => setSlug(e.target.value)}>
        {sites.map(s => <option key={s.slug} value={s.slug}>{s.name || s.slug}</option>)}
      </select>
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
      <button className="btn primary" data-testid="sftp-save" disabled={!slug} onClick={save}>Save SFTP settings</button>
    </div>
  );
}

function SitesTab({ flash }) {
  const [avail, setAvail] = useState([]);
  const [busy, setBusy] = useState("");
  const load = () => axios.get(`${API}/available-sites`).then(r => setAvail(r.data));
  useEffect(() => { load(); }, []);
  const ingest = async (slug) => {
    setBusy(slug);
    try { const { data } = await axios.post(`${API}/sites/${slug}/ingest`); flash(`Ingested ${data.ingested} pages`); load(); }
    catch (e) { flash("Ingest failed"); }
    finally { setBusy(""); }
  };
  return (
    <div>
      <p className="hint">Drop a built static site folder into the app's <code>sites_source</code> directory and it will appear here to ingest.</p>
      <div className="admin-list" data-testid="available-sites">
        {avail.length === 0 && <div className="muted">No source sites found.</div>}
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

function Dashboard() {
  const { user, logout } = useAuth();
  const [site, setSite] = useState(null);
  const [pages, setPages] = useState([]);
  const [editing, setEditing] = useState(null);
  const [toast, setToast] = useState("");
  const [modal, setModal] = useState(null);

  const loadSite = useCallback(() => {
    axios.get(`${API}/sites`).then(r => {
      const s = r.data[0]; setSite(s); setPages(s ? s.order : []);
    });
  }, []);
  useEffect(() => { loadSite(); }, [loadSite]);

  const flash = (m) => { setToast(m); setTimeout(() => setToast(""), 4000); };

  const publish = async () => {
    flash("Publishing…");
    const { data } = await axios.post(`${API}/sites/${site.slug}/publish`);
    flash(data.message || (data.published ? "Published!" : "Done"));
  };
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
    flash("Page deleted"); loadSite();
  };

  if (editing) return <Editor site={site.slug} page={editing} onBack={() => setEditing(null)} flash={flash} />;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Website <span>Editor</span></div>
        <div className="topbar-right">
          {user.role === "admin" && <button className="btn ghost" data-testid="admin-settings-btn" onClick={() => setModal("admin")}>Admin settings</button>}
          <span className="who" data-testid="current-user">{user.email} · {user.role}</span>
          <button className="btn ghost" data-testid="logout-btn" onClick={logout}>Logout</button>
        </div>
      </header>
      <div className="dash">
        <div className="dash-head">
          <div>
            <h1>{site?.name || "Site"}</h1>
            <p className="muted">{pages.length} pages · click a page to edit it live</p>
          </div>
          <div className="actions">
            <button className="btn" data-testid="add-page-btn" onClick={() => setModal("addpage")}>+ New page</button>
            <button className="btn" data-testid="version-history-btn" onClick={() => setModal("versions")}>Version history</button>
            <button className="btn" data-testid="preview-btn" onClick={preview}>Preview</button>
            <button className="btn primary" data-testid="publish-btn" onClick={publish}>Publish to Hostinger</button>
          </div>
        </div>
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
      {modal === "addpage" && site && <AddPageModal site={site.slug} flash={flash} onClose={() => setModal(null)} onDone={() => { setModal(null); loadSite(); }} />}
      {modal === "versions" && site && <VersionHistory site={site.slug} flash={flash} onClose={() => setModal(null)} />}
      {modal === "admin" && <AdminSettings flash={flash} onClose={() => setModal(null)} />}
      {toast && <div className="toast" data-testid="toast">{toast}</div>}
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
