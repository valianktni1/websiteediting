import React, { useState, useEffect, useRef, createContext, useContext, useCallback } from "react";
import axios from "axios";
import Cropper from "react-easy-crop";
import { UI_BUILD } from "./version";
import "./App.css";

function loadImg(src) {
  return new Promise((res, rej) => {
    const i = new Image(); i.crossOrigin = "anonymous";
    i.onload = () => res(i); i.onerror = rej; i.src = src;
  });
}
async function getCroppedBlob(src, area) {
  const img = await loadImg(src);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(area.width); canvas.height = Math.round(area.height);
  canvas.getContext("2d").drawImage(img, area.x, area.y, area.width, area.height, 0, 0, area.width, area.height);
  return new Promise(res => canvas.toBlob(b => res(b), "image/jpeg", 0.9));
}
async function autoCropToAspect(file, aspect) {
  const url = URL.createObjectURL(file);
  try {
    const img = await loadImg(url);
    const sw = img.naturalWidth, sh = img.naturalHeight, ar = aspect || 1;
    let cw = sw, ch = Math.round(sw / ar);
    if (ch > sh) { ch = sh; cw = Math.round(sh * ar); }
    const sx = Math.round((sw - cw) / 2), sy = Math.round((sh - ch) / 2);
    const canvas = document.createElement("canvas"); canvas.width = cw; canvas.height = ch;
    canvas.getContext("2d").drawImage(img, sx, sy, cw, ch, 0, 0, cw, ch);
    return await new Promise(res => canvas.toBlob(b => res(b), "image/jpeg", 0.9));
  } finally { URL.revokeObjectURL(url); }
}

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
  const [api, setApi] = useState("…");
  useEffect(() => {
    axios.get(`${API}/version`).then(r => setApi(r.data.version)).catch(() => setApi("offline"));
  }, []);
  const stale = api !== "…" && api !== "offline" && api !== UI_BUILD;
  return (
    <footer className="site-footer" data-testid="app-footer">
      Hosted &amp; powered by <b>Ivory Digital</b> · Weddings by Mark
      <span
        data-testid="build-stamp"
        title={stale ? "UI and API builds differ — rebuild the stale container" : "Running build"}
        style={{ display: "block", marginTop: 6, fontSize: 11, opacity: 0.7, color: stale ? "#c0392b" : "inherit" }}
      >
        Build · UI {UI_BUILD} · API {api}{stale ? " ⚠️ mismatch — rebuild needed" : ""}
      </span>
    </footer>
  );
}

function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState(""); const [pw, setPw] = useState("");
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [brand, setBrand] = useState({ name: "Ivory Digital", logo: "", custom: false });
  useEffect(() => {
    axios.get(`${API}/branding`, { params: { host: window.location.hostname } })
      .then(r => { if (r.data) setBrand(r.data); }).catch(() => {});
  }, []);
  const submit = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { await login(email, pw); }
    catch (e) { setErr(e.response?.data?.detail || "Login failed"); }
    finally { setBusy(false); }
  };
  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit} data-testid="login-form">
        {brand.custom && brand.logo ? (
          <img className="brand-logo" data-testid="brand-logo"
            src={`${process.env.REACT_APP_BACKEND_URL}${brand.logo}`} alt={brand.name} />
        ) : (
          <div className="brand">Ivory Digital <span>Editor</span></div>
        )}
        <p className="sub" data-testid="brand-name">
          {brand.custom ? `${brand.name} · Sign in to edit your site` : "Sign in to edit your site"}
        </p>
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
  const [mode, setMode] = useState("blank");
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState("");
  const [enquiryEmail, setEnquiryEmail] = useState("");
  useEffect(() => {
    axios.get(`${API}/templates`).then(r => { setTemplates(r.data); if (r.data[0]) setTemplateId(r.data[0].id); }).catch(() => {});
  }, []);
  const slugFromTitle = (t) => t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const submit = async () => {
    setErr(""); setBusy(true);
    try {
      const finalSlug = (slug || slugFromTitle(title));
      if (mode === "template") {
        if (!templateId) { setErr("Pick a template"); setBusy(false); return; }
        await axios.post(`${API}/pages/${site}/from-template`, { template_id: templateId, slug: finalSlug, title, enquiry_email: enquiryEmail });
      } else {
        await axios.post(`${API}/pages/${site}`, { slug: finalSlug, title });
      }
      flash("Page created"); onDone();
    } catch (e) { setErr(e.response?.data?.detail || "Could not create page"); }
    finally { setBusy(false); }
  };
  const isUsedCars = mode === "template" && templates.find(t => t.id === templateId)?.name?.toLowerCase().includes("car");
  return (
    <Modal title="Add a new page" onClose={onClose}>
      <div className="seg" data-testid="addpage-mode">
        <button className={`seg-btn ${mode === "blank" ? "on" : ""}`} data-testid="mode-blank" onClick={() => setMode("blank")}>Copy of Home</button>
        <button className={`seg-btn ${mode === "template" ? "on" : ""}`} data-testid="mode-template" onClick={() => setMode("template")}>From a template</button>
      </div>
      {mode === "blank" ? (
        <p className="hint">A new page is created as a copy of your Home page so it already has your header, footer and styling — just edit the content.</p>
      ) : (
        <p className="hint">A ready-made page design. It automatically takes on this site's header, footer, colours and fonts.</p>
      )}
      {mode === "template" && (
        <>
          <label>Template</label>
          <select data-testid="addpage-template" value={templateId} onChange={e => setTemplateId(e.target.value)}>
            {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          {templateId && <div className="hint" style={{ marginTop: 4 }}>{templates.find(t => t.id === templateId)?.description}</div>}
          {isUsedCars && (
            <>
              <label>Enquiry email (where car enquiries are sent)</label>
              <input data-testid="addpage-enquiry-email" value={enquiryEmail} placeholder="sales@yourgarage.co.uk" onChange={e => setEnquiryEmail(e.target.value)} />
            </>
          )}
        </>
      )}
      <label>Page title</label>
      <input data-testid="addpage-title" value={title} placeholder="e.g. Used Cars"
        onChange={e => { setTitle(e.target.value); setSlug(slugFromTitle(e.target.value)); }} />
      <label>Page URL</label>
      <div className="slug-row"><span>/</span>
        <input data-testid="addpage-slug" value={slug} placeholder="used-cars"
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

function VersionHistory({ site, onClose, flash, onRestored }) {
  const [snaps, setSnaps] = useState(null);
  const [busy, setBusy] = useState("");
  const [saving, setSaving] = useState(false);
  const load = useCallback(() => {
    axios.get(`${API}/sites/${site}/snapshots`).then(r => setSnaps(r.data));
  }, [site]);
  useEffect(() => { load(); }, [load]);
  const saveNow = async () => {
    setSaving(true);
    try { await axios.post(`${API}/sites/${site}/snapshots`, { label: "Manual restore point" }); flash("Restore point saved"); load(); }
    catch (e) { flash("Could not save restore point"); }
    finally { setSaving(false); }
  };
  const restore = async (s) => {
    if (!window.confirm(`Roll back "${site}" to this restore point?\n\n${s.label} — ${fmt(s.created)}\n\nYour current version is saved first, so you can undo this too. You'll then Publish to push it live.`)) return;
    setBusy(s.id);
    try {
      const { data } = await axios.post(`${API}/sites/${site}/snapshots/${s.id}/restore`);
      flash(`Rolled back to "${data.label}" (${data.pages} pages). Publish to push it live.`);
      onRestored && onRestored();
      load();
    } catch (e) { flash("Rollback failed"); }
    finally { setBusy(""); }
  };
  const fmt = (iso) => {
    const d = new Date(iso); const now = new Date();
    const mins = Math.round((now - d) / 60000);
    let rel = "";
    if (mins < 1) rel = "just now";
    else if (mins < 60) rel = `${mins} min ago`;
    else if (mins < 1440) rel = `${Math.round(mins / 60)} hr ago`;
    else rel = `${Math.round(mins / 1440)} days ago`;
    return `${d.toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} · ${rel}`;
  };
  const badge = (k) => k === "import" ? "Start point" : k === "pre-publish" ? "Before publish" : k === "manual" ? "Saved by you" : "Auto-saved";
  const badgeCls = (k) => k === "import" ? "b-start" : k === "manual" ? "b-manual" : k === "pre-publish" ? "b-pub" : "b-auto";
  return (
    <Modal title="Restore points" onClose={onClose} wide>
      <div className="version-top">
        <p className="hint">Every edit session, every publish, and your original import are saved here. Pick any point to roll the whole site back to how it was then — nothing is lost, and the rollback itself is undoable.</p>
        <button className="btn primary" data-testid="save-restore-point" disabled={saving} onClick={saveNow}>{saving ? "Saving…" : "Save a restore point now"}</button>
      </div>
      {snaps === null && <div className="muted">Loading…</div>}
      {snaps && snaps.length === 0 && <div className="muted" data-testid="no-snapshots">No restore points yet — they'll build up as you edit.</div>}
      <div className="version-list" data-testid="version-list">
        {snaps && snaps.map(s => (
          <div className="version-row" key={s.id} data-testid={`snapshot-${s.id}`}>
            <div>
              <div className="version-date"><span className={`vbadge ${badgeCls(s.kind)}`}>{badge(s.kind)}</span> {s.label}</div>
              <div className="version-meta">{fmt(s.created)} · {s.pages} pages</div>
            </div>
            <button className="btn" disabled={busy === s.id} data-testid={`restore-${s.id}`} onClick={() => restore(s)}>
              {busy === s.id ? "Rolling back…" : "Roll back to here"}
            </button>
          </div>
        ))}
      </div>
    </Modal>
  );
}

function AdminSettings({ onClose, flash, onSitesChanged, user }) {
  const [tab, setTab] = useState("users");
  return (
    <Modal title="Admin settings" onClose={onClose} wide>
      <div className="tabs">
        <button className={`tab ${tab === "users" ? "on" : ""}`} data-testid="tab-users" onClick={() => setTab("users")}>Users</button>
        <button className={`tab ${tab === "sftp" ? "on" : ""}`} data-testid="tab-sftp" onClick={() => setTab("sftp")}>Hostinger SFTP</button>
        <button className={`tab ${tab === "sites" ? "on" : ""}`} data-testid="tab-sites" onClick={() => setTab("sites")}>Sites</button>
        <button className={`tab ${tab === "branding" ? "on" : ""}`} data-testid="tab-branding" onClick={() => setTab("branding")}>Branding</button>
        <button className={`tab ${tab === "templates" ? "on" : ""}`} data-testid="tab-templates" onClick={() => setTab("templates")}>Templates</button>
      </div>
      {tab === "users" && <UsersTab flash={flash} />}
      {tab === "sftp" && <SftpTab flash={flash} />}
      {tab === "sites" && <SitesTab flash={flash} onSitesChanged={onSitesChanged} />}
      {tab === "branding" && <BrandingTab flash={flash} />}
      {tab === "templates" && <TemplatesTab flash={flash} user={user} />}
    </Modal>
  );
}

function TemplatesTab({ flash, user }) {
  const [list, setList] = useState([]);
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState({ name: "", description: "", sections_html: "", css: "", js: "" });
  const isSuper = user?.role === "superadmin";
  const load = () => axios.get(`${API}/templates`).then(r => setList(r.data));
  useEffect(() => { load(); }, []);
  const save = async () => {
    if (!f.name.trim() || !f.sections_html.trim()) { flash("Name and HTML are required"); return; }
    await axios.post(`${API}/templates`, f);
    setF({ name: "", description: "", sections_html: "", css: "", js: "" });
    setAdding(false); flash("Template added"); load();
  };
  const del = async (id) => {
    if (!window.confirm("Delete this template?")) return;
    try { await axios.delete(`${API}/templates/${id}`); flash("Template deleted"); load(); }
    catch (e) { flash(e.response?.data?.detail || "Could not delete"); }
  };
  return (
    <div className="admin-form" data-testid="templates-tab">
      <p className="hint">Reusable page designs you can add to any site. When added, a template adopts that site's header, footer, colours and fonts automatically.</p>
      {list.map(t => (
        <div key={t.id} className="tmpl-row" data-testid={`template-${t.id}`}>
          <div>
            <div className="tmpl-name">{t.name}{t.builtin && <span className="tmpl-badge">built-in</span>}</div>
            <div className="admin-meta">{t.description}</div>
          </div>
          {isSuper && !t.builtin && <button className="btn danger" data-testid={`del-template-${t.id}`} onClick={() => del(t.id)}>Remove</button>}
        </div>
      ))}
      {isSuper && !adding && <button className="btn" data-testid="add-template-btn" style={{ marginTop: 12 }} onClick={() => setAdding(true)}>+ Add a template</button>}
      {isSuper && adding && (
        <div className="tmpl-add">
          <label>Template name</label>
          <input data-testid="tmpl-name" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} placeholder="e.g. Contact page" />
          <label>Short description</label>
          <input data-testid="tmpl-desc" value={f.description} onChange={e => setF({ ...f, description: e.target.value })} placeholder="What this page is for" />
          <label>Sections HTML (the body content — no header/footer)</label>
          <textarea data-testid="tmpl-html" rows={6} value={f.sections_html} onChange={e => setF({ ...f, sections_html: e.target.value })} placeholder="<section>…</section>" />
          <label>Component CSS (optional — use var(--brand-accent) so it adapts)</label>
          <textarea data-testid="tmpl-css" rows={4} value={f.css} onChange={e => setF({ ...f, css: e.target.value })} />
          <label>Component JS (optional)</label>
          <textarea data-testid="tmpl-js" rows={3} value={f.js} onChange={e => setF({ ...f, js: e.target.value })} />
          <div className="modal-actions">
            <button className="btn ghost" onClick={() => setAdding(false)}>Cancel</button>
            <button className="btn primary" data-testid="tmpl-save" onClick={save}>Save template</button>
          </div>
        </div>
      )}
    </div>
  );
}

function BrandingTab({ flash }) {
  const [sites, setSites] = useState([]);
  const [slug, setSlug] = useState("");
  const [f, setF] = useState({ brand_name: "", logo_url: "", subdomain: "", accent: "", accent_dark: "", on_accent: "", heading_font: "", body_font: "", font_link: "" });
  const fileRef = useRef(null);
  useEffect(() => { axios.get(`${API}/sites`).then(r => { setSites(r.data); if (r.data[0]) setSlug(r.data[0].slug); }); }, []);
  useEffect(() => { if (!slug) return; axios.get(`${API}/sites/${slug}/branding`).then(r => setF(r.data)); }, [slug]);
  const save = async () => { await axios.put(`${API}/sites/${slug}/branding`, f); flash("Branding saved"); };
  const onLogo = async (e) => {
    const file = e.target.files?.[0]; if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    const { data } = await axios.post(`${API}/media/${slug}/upload`, fd);
    setF(prev => ({ ...prev, logo_url: data.url })); flash("Logo uploaded — Save to apply"); e.target.value = "";
  };
  const logoSrc = f.logo_url ? `${process.env.REACT_APP_BACKEND_URL}/api/asset/${slug}/${f.logo_url}` : "";
  return (
    <div className="admin-form">
      <p className="hint">Give each client their own branded login screen. When they visit their site's subdomain, they'll see their logo and name instead of the default.</p>
      <label>Site</label>
      <select data-testid="brand-site" value={slug} onChange={e => setSlug(e.target.value)}>
        {sites.map(s => <option key={s.slug} value={s.slug}>{s.name || s.slug}</option>)}
      </select>
      <label>Brand name (shown on their login)</label>
      <input data-testid="brand-name-input" value={f.brand_name} placeholder="Wife To Be" onChange={e => setF({ ...f, brand_name: e.target.value })} />
      <label>Subdomain (the login host that shows this brand)</label>
      <input data-testid="brand-subdomain" value={f.subdomain} placeholder="wifetobe" onChange={e => setF({ ...f, subdomain: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") })} />
      <div className="hint" style={{ marginTop: 6 }}>e.g. if this client logs in at <code>wifetobe.editor.yourdomain.com</code>, enter <code>wifetobe</code>. The first part of the address is matched.</div>
      <label>Logo</label>
      {logoSrc && <img className="brand-logo-preview" data-testid="brand-logo-preview" src={logoSrc} alt="logo preview" />}
      <button className="btn" data-testid="brand-logo-upload" onClick={() => fileRef.current?.click()}>{f.logo_url ? "Replace logo" : "Upload logo"}</button>
      <input ref={fileRef} type="file" accept="image/*" hidden onChange={onLogo} />
      <div className="brand-tokens">
        <p className="hint" style={{ marginTop: 16 }}>Colour scheme &amp; fonts — page templates you add to this site adopt these. Auto-filled from the site on import; tweak if needed.</p>
        <div className="brand-token-grid">
          <div>
            <label>Accent colour</label>
            <div className="colour-row">
              <input type="color" data-testid="brand-accent-color" value={f.accent || "#d7a24b"} onChange={e => setF({ ...f, accent: e.target.value })} />
              <input data-testid="brand-accent-hex" value={f.accent} placeholder="#d7a24b" onChange={e => setF({ ...f, accent: e.target.value })} />
            </div>
          </div>
          <div>
            <label>Accent (dark/hover)</label>
            <div className="colour-row">
              <input type="color" data-testid="brand-accent-dark-color" value={f.accent_dark || "#b8863a"} onChange={e => setF({ ...f, accent_dark: e.target.value })} />
              <input data-testid="brand-accent-dark-hex" value={f.accent_dark} placeholder="#b8863a" onChange={e => setF({ ...f, accent_dark: e.target.value })} />
            </div>
          </div>
          <div>
            <label>Text on accent</label>
            <div className="colour-row">
              <input type="color" data-testid="brand-on-accent-color" value={f.on_accent || "#1a1205"} onChange={e => setF({ ...f, on_accent: e.target.value })} />
              <input data-testid="brand-on-accent-hex" value={f.on_accent} placeholder="#1a1205" onChange={e => setF({ ...f, on_accent: e.target.value })} />
            </div>
          </div>
        </div>
        <label>Heading font</label>
        <input data-testid="brand-heading-font" value={f.heading_font} placeholder="Sora" onChange={e => setF({ ...f, heading_font: e.target.value })} />
        <label>Body font</label>
        <input data-testid="brand-body-font" value={f.body_font} placeholder="Manrope" onChange={e => setF({ ...f, body_font: e.target.value })} />
      </div>
      <button className="btn primary" data-testid="brand-save" style={{ marginTop: 12 }} disabled={!slug} onClick={save}>Save branding</button>
    </div>
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
  const removeSite = async (slug) => {
    const typed = window.prompt(`This permanently removes "${slug}" from the editor — its pages, restore points and downloaded files.\n\n⚠️ Your LIVE Hostinger site is NOT touched.\n\nType the site ID "${slug}" to confirm:`);
    if (typed === null) return;
    if (typed !== slug) { flash("Name didn't match — nothing removed"); return; }
    setBusy(slug);
    try { const { data } = await axios.delete(`${API}/sites/${slug}`); flash(data.message || `Removed "${slug}"`); load(); onSitesChanged && onSitesChanged(); }
    catch (e) { flash(e.response?.data?.detail || "Could not remove site"); }
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
    setAdding(true); setAddMsg("… Starting…");
    try {
      const { data } = await axios.post(`${API}/sites/add`, f, { timeout: 30000 });
      const jobId = data.job_id;
      let ticks = 0;
      const poll = setInterval(async () => {
        ticks += 1;
        if (ticks > 90) { clearInterval(poll); setAdding(false); setAddMsg("✗ Timed out waiting for the pull. Check the backend logs, or try 'Test connection' first."); return; }
        try {
          const { data: s } = await axios.get(`${API}/sites/add-status/${jobId}`, { timeout: 20000 });
          const icon = s.state === "done" ? "✓ " : s.state === "error" ? "✗ " : "… ";
          setAddMsg(icon + s.message);
          if (s.state === "done" || s.state === "error") {
            clearInterval(poll); setAdding(false);
            if (s.state === "done") {
              setF({ slug: "", name: "", domain: "", host: "", port: 65002, username: "", password: "", remote_path: "" });
              load(); onSitesChanged && onSitesChanged();
            }
          }
        } catch (e) { /* keep polling */ }
      }, 2000);
    } catch (e) {
      setAddMsg("✗ " + (e.response?.data?.detail || e.message || "Could not start add-site"));
      setAdding(false);
    }
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
            <div className="row-actions">
              <button className="btn" disabled={busy === s.slug} data-testid={`ingest-${s.slug}`} onClick={() => ingest(s.slug)}>
                {busy === s.slug ? "Ingesting…" : s.ingested ? "Re-ingest" : "Ingest"}
              </button>
              {user.role === "superadmin" && (
                <button className="btn danger" disabled={busy === s.slug} data-testid={`remove-site-${s.slug}`} onClick={() => removeSite(s.slug)}>Remove</button>
              )}
            </div>
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

  useEffect(() => {
    if (!site) return;
    const key = `ivd_sess_${site.slug}`;
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, "1");
    axios.post(`${API}/sites/${site.slug}/session-snapshot`).catch(() => {});
  }, [site]);

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
              <button className="btn" data-testid="version-history-btn" onClick={() => setModal("versions")}>Restore points</button>
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
      {modal === "versions" && site && <VersionHistory site={site.slug} flash={flash} onClose={() => setModal(null)} onRestored={() => loadSites(site.slug)} />}
      {modal === "admin" && <AdminSettings user={user} flash={flash} onClose={() => setModal(null)} onSitesChanged={() => loadSites()} />}
      {modal === "publish" && site && <PublishConfirm site={site.slug} flash={flash} onClose={() => setModal(null)} />}
      {toast && <div className="toast" data-testid="toast">{toast}</div>}
      <Footer />
    </div>
  );
}

function CropModal({ file, aspect, onCancel, onDone }) {
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [area, setArea] = useState(null);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { const u = URL.createObjectURL(file); setUrl(u); return () => URL.revokeObjectURL(u); }, [file]);
  const save = async () => {
    if (!area) return;
    setBusy(true);
    const blob = await getCroppedBlob(url, area);
    onDone(blob);
  };
  return (
    <Modal title="Position your photo" onClose={onCancel}>
      <p className="hint">Drag to move and use the slider to zoom. Your photo is cropped to fit this spot so the layout stays perfect.</p>
      <div className="crop-stage" data-testid="crop-stage">
        {url && <Cropper image={url} crop={crop} zoom={zoom} aspect={aspect || 1} showGrid={false}
          onCropChange={setCrop} onZoomChange={setZoom} onCropComplete={(_, px) => setArea(px)} />}
      </div>
      <input type="range" min="1" max="3" step="0.01" value={zoom} className="crop-zoom" data-testid="crop-zoom"
        onChange={e => setZoom(parseFloat(e.target.value))} />
      <div className="modal-actions">
        <button className="btn ghost" data-testid="crop-cancel" onClick={onCancel}>Cancel</button>
        <button className="btn primary" data-testid="crop-save" disabled={busy} onClick={save}>{busy ? "Working…" : "Use photo"}</button>
      </div>
    </Modal>
  );
}

function AltModal({ site, page, eid, initial, onClose, onSaved, flash }) {
  const [alt, setAlt] = useState(initial || "");
  const [busy, setBusy] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const suggest = async () => {
    setSuggesting(true);
    try {
      const { data } = await axios.post(`${API}/pages/${site}/${page}/suggest-alt`, { eid }, { timeout: 70000 });
      if (data.ok && data.alt) setAlt(data.alt);
      else flash(data.message || "Couldn't suggest alt text");
    } catch (e) { flash("AI suggestion failed — you can still type it in"); }
    finally { setSuggesting(false); }
  };
  const save = async () => {
    setBusy(true);
    try { await axios.put(`${API}/pages/${site}/${page}/alt`, { eid, alt }); flash("Description saved"); onSaved(); }
    catch (e) { flash("Could not save description"); }
    finally { setBusy(false); }
  };
  return (
    <Modal title="Image description (alt text)" onClose={onClose}>
      <p className="hint">Describe the photo in a few words — it helps Google and screen readers understand your image and keeps your SEO strong after a swap.</p>
      <textarea className="alt-text" data-testid="alt-textarea" rows={3} value={alt}
        placeholder="e.g. Bride in a lace A-line gown at Wife To Be, Chester" onChange={e => setAlt(e.target.value)} />
      <button className="btn" data-testid="alt-suggest" disabled={suggesting} onClick={suggest}>
        {suggesting ? "✨ Thinking…" : "✨ Suggest with AI"}
      </button>
      <div className="modal-actions">
        <button className="btn ghost" onClick={onClose}>Cancel</button>
        <button className="btn primary" data-testid="alt-save" disabled={busy} onClick={save}>Save description</button>
      </div>
    </Modal>
  );
}

function StatusModal({ site, page, eid, onClose, onDone, flash }) {
  const [busy, setBusy] = useState(false);
  const set = async (op, label) => {
    setBusy(true);
    try { await axios.post(`${API}/pages/${site}/${page}/op`, { op, eid }); flash(label); onDone(); }
    catch (e) { flash("Could not update status"); setBusy(false); }
  };
  return (
    <Modal title="Car status badge" onClose={onClose}>
      <p className="hint">Show a badge on this car. Use "Sold" to keep a car on the page (with its photos) but clearly mark it as gone.</p>
      <div className="status-choices">
        <button className="btn status-sold" data-testid="status-sold" disabled={busy} onClick={() => set("status-sold", "Marked as Sold")}>SOLD</button>
        <button className="btn status-reserved" data-testid="status-reserved" disabled={busy} onClick={() => set("status-reserved", "Marked as Reserved")}>RESERVED</button>
        <button className="btn status-new" data-testid="status-new" disabled={busy} onClick={() => set("status-new", "Marked as New in")}>NEW IN</button>
      </div>
      <button className="btn" style={{ marginTop: 12, width: "100%" }} data-testid="status-clear" disabled={busy} onClick={() => set("status-clear", "Badge cleared")}>Clear badge</button>
    </Modal>
  );
}

function Editor({ site, page, onBack, flash }) {
  const iframeRef = useRef(null);
  const fileRef = useRef(null);
  const bulkFileRef = useRef(null);
  const pendingEid = useRef(null);
  const pendingAspect = useRef(1);
  const [seo, setSeo] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [nonce, setNonce] = useState(0);
  const [canUndo, setCanUndo] = useState(false);
  const [showPublish, setShowPublish] = useState(false);
  const [cropState, setCropState] = useState(null);
  const [altEdit, setAltEdit] = useState(null);
  const [statusEdit, setStatusEdit] = useState(null);
  const [fillingAlt, setFillingAlt] = useState(false);

  useEffect(() => {
    axios.get(`${API}/pages/${site}/${page}`).then(r => setSeo(r.data.seo));
    axios.get(`${API}/sites/${site}/undo-status`).then(r => setCanUndo(r.data.can_undo)).catch(() => {});
  }, [site, page]);

  const undo = async () => {
    try {
      const { data } = await axios.post(`${API}/sites/${site}/undo`);
      if (data.ok) {
        flash("Undid your last change"); setCanUndo(data.can_undo); setNonce(n => n + 1);
        axios.get(`${API}/pages/${site}/${page}`).then(r => setSeo(r.data.seo));
      } else flash(data.message || "Nothing to undo");
    } catch (e) { flash("Undo failed"); }
  };

  const fillAllAlt = async () => {
    setFillingAlt(true); flash("Scanning images…");
    try {
      const { data } = await axios.post(`${API}/pages/${site}/${page}/fill-alt`);
      if (!data.job_id) { flash(data.message || "Nothing to fill"); setFillingAlt(false); return; }
      let ticks = 0;
      const poll = setInterval(async () => {
        ticks += 1;
        if (ticks > 120) { clearInterval(poll); setFillingAlt(false); flash("Timed out — some images may still be processing."); return; }
        try {
          const { data: s } = await axios.get(`${API}/pages/${site}/${page}/fill-alt-status/${data.job_id}`);
          flash(`Writing alt text… ${s.done}/${s.total}`);
          if (s.state === "done") {
            clearInterval(poll); setFillingAlt(false);
            flash(`Added AI descriptions to ${s.filled} image${s.filled === 1 ? "" : "s"}`);
            setDirty(true); setCanUndo(true); setNonce(n => n + 1);
          }
        } catch (e) { /* keep polling */ }
      }, 2000);
    } catch (e) { flash("Could not start"); setFillingAlt(false); }
  };

  const onMessage = useCallback(async (ev) => {
    const d = ev.data || {};
    if (d.t === "text") {
      await axios.put(`${API}/pages/${site}/${page}/region`, { eid: d.eid, value: d.value });
      setDirty(true); setCanUndo(true); flash("Saved");
    } else if (d.t === "image") {
      pendingEid.current = d.eid; pendingAspect.current = d.ar || 1;
      fileRef.current?.click();
    } else if (d.t === "bulk-image") {
      pendingEid.current = d.eid; pendingAspect.current = d.ar || 1;
      bulkFileRef.current?.click();
    } else if (d.t === "alt") {
      setAltEdit({ eid: d.eid, alt: d.alt || "" });
    } else if (d.t === "status") {
      setStatusEdit({ eid: d.eid });
    } else if (d.t === "caption") {
      const cap = window.prompt("Caption shown under this photo (leave blank to show no caption):", d.caption || "");
      if (cap !== null) {
        await axios.put(`${API}/pages/${site}/${page}/caption`, { eid: d.eid, caption: cap });
        setDirty(true); setCanUndo(true); flash(cap.trim() ? "Caption saved" : "Caption removed"); setNonce(n => n + 1);
      }
    } else if (d.t === "link") {
      const url = window.prompt("Link URL (where this button/link goes):", d.href || "");
      if (url !== null) {
        await axios.put(`${API}/pages/${site}/${page}/link`, { eid: d.eid, href: url });
        setDirty(true); setCanUndo(true); flash("Link updated"); setNonce(n => n + 1);
      }
    } else if (d.t === "op") {
      if ((d.op === "delete" || d.op === "delete-block") &&
          !window.confirm(d.op === "delete-block"
            ? "Remove this whole card/block? A restore point is saved first, so you can undo it."
            : "Delete this element? It will be removed on the next publish (a backup is always kept).")) return;
      try {
        await axios.post(`${API}/pages/${site}/${page}/op`, { op: d.op, eid: d.eid, ref: d.ref });
        setDirty(true); setCanUndo(true);
        const msg = { "delete": "Deleted", "add-button": "Button added", "add-image": "Image added — click it to replace", "move-up": "Moved up", "move-down": "Moved down", "swap-image": "Photos reordered", "duplicate-block": "Card duplicated", "delete-block": "Card removed", "move-block-up": "Card moved", "move-block-down": "Card moved" }[d.op] || "Duplicated";
        flash(msg);
        setNonce(n => n + 1); // reload iframe to reflect structural change
      } catch (e) { flash(e.response?.data?.detail || "Could not apply change"); }
    }
  }, [site, page, flash]);

  useEffect(() => {
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [onMessage]);

  const onFile = (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    setCropState({ file: f, aspect: pendingAspect.current, eid: pendingEid.current });
    e.target.value = "";
  };

  const finishCrop = async (blob) => {
    const cs = cropState; setCropState(null);
    flash("Uploading image…");
    try {
      const fd = new FormData(); fd.append("file", new File([blob], "photo.jpg", { type: "image/jpeg" }));
      const { data } = await axios.post(`${API}/media/${site}/upload`, fd);
      await axios.put(`${API}/pages/${site}/${page}/region`, { eid: cs.eid, value: data.url });
      setDirty(true); setCanUndo(true); flash("Image replaced"); setNonce(n => n + 1);
    } catch (err) { flash("Could not replace image"); }
  };

  const onBulkFiles = async (e) => {
    const files = Array.from(e.target.files || []); if (!files.length) return;
    const aspect = pendingAspect.current;
    flash(`Preparing ${files.length} photo${files.length > 1 ? "s" : ""}…`);
    try {
      const urls = [];
      for (const file of files) {
        const blob = await autoCropToAspect(file, aspect);
        const fd = new FormData(); fd.append("file", new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" }));
        const { data } = await axios.post(`${API}/media/${site}/upload`, fd);
        urls.push(data.url);
      }
      await axios.post(`${API}/pages/${site}/${page}/bulk-image`, { eid: pendingEid.current, urls });
      setDirty(true); setCanUndo(true); flash(`Added ${urls.length} photo${urls.length > 1 ? "s" : ""}`);
      setNonce(n => n + 1);
    } catch (err) { flash("Could not add photos"); }
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
          <button className="btn ghost" data-testid="editor-undo" disabled={!canUndo} onClick={undo}>↶ Undo last change</button>
          {dirty && <span className="dirty">● unsaved changes will publish on next Publish</span>}
          <button className="btn primary" data-testid="editor-publish-btn" onClick={() => setShowPublish(true)}>Publish to Hostinger</button>
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
              <button className="btn" style={{ marginTop: 10 }} data-testid="fill-alt-btn" disabled={fillingAlt} onClick={fillAllAlt}>
                {fillingAlt ? "✨ Filling…" : "✨ Fill missing alt text"}
              </button>
              <div className="hint" style={{ marginTop: 6 }}>Let AI write alt text for every image on this page that doesn't have one yet.</div>
            </>
          )}
          <div className="tips">
            <h4>How to edit</h4>
            <ul>
              <li>Click any <b>text</b> and type to change it.</li>
              <li>Click an element to get a <b>toolbar</b> with actions.</li>
              <li><b>Images</b>: Replace (crop &amp; zoom to fit), "+ Add photos" for a gallery, "Alt text" (✨ AI), or "Caption" for a line under the photo.</li>
              <li><b>Reorder photos</b>: drag one photo onto another to swap them, or use ↑/↓.</li>
              <li><b>Links / buttons</b>: "Link" to change where they go.</li>
              <li><b>Duplicate</b>, <b>Delete</b>, or <b>+ Button</b> anything.</li>
              <li>Use <b>↑ Up</b> / <b>↓ Down</b> to reorder items like gallery photos.</li>
              <li>Made a mistake? Hit <b>↶ Undo last change</b> up top.</li>
              <li>Hit <b>Publish</b> on the dashboard to go live.</li>
            </ul>
          </div>
        </aside>
      </div>
      <input ref={fileRef} type="file" accept="image/*" hidden onChange={onFile} data-testid="image-input" />
      <input ref={bulkFileRef} type="file" accept="image/*" multiple hidden onChange={onBulkFiles} data-testid="bulk-image-input" />
      {showPublish && <PublishConfirm site={site} flash={flash} onClose={() => setShowPublish(false)} />}
      {cropState && <CropModal file={cropState.file} aspect={cropState.aspect} onCancel={() => setCropState(null)} onDone={finishCrop} />}
      {altEdit && <AltModal site={site} page={page} eid={altEdit.eid} initial={altEdit.alt} flash={flash}
        onClose={() => setAltEdit(null)} onSaved={() => { setAltEdit(null); setDirty(true); setCanUndo(true); setNonce(n => n + 1); }} />}
      {statusEdit && <StatusModal site={site} page={page} eid={statusEdit.eid} flash={flash}
        onClose={() => setStatusEdit(null)} onDone={() => { setStatusEdit(null); setDirty(true); setCanUndo(true); setNonce(n => n + 1); }} />}
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
