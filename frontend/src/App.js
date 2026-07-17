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

function Dashboard() {
  const { user, logout } = useAuth();
  const [site, setSite] = useState(null);
  const [pages, setPages] = useState([]);
  const [editing, setEditing] = useState(null);
  const [toast, setToast] = useState("");

  useEffect(() => {
    axios.get(`${API}/sites`).then(r => {
      const s = r.data[0]; setSite(s); setPages(s ? s.order : []);
    });
  }, []);

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

  if (editing) return <Editor site={site.slug} page={editing} onBack={() => setEditing(null)} flash={flash} />;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Website <span>Editor</span></div>
        <div className="topbar-right">
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
            <button className="btn" data-testid="preview-btn" onClick={preview}>Preview</button>
            <button className="btn primary" data-testid="publish-btn" onClick={publish}>Publish to Hostinger</button>
          </div>
        </div>
        <div className="page-grid">
          {pages.map(p => (
            <button key={p.slug} className="page-card" data-testid={`page-${p.slug}`} onClick={() => setEditing(p.slug)}>
              <div className="page-title">{p.title?.split("|")[0] || p.slug}</div>
              <div className="page-slug">/{p.slug === "home" ? "" : p.slug + "/"}</div>
              <div className="edit-cta">Edit page →</div>
            </button>
          ))}
        </div>
      </div>
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
