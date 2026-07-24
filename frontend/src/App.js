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

// Hostinger account defaults — prefilled when creating a new site (only the domain + password differ per site)
const SFTP_HOST = "77.37.37.182";
const SFTP_USER = "u897891218";
const SFTP_PORT = 65002;
const rpForDomain = (d) => (d ? `/home/${SFTP_USER}/domains/${d}/public_html` : "");

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
  const needsEmail = mode === "template" && ["used-cars", "contact"].includes(templateId);
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
          <label>Choose a template</label>
          <div className="tpl-grid" data-testid="template-grid">
            {templates.map(t => (
              <button type="button" key={t.id} data-testid={`tpl-card-${t.id}`}
                className={`tpl-card ${templateId === t.id ? "on" : ""}`}
                onClick={() => setTemplateId(t.id)}>
                <div className="tpl-thumb">
                  <img src={`/template-thumbs/${t.id}.jpg`} alt={t.name}
                    onError={e => { e.target.style.display = "none"; }} />
                </div>
                <div className="tpl-name">{t.name}{templateId === t.id && <span className="tpl-tick">✓</span>}</div>
              </button>
            ))}
          </div>
          <select data-testid="addpage-template" value={templateId} onChange={e => setTemplateId(e.target.value)} hidden readOnly>
            {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          {templateId && <div className="hint" style={{ marginTop: 8 }}>{templates.find(t => t.id === templateId)?.description}</div>}
          {needsEmail && (
            <>
              <label>{templateId === "contact" ? "Enquiry email (where messages are sent)" : "Enquiry email (where car enquiries are sent)"}</label>
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

function FindReplaceModal({ site, onClose, onDone, flash }) {
  const [find, setFind] = useState("");
  const [replace, setReplace] = useState("");
  const [matchCase, setMatchCase] = useState(true);
  const [count, setCount] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const check = async () => {
    if (!find) return;
    setBusy(true); setDone(null);
    try {
      const { data } = await axios.post(`${API}/sites/${site}/replace`, { find, replace, match_case: matchCase, dry_run: true });
      setCount(data);
    } catch (e) { flash(e.response?.data?.detail || "Could not search"); }
    finally { setBusy(false); }
  };
  const apply = async () => {
    if (!find) return;
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/sites/${site}/replace`, { find, replace, match_case: matchCase, dry_run: false });
      setDone(data); setCount(null);
      flash(`Replaced ${data.replacements} on ${data.pages} page${data.pages === 1 ? "" : "s"}`);
      onDone && onDone();
    } catch (e) { flash(e.response?.data?.detail || "Could not replace"); }
    finally { setBusy(false); }
  };
  return (
    <Modal title="Find & Replace across the whole site" onClose={onClose}>
      <p className="hint">Change a word or phrase everywhere on this site in one go — perfect for wiping a leftover name or fixing the same typo on every page. A restore point is saved first, so you can always undo it.</p>
      <label>Find this text</label>
      <input data-testid="fr-find" value={find} placeholder="e.g. Apex" onChange={e => { setFind(e.target.value); setCount(null); setDone(null); }} />
      <label>Replace with (leave empty to delete it)</label>
      <input data-testid="fr-replace" value={replace} placeholder="e.g. Ribble Valley" onChange={e => setReplace(e.target.value)} />
      <label className="check-row" style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10 }}>
        <input type="checkbox" data-testid="fr-case" checked={matchCase} onChange={e => { setMatchCase(e.target.checked); setCount(null); }} />
        Match upper/lower case exactly
      </label>
      {count && (
        <div className="hint" data-testid="fr-count" style={{ marginTop: 10 }}>
          {count.replacements > 0
            ? `Found ${count.replacements} match${count.replacements === 1 ? "" : "es"} across ${count.pages} page${count.pages === 1 ? "" : "s"}. Click Replace all to change them.`
            : `No matches for "${find}".`}
        </div>
      )}
      {done && <div className="hint" data-testid="fr-done" style={{ marginTop: 10, color: "#1f9d55" }}>✓ Replaced {done.replacements} on {done.pages} page{done.pages === 1 ? "" : "s"}. Open a page to see it, then Publish to go live.</div>}
      <div className="modal-actions">
        <button className="btn ghost" onClick={onClose}>Close</button>
        <button className="btn" data-testid="fr-check" disabled={busy || !find} onClick={check}>{busy ? "…" : "Find matches"}</button>
        <button className="btn primary" data-testid="fr-apply" disabled={busy || !find || (count && count.replacements === 0)} onClick={apply}>Replace all</button>
      </div>
    </Modal>
  );
}

function NavMenuModal({ site, onClose, flash }) {
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const dragIx = useRef(null);
  const [overIx, setOverIx] = useState(null);
  useEffect(() => {
    axios.get(`${API}/sites/${site}/nav`)
      .then(r => setItems(r.data.items.map(i => i.label)))
      .catch(() => setItems([]));
  }, [site]);
  const move = (from, to) => {
    if (to < 0 || to >= items.length) return;
    const next = items.slice();
    const [it] = next.splice(from, 1);
    next.splice(to, 0, it);
    setItems(next); setSaved(false);
  };
  const onDrop = (to) => {
    const from = dragIx.current;
    if (from !== null && from !== to) move(from, to);
    dragIx.current = null; setOverIx(null);
  };
  const save = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/sites/${site}/nav/reorder`, { order: items });
      setSaved(true); flash(`Menu order saved across ${data.pages_updated} page${data.pages_updated === 1 ? "" : "s"} — Publish to go live`);
    } catch (e) { flash(e.response?.data?.detail || "Could not save menu order"); }
    finally { setBusy(false); }
  };
  return (
    <Modal title={`Menu order — ${site}`} onClose={onClose}>
      <p className="hint">Drag the items (or use the arrows) to set the order of your navigation menu. The new order is applied to every page. Nothing goes live until you Publish.</p>
      {items === null ? <div className="hint">Loading…</div>
        : items.length < 2 ? <div className="hint">This site's menu couldn't be detected automatically, or it has fewer than two links to reorder.</div>
        : (
          <ul className="nav-reorder" data-testid="nav-reorder">
            {items.map((lbl, i) => (
              <li key={lbl + i} data-testid={`nav-item-${i}`}
                draggable
                className={overIx === i ? "over" : ""}
                onDragStart={() => { dragIx.current = i; }}
                onDragOver={e => { e.preventDefault(); setOverIx(i); }}
                onDragLeave={() => setOverIx(o => (o === i ? null : o))}
                onDrop={() => onDrop(i)}>
                <span className="grip">⋮⋮</span>
                <span className="nav-lbl">{lbl}</span>
                <span className="updown">
                  <button data-testid={`nav-up-${i}`} disabled={i === 0} onClick={() => move(i, i - 1)} title="Move up">↑</button>
                  <button data-testid={`nav-down-${i}`} disabled={i === items.length - 1} onClick={() => move(i, i + 1)} title="Move down">↓</button>
                </span>
              </li>
            ))}
          </ul>
        )}
      {saved && <div className="hint" style={{ marginTop: 10, color: "#1f9d55" }}>✓ Saved. Publish the site to push the new menu order live.</div>}
      <div className="modal-actions">
        <button className="btn ghost" onClick={onClose}>Close</button>
        <button className="btn primary" data-testid="nav-save" disabled={busy || !items || items.length < 2} onClick={save}>{busy ? "Saving…" : "Save menu order"}</button>
      </div>
    </Modal>
  );
}


function HelpModal({ onClose }) {
  return (
    <Modal title="How to use the editor" onClose={onClose} wide>
      <div className="help-guide" data-testid="help-guide">
        <p className="hint">Everything here is safe to try — every change can be undone, and nothing goes live until you hit <b>Publish</b>.</p>

        <h4>Editing text</h4>
        <ul>
          <li>Click almost any words — a heading, a paragraph, a price, a spec like <b>Year</b> or <b>Mileage</b>, even the name in your logo — and just type over them.</li>
          <li>Click away when you're done. That's it.</li>
        </ul>

        <h4>Photos</h4>
        <ul>
          <li>Click a photo, then <b>Replace</b> to swap it (you can crop &amp; zoom to fit the frame).</li>
          <li><b>+ Add photos</b> turns a single photo into a swipeable gallery — add as many as you like.</li>
          <li><b>Delete photo</b> removes just that one photo. It only removes the picture — the car or listing stays exactly where it is.</li>
          <li>Drag one photo onto another to reorder them.</li>
          <li><b>Alt text</b> describes the photo for Google — hit the ✨ button to let AI write it.</li>
        </ul>

        <h4>Car &amp; bike listings</h4>
        <ul>
          <li>Click a listing's title, price or a spec (like <b>Year</b> or <b>Mileage</b>) and type over it.</li>
          <li><b>+ Add another car</b> drops in a fresh blank "Coming soon" listing in one click — no need to copy an old one and wipe it. (On bikes it does the same thing.)</li>
          <li><b>Duplicate</b> makes a copy of a listing if you'd rather start from one you've already filled in.</li>
          <li><b>Status</b> lets you mark a listing <b>Sold</b>, <b>Reserved</b> or <b>New in</b> — a ribbon appears automatically, and Sold ones drop to the bottom of the list on your live site.</li>
          <li>Use the <b>◀ Move</b> / <b>Move ▶</b> buttons to change the order listings appear in.</li>
          <li>A <b>"From £x/mo"</b> finance estimate is added to each car automatically on the live site.</li>
          <li>The <b>Enquire about this car</b> button opens a little form that already knows which make &amp; model the customer is asking about, and sends it straight to your enquiries email.</li>
        </ul>

        <h4>Features (the little chips)</h4>
        <ul>
          <li>Each listing has a row of feature "chips" (things like <i>Heated seats</i> or <i>Reversing camera</i>). Click one and type over it.</li>
          <li><b>+ Add feature</b> adds another chip — repeat it for as many features as you want.</li>
          <li><b>Delete feature</b> removes a chip you don't need.</li>
        </ul>

        <h4>Change something everywhere</h4>
        <ul>
          <li>Use <b>Find &amp; Replace</b> (top of the dashboard) to change a word across every page at once — great for removing an old name or fixing a repeated typo.</li>
        </ul>

        <h4>Adding &amp; ordering pages</h4>
        <ul>
          <li><b>+ New page</b> creates a new page for you (you can start from a ready-made layout).</li>
          <li>On the dashboard, drag the page cards to change the order they appear in your menu.</li>
        </ul>

        <h4>Safety net</h4>
        <ul>
          <li>Made a mistake? Hit <b>↶ Undo</b> while editing.</li>
          <li><b>Restore points</b> on the dashboard roll the whole site back to how it was at any earlier moment — and even that can be undone. Nothing is ever lost.</li>
        </ul>

        <h4>Going live</h4>
        <ul>
          <li><b>Preview</b> opens your site in a new tab exactly as visitors will see it.</li>
          <li><b>Publish to Hostinger</b> pushes it live. Before it does, it shows you <b>a plain list of what's about to change</b>, and there's a <b>Preview exactly what will go live</b> button so there are no surprises.</li>
          <li>A safety lock means a site can never accidentally overwrite a different one.</li>
          <li>Changed your mind straight after publishing? Hit <b>Undo this publish</b> to put the previous version back live in one click.</li>
          <li><b>Publish history</b> (dashboard) keeps a backup of every publish — roll the live site back to any earlier version whenever you need to.</li>
        </ul>
      </div>
      <div className="modal-actions">
        <button className="btn primary" onClick={onClose}>Got it</button>
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
  const [edit, setEdit] = useState(null);
  const saveEdit = async () => {
    try {
      await axios.put(`${API}/users/${edit.id}`, { name: edit.name, role: edit.role, site_id: edit.site_id || null, password: edit.password || "" });
      flash("User updated"); setEdit(null); load();
    } catch (e) { flash(e.response?.data?.detail || "Could not update user"); }
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
            <div className="row-actions">
              <button className="btn" data-testid={`edit-user-${u.email}`} onClick={() => setEdit({ id: u.id, email: u.email, name: u.name || "", role: u.role, site_id: u.site_id || "", password: "" })}>Edit</button>
              {u.role !== "admin" && u.role !== "superadmin" && <button className="btn danger" data-testid={`del-user-${u.email}`} onClick={() => del(u.id)}>Remove</button>}
            </div>
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
      {edit && (
        <Modal title={`Edit ${edit.email}`} onClose={() => setEdit(null)}>
          <label className="modal-label">Name</label>
          <input className="modal-input" data-testid="eu-name" value={edit.name} onChange={e => setEdit({ ...edit, name: e.target.value })} />
          <label className="modal-label">Role</label>
          <select className="modal-input" data-testid="eu-role" value={edit.role} onChange={e => setEdit({ ...edit, role: e.target.value })}>
            <option value="editor">Editor (client)</option>
            <option value="admin">Admin</option>
            <option value="superadmin">Super admin</option>
          </select>
          <label className="modal-label">Assigned site</label>
          <select className="modal-input" data-testid="eu-site" value={edit.site_id} onChange={e => setEdit({ ...edit, site_id: e.target.value })}>
            <option value="">— none —</option>
            {sites.map(s => <option key={s.slug} value={s.slug}>{s.name || s.slug}</option>)}
          </select>
          <label className="modal-label">New password (leave blank to keep current)</label>
          <input className="modal-input" data-testid="eu-password" type="text" value={edit.password} placeholder="••••••••" onChange={e => setEdit({ ...edit, password: e.target.value })} />
          <div className="modal-actions">
            <button className="btn ghost" onClick={() => setEdit(null)}>Cancel</button>
            <button className="btn primary" data-testid="eu-save" onClick={saveEdit}>Save changes</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function SftpTab({ flash }) {
  const [sites, setSites] = useState([]);
  const [slug, setSlug] = useState("");
  const [f, setF] = useState({ host: "", port: 22, username: "", password: "", remote_path: "public_html", domain: "" });
  const [hasPw, setHasPw] = useState(false);
  const [clean, setClean] = useState(false);
  useEffect(() => { axios.get(`${API}/sites`).then(r => { setSites(r.data); if (r.data[0]) setSlug(r.data[0].slug); }); }, []);
  useEffect(() => {
    if (!slug) return;
    axios.get(`${API}/sites/${slug}/sftp`).then(r => {
      setF({ host: r.data.host, port: r.data.port, username: r.data.username, password: "", remote_path: r.data.remote_path, domain: r.data.domain || "" });
      setHasPw(r.data.has_password);
    });
    axios.get(`${API}/sites/${slug}/publish-target`).then(r => setClean(!!r.data.clean_urls)).catch(() => {});
  }, [slug]);
  const toggleClean = async (v) => {
    setClean(v);
    try {
      await axios.put(`${API}/sites/${slug}/clean-urls`, { enabled: v });
      flash(v ? "Clean URLs turned ON for this site — Publish to apply" : "Clean URLs turned OFF — Publish to apply");
    } catch (e) { setClean(!v); flash("Could not change Clean URLs setting"); }
  };
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
  const [pulling, setPulling] = useState(false); const [pullMsg, setPullMsg] = useState("");
  const pull = async () => {
    if (!slug) return;
    const label = sites.find(s => s.slug === slug)?.name || slug;
    if (!window.confirm(`Pull the latest files for "${label}" from Hostinger?\n\n• Downloads this site's CURRENT live files and refreshes them in the editor.\n• ⚠️ Replaces the editor copy (a restore point is saved first, so you can undo).\n• Read-only from your server — your LIVE site is NOT touched.\n\nContinue?`)) return;
    setPulling(true); setPullMsg("Connecting to your server…");
    try {
      const { data } = await axios.post(`${API}/sites/${slug}/pull`);
      const jobId = data.job_id;
      let ticks = 0;
      const poll = setInterval(async () => {
        ticks++;
        try {
          const { data: st } = await axios.get(`${API}/sites/add-status/${jobId}`);
          setPullMsg(st.message);
          if (st.state === "done") { clearInterval(poll); setPulling(false); flash(st.message); }
          else if (st.state === "error") { clearInterval(poll); setPulling(false); }
        } catch (e) { /* keep polling */ }
        if (ticks > 120) { clearInterval(poll); setPulling(false); setPullMsg("✗ Timed out waiting for the pull. Run 'Test connection' first, then try again."); }
      }, 1500);
    } catch (e) {
      setPulling(false); setPullMsg("✗ " + (e.response?.data?.detail || "Pull failed"));
    }
  };
  return (
    <div className="admin-form">
      <label>Site</label>
      <select data-testid="sftp-site" value={slug} onChange={e => setSlug(e.target.value)}>
        {sites.map(s => <option key={s.slug} value={s.slug}>{s.name || s.slug}</option>)}
      </select>
      <div className="pull-box" data-testid="pull-box" style={{marginTop:12,padding:"14px 16px",border:"1px solid rgba(198,167,94,.35)",borderRadius:10,background:"rgba(198,167,94,.06)"}}>
        <div style={{display:"flex",flexWrap:"wrap",alignItems:"center",gap:12,justifyContent:"space-between"}}>
          <div style={{minWidth:220,flex:1}}>
            <div style={{fontWeight:600}}>Pull latest from server</div>
            <div className="hint" style={{marginTop:2}}>Grabs the selected site's current files from Hostinger and refreshes the editor. Handy after you edit files directly on the server. <b>Your live site is not touched.</b></div>
          </div>
          <button className="btn primary" data-testid="sftp-pull" disabled={!slug || pulling} onClick={pull}>
            {pulling ? "Pulling…" : "⭳ Pull latest from server"}
          </button>
        </div>
        {pullMsg && <div className={`test-msg ${pullMsg.startsWith("✗") ? "bad" : "ok"}`} data-testid="sftp-pull-result" style={{marginTop:10}}>{pullMsg}</div>}
      </div>
      <label style={{marginTop:16}}>Locked domain 🔒</label>
      <input data-testid="sftp-domain" value={f.domain} placeholder="wifetobe.org" onChange={e => setF({ ...f, domain: e.target.value.trim().toLowerCase() })} />
      <div className="hint" style={{marginTop:6}}>Safety lock: the app will <b>refuse to publish</b> unless the remote path below contains this domain — so this site can never overwrite another.</div>
      <label style={{marginTop:16}}>Clean URLs</label>
      <label style={{display:"flex",alignItems:"center",gap:10,fontWeight:400,cursor:"pointer"}}>
        <input type="checkbox" data-testid="sftp-clean-urls" checked={clean} disabled={!slug} onChange={e => toggleClean(e.target.checked)} style={{width:18,height:18}} />
        <span>Publish this site with clean, extensionless URLs (e.g. <code>/about</code> instead of <code>/about.html</code>)</span>
      </label>
      <div className="hint" style={{marginTop:6}}>When on, publishing rewrites menu links, adds canonical tags, a <code>sitemap.xml</code>, and the correct <code>.htaccess</code> so old <code>.html</code> links 301-redirect to the clean version. Off by default — other sites are unaffected. Set the <b>Locked domain</b> above so canonical/sitemap URLs are correct. <b>Publish</b> to apply.</div>
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
  const [editSite, setEditSite] = useState(null);
  const [navSite, setNavSite] = useState(null);
  const load = () => axios.get(`${API}/available-sites`).then(r => setAvail(r.data));
  useEffect(() => { load(); }, []);
  const ingest = async (slug) => {
    setBusy(slug);
    try { const { data } = await axios.post(`${API}/sites/${slug}/ingest`); flash(data.added > 0 ? `Added ${data.added} new page${data.added===1?"":"s"} · kept your edits on ${data.preserved}` : `Up to date · your edits on all ${data.preserved} page${data.preserved===1?"":"s"} were kept`); load(); onSitesChanged && onSitesChanged(); }
    catch (e) { flash("Ingest failed"); }
    finally { setBusy(""); }
  };
  const reimport = async (slug) => {
    if (!window.confirm(`Re-import "${slug}" FRESH from its source files?\n\n• Rebuilds every page from the latest files — great for applying fixes.\n• ⚠️ This DISCARDS edits made in the editor (a restore point is saved first, so you can undo).\n• Your LIVE Hostinger site is not touched until you Publish.\n\nContinue?`)) return;
    setBusy(slug);
    try { const { data } = await axios.post(`${API}/sites/${slug}/ingest?force=true`); flash(`Re-imported ${data.ingested} page${data.ingested===1?"":"s"} fresh from source — review, then Publish`); load(); onSitesChanged && onSitesChanged(); }
    catch (e) { flash(e.response?.data?.detail || "Re-import failed"); }
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
  const saveSite = async () => {
    try {
      await axios.put(`${API}/sites/${editSite.slug}/meta`, { name: editSite.name, domain: editSite.domain });
      flash("Site details saved"); setEditSite(null); load(); onSitesChanged && onSitesChanged();
    } catch (e) { flash(e.response?.data?.detail || "Could not save site"); }
  };

  const [f, setF] = useState({ slug: "", name: "", domain: "", host: SFTP_HOST, port: SFTP_PORT, username: SFTP_USER, password: "", remote_path: "" });
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
              setF({ slug: "", name: "", domain: "", host: SFTP_HOST, port: SFTP_PORT, username: SFTP_USER, password: "", remote_path: "" });
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

  // ---- New site from a design (ZIP upload) ----
  const [showDesign, setShowDesign] = useState(false);
  const [df, setDf] = useState({ slug: "", name: "", domain: "", client_email: "", client_password: "", sftp_host: SFTP_HOST, sftp_port: SFTP_PORT, sftp_username: SFTP_USER, sftp_password: "", sftp_remote_path: "" });
  const [dfFile, setDfFile] = useState(null);
  const [creating, setCreating] = useState(false);
  const [dfMsg, setDfMsg] = useState("");
  const createFromDesign = async () => {
    if (!dfFile) { setDfMsg("✗ Choose a .zip of your design first."); return; }
    setCreating(true); setDfMsg("… Uploading & building…");
    try {
      const fd = new FormData();
      fd.append("file", dfFile);
      Object.entries(df).forEach(([k, v]) => fd.append(k, v));
      const { data } = await axios.post(`${API}/sites/create-from-design`, fd, { timeout: 180000 });
      setDfMsg("✓ " + data.message + (data.client_user ? ` · client login: ${data.client_user}` : "") + (data.sftp_set ? " · SFTP saved" : ""));
      setDf({ slug: "", name: "", domain: "", client_email: "", client_password: "", sftp_host: SFTP_HOST, sftp_port: SFTP_PORT, sftp_username: SFTP_USER, sftp_password: "", sftp_remote_path: "" });
      setDfFile(null);
      load(); onSitesChanged && onSitesChanged();
    } catch (e) {
      setDfMsg("✗ " + (e.response?.data?.detail || e.message || "Could not create the site"));
    } finally { setCreating(false); }
  };

  return (
    <div>
      {user.role === "superadmin" && (
        <div className="admin-form" style={{ borderTop: "none", paddingTop: 0, marginBottom: 24 }}>
          <h4>New site from a design</h4>
          <p className="hint">Upload a <b>.zip</b> of a finished site design (index.html + assets + any subfolders). The app unpacks it, ingests every page ready to edit, and can create the client login &amp; save Hostinger SFTP details in one go. Nothing is published until you press Publish.</p>
          {!showDesign
            ? <button className="btn primary" data-testid="design-open" onClick={() => setShowDesign(true)}>Create a site from a design ZIP</button>
            : (
              <div data-testid="design-form">
                <label>Design ZIP file</label>
                <input type="file" accept=".zip,application/zip" data-testid="design-file" onChange={e => setDfFile(e.target.files[0] || null)} />
                <label>Site name</label>
                <input data-testid="design-name" value={df.name} placeholder="Ribble Valley Cars" onChange={e => setDf({ ...df, name: e.target.value, slug: df.slug || e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") })} />
                <label>Short ID (URL-safe)</label>
                <input data-testid="design-slug" value={df.slug} placeholder="ribble-valley" onChange={e => setDf({ ...df, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") })} />
                <label>Locked domain 🔒 (optional)</label>
                <input data-testid="design-domain" value={df.domain} placeholder="ribblevalleycars.co.uk" onChange={e => { const dom = e.target.value.trim().toLowerCase(); setDf({ ...df, domain: dom, sftp_remote_path: rpForDomain(dom) }); }} />

                <h4 style={{ marginTop: 18 }}>Client login (optional)</h4>
                <label>Client email</label>
                <input data-testid="design-client-email" value={df.client_email} placeholder="client@theirdomain.co.uk" onChange={e => setDf({ ...df, client_email: e.target.value })} />
                <label>Client password</label>
                <input data-testid="design-client-pass" type="text" value={df.client_password} placeholder="a password to give the client" onChange={e => setDf({ ...df, client_password: e.target.value })} />

                <h4 style={{ marginTop: 18 }}>Hostinger SFTP (optional — can add later)</h4>
                <label>SFTP host</label>
                <input data-testid="design-sftp-host" value={df.sftp_host} placeholder="77.37.37.182" onChange={e => setDf({ ...df, sftp_host: e.target.value })} />
                <label>Port</label>
                <input data-testid="design-sftp-port" type="number" value={df.sftp_port} onChange={e => setDf({ ...df, sftp_port: parseInt(e.target.value || "65002") })} />
                <label>Username</label>
                <input data-testid="design-sftp-user" value={df.sftp_username} onChange={e => setDf({ ...df, sftp_username: e.target.value })} />
                <label>Password</label>
                <input data-testid="design-sftp-pass" type="password" value={df.sftp_password} onChange={e => setDf({ ...df, sftp_password: e.target.value })} />
                <label>Remote path (this site's own folder)</label>
                <input data-testid="design-sftp-path" value={df.sftp_remote_path} placeholder="/home/USER/domains/domain.co.uk/public_html" onChange={e => setDf({ ...df, sftp_remote_path: e.target.value })} />

                {dfMsg && <div className={`test-msg ${dfMsg.startsWith("✓") ? "ok" : dfMsg.startsWith("✗") ? "bad" : ""}`} data-testid="design-result">{dfMsg}</div>}
                <div className="sftp-btns">
                  <button className="btn" data-testid="design-cancel" disabled={creating} onClick={() => { setShowDesign(false); setDfMsg(""); }}>Cancel</button>
                  <button className="btn primary" data-testid="design-submit" disabled={creating || !dfFile || !df.slug} onClick={createFromDesign}>
                    {creating ? "Building…" : "Create site from design"}
                  </button>
                </div>
                {(!dfFile || !df.slug) && <div className="hint" style={{ marginTop: 8 }}>Choose a ZIP and enter a Short ID to enable Create.</div>}
              </div>
            )}
        </div>
      )}
      {user.role === "superadmin" && (
        <div className="admin-form" style={{ borderTop: "none", paddingTop: 0, marginBottom: 24 }}>
          <h4>Add a new site (pull from your server)</h4>
          <p className="hint">Enter the site's SFTP details. The app connects, downloads every file already on that server, and ingests the pages — ready to edit and publish. No uploads or redeploys.</p>
          <label>Site name</label>
          <input data-testid="as-name" value={f.name} placeholder="Wife To Be (co.uk)" onChange={e => setF({ ...f, name: e.target.value, slug: f.slug || e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") })} />
          <label>Short ID (URL-safe)</label>
          <input data-testid="as-slug" value={f.slug} placeholder="wifetobe-couk" onChange={e => setF({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") })} />
          <label>Locked domain 🔒</label>
          <input data-testid="as-domain" value={f.domain} placeholder="wifetobe.co.uk" onChange={e => { const dom = e.target.value.trim().toLowerCase(); setF({ ...f, domain: dom, remote_path: rpForDomain(dom) }); }} />
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
              <div className="admin-title">{s.name || s.slug}</div>
              <div className="admin-meta">{s.slug}{s.domain ? ` · 🔒 ${s.domain}` : ""} · {s.pages} pages · {s.ingested ? "ingested" : "not ingested"}</div>
            </div>
            <div className="row-actions">
              <button className="btn" disabled={busy === s.slug} data-testid={`ingest-${s.slug}`} onClick={() => ingest(s.slug)}>
                {busy === s.slug ? "Ingesting…" : s.ingested ? "Re-ingest" : "Ingest"}
              </button>
              {s.ingested && (
                <button className="btn" disabled={busy === s.slug} data-testid={`reimport-${s.slug}`} title="Rebuild every page from the latest source files (discards editor edits)" onClick={() => reimport(s.slug)}>Re-import fresh</button>
              )}
              <button className="btn" data-testid={`edit-site-${s.slug}`} onClick={() => setEditSite({ slug: s.slug, name: s.name || s.slug, domain: s.domain || "" })}>Edit</button>
              {s.ingested && <button className="btn" data-testid={`menu-${s.slug}`} onClick={() => setNavSite(s.slug)}>Menu</button>}
              {user.role === "superadmin" && (
                <button className="btn danger" disabled={busy === s.slug} data-testid={`remove-site-${s.slug}`} onClick={() => removeSite(s.slug)}>Remove</button>
              )}
            </div>
          </div>
        ))}
      </div>
      {editSite && (
        <Modal title={`Edit ${editSite.slug}`} onClose={() => setEditSite(null)}>
          <label className="modal-label">Site name</label>
          <input className="modal-input" data-testid="es-name" value={editSite.name} onChange={e => setEditSite({ ...editSite, name: e.target.value })} />
          <label className="modal-label">Locked domain 🔒 (optional)</label>
          <input className="modal-input" data-testid="es-domain" value={editSite.domain} placeholder="theirdomain.co.uk" onChange={e => setEditSite({ ...editSite, domain: e.target.value.trim().toLowerCase() })} />
          <div className="hint" style={{ marginTop: 8 }}>The locked domain is a safety lock — publishing is refused unless the SFTP path contains it. Set Hostinger login details in the <b>Hostinger SFTP</b> tab.</div>
          <div className="modal-actions">
            <button className="btn ghost" onClick={() => setEditSite(null)}>Cancel</button>
            <button className="btn primary" data-testid="es-save" onClick={saveSite}>Save changes</button>
          </div>
        </Modal>
      )}
      {navSite && <NavMenuModal site={navSite} flash={flash} onClose={() => setNavSite(null)} />}
    </div>
  );
}

function _pageLabel(f) {
  if (f === "index.html") return "Home";
  if (f.endsWith("/index.html")) return "/" + f.slice(0, -("index.html".length));
  if (f.endsWith(".html")) return "/" + f.slice(0, -5);
  return null;
}
function ChangeLine({ label, list, cls }) {
  if (!list || !list.length) return null;
  const pages = [], other = [];
  list.forEach(f => { const l = _pageLabel(f); if (l) pages.push(l); else other.push(f); });
  return (
    <div className={`chg-line ${cls}`} data-testid={`chg-${cls}`}>
      <span className="chg-dot" /> <b>{label}</b>{" "}
      {pages.length ? <span>{pages.join(", ")}</span> : null}
      {pages.length && other.length ? " · " : ""}
      {other.length ? <span className="muted">{other.length} supporting file{other.length === 1 ? "" : "s"} (sitemap, styles, images)</span> : null}
    </div>
  );
}

function PublishConfirm({ site, isAdmin, onClose, flash, onPublished }) {
  const [t, setT] = useState(null);
  const [chg, setChg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const [undoing, setUndoing] = useState(false);

  useEffect(() => {
    axios.get(`${API}/sites/${site}/publish-target`).then(r => setT(r.data));
    axios.get(`${API}/sites/${site}/publish-changes`).then(r => setChg(r.data)).catch(() => setChg({ error: true }));
  }, [site]);

  const total = chg && !chg.error ? (chg.changed?.length || 0) + (chg.added?.length || 0) + (chg.removed?.length || 0) : null;
  const previewChanges = () => window.open(`${API}/dist/${site}/index.html`, "_blank");

  const go = async () => {
    setBusy(true); flash("Publishing…");
    try {
      const { data } = await axios.post(`${API}/sites/${site}/publish`);
      setDone(data);
      flash(data.message || (data.published ? "Published!" : "Done"));
      onPublished && onPublished();
    } catch (e) { flash("Publish failed"); }
    finally { setBusy(false); }
  };

  const undo = async () => {
    setUndoing(true); flash("Rolling the live site back…");
    try {
      const { data } = await axios.get(`${API}/sites/${site}/backups`);
      if (!data || data.length < 2) { flash("No earlier version to roll back to yet."); setUndoing(false); return; }
      const res = await axios.post(`${API}/sites/${site}/restore`, { name: data[1].name });
      flash(res.data.message || "Live site rolled back.");
      setDone(null);
    } catch (e) { flash("Rollback failed — open Publish history to pick a version."); }
    finally { setUndoing(false); }
  };

  if (done) {
    return (
      <Modal title="Publish complete" onClose={onClose}>
        <div className="publish-done" data-testid="publish-done">
          <div className="pd-icon">{done.published ? "✓" : "•"}</div>
          <p className="hint" style={{ fontSize: 15 }}>{done.message || (done.published ? "Your site is now live." : "Done.")}</p>
        </div>
        {done.published && isAdmin && (
          <>
            <p className="hint" style={{ marginTop: 8 }}>Not happy with it? You can put the <b>previous live version</b> back in one click — visitors will see it again immediately.</p>
            <button className="btn" data-testid="undo-publish-btn" disabled={undoing} onClick={undo} style={{ marginTop: 6 }}>
              {undoing ? "Rolling back…" : "↩ Undo this publish (restore previous version)"}
            </button>
          </>
        )}
        <div className="modal-actions">
          <button className="btn primary" data-testid="publish-close" onClick={onClose}>Done</button>
        </div>
      </Modal>
    );
  }

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
          <div className="chg-summary" data-testid="change-summary">
            {!chg && <div className="muted">Working out what's changed…</div>}
            {chg && chg.error && <div className="muted">Ready to publish {t.pages} page(s).</div>}
            {chg && !chg.error && !chg.has_baseline && (
              <p className="hint"><b>First publish.</b> Your whole site ({chg.pages} page{chg.pages === 1 ? "" : "s"}) will go live.</p>
            )}
            {chg && !chg.error && chg.has_baseline && total === 0 && (
              <p className="hint" data-testid="no-changes">✓ <b>No changes since your last publish</b> — everything's already live. You can still re-publish if you like.</p>
            )}
            {chg && !chg.error && chg.has_baseline && total > 0 && (
              <>
                <p className="hint" style={{ marginBottom: 8 }}><b>Here's what will change</b> when you publish:</p>
                <ChangeLine label="Updated:" list={chg.changed} cls="chg-upd" />
                <ChangeLine label="New:" list={chg.added} cls="chg-add" />
                <ChangeLine label="Removed:" list={chg.removed} cls="chg-del" />
              </>
            )}
          </div>
          <button className="btn ghost" data-testid="preview-changes-btn" onClick={previewChanges} style={{ marginTop: 4, marginBottom: 12 }}>
            👁 Preview exactly what will go live
          </button>
          <p className="hint">Pushing <b>{t.pages} page(s)</b> to:</p>
          <div className={`target-box ${t.path_ok ? "" : "blocked"}`} data-testid="publish-target-path">
            <div className="target-host">{t.host}{t.domain ? ` · 🔒 ${t.domain}` : ""}</div>
            <div className="target-path">{t.remote_path || "(account home)"}</div>
          </div>
          {t.path_ok ? (
            <p className="hint" style={{ marginTop: 12 }}>A full backup is saved first, so this is always reversible. If unsure, cancel and run <b>Test connection</b> first.</p>
          ) : (
            <p className="hint bad-hint" style={{ marginTop: 12 }} data-testid="publish-blocked">🛑 <b>Blocked:</b> the remote path does not contain this site's locked domain <b>{t.domain}</b>. Publishing is disabled to protect your other sites. Fix the path in <b>Admin → Hostinger SFTP</b> to <code>.../domains/{t.domain}/public_html</code>.</p>
          )}
          <div className="modal-actions">
            <button className="btn ghost" data-testid="publish-cancel" onClick={onClose}>Cancel</button>
            <button className="btn primary" data-testid="publish-confirm" disabled={busy || !t.path_ok} onClick={go}>{busy ? "Publishing…" : "Publish now"}</button>
          </div>
        </>
      )}
    </Modal>
  );
}

function PublishHistory({ site, onClose, flash }) {
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(null);
  const load = () => axios.get(`${API}/sites/${site}/backups`).then(r => setItems(r.data)).catch(() => setItems([]));
  useEffect(() => { load(); }, [site]);
  const fmt = (iso) => { try { return new Date(iso).toLocaleString(); } catch { return iso; } };
  const kb = (n) => n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.round(n / 1024) + " KB";
  const restore = async (b) => {
    if (!window.confirm(`Put this version back LIVE on Hostinger?\n\n${fmt(b.created)}\n\nVisitors will see this exact version immediately. Your current live version stays saved in this list, so this is reversible too.`)) return;
    setBusy(b.name); flash("Pushing this version live…");
    try {
      const { data } = await axios.post(`${API}/sites/${site}/restore`, { name: b.name });
      flash(data.message || "Restored live.");
    } catch (e) { flash("Restore failed — check SFTP settings."); }
    finally { setBusy(null); }
  };
  return (
    <Modal title="Publish history & live rollback" onClose={onClose} wide>
      <p className="hint">Every publish saves a full backup of the exact files that went live. Roll the <b>live Hostinger site</b> back to any of these in one click — handy if a client publishes something they'd like to reverse.</p>
      {!items && <div className="muted">Loading…</div>}
      {items && items.length === 0 && <div className="muted" data-testid="no-backups">No publishes yet — backups appear here after your first publish.</div>}
      <div className="version-list">
        {items && items.map((b, i) => (
          <div className="version-row" key={b.name} data-testid={`backup-${b.name}`}>
            <div>
              <div className="version-date"><span className={`vbadge ${i === 0 ? "b-live" : "b-auto"}`}>{i === 0 ? "● Live now" : "Backup"}</span> {fmt(b.created)}</div>
              <div className="version-meta">{kb(b.size)}</div>
            </div>
            {i !== 0 && (
              <button className="btn" disabled={busy === b.name} data-testid={`restore-live-${b.name}`} onClick={() => restore(b)}>
                {busy === b.name ? "Pushing…" : "Restore this version live"}
              </button>
            )}
          </div>
        ))}
      </div>
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

  const dragPageIx = useRef(null);
  const [overPageSlug, setOverPageSlug] = useState(null);
  const reorderPages = async (from, to) => {
    if (from == null || to == null || from === to || to < 0 || to >= pages.length) return;
    const next = pages.slice();
    const [it] = next.splice(from, 1);
    next.splice(to, 0, it);
    setPages(next);
    try {
      await axios.post(`${API}/sites/${site.slug}/pages/reorder`, { order: next.map(p => p.slug) });
      flash("Page order saved");
    } catch (e) { flash("Could not save page order"); loadSites(site.slug); }
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
    flash("Page deleted"); loadSites(site.slug);
  };
  const isAdmin = user.role === "admin" || user.role === "superadmin";

  if (editing) return <Editor site={site.slug} page={editing} onBack={() => setEditing(null)} flash={flash} />;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Ivory Digital <span>Editor</span></div>
        <div className="topbar-right">
          <button className="btn ghost" data-testid="help-btn" onClick={() => setModal("help")}>Help</button>
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
              <button className="btn" data-testid="find-replace-btn" onClick={() => setModal("replace")}>Find &amp; Replace</button>
              <button className="btn" data-testid="version-history-btn" onClick={() => setModal("versions")}>Restore points</button>
              {isAdmin && <button className="btn" data-testid="publish-history-btn" onClick={() => setModal("pubhistory")}>Publish history</button>}
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
          {pages.map((p, idx) => (
            <div key={p.slug} className={`page-card ${overPageSlug === p.slug ? "drag-over" : ""}`} data-testid={`page-${p.slug}`}
              draggable
              onDragStart={(e) => { dragPageIx.current = idx; e.dataTransfer.effectAllowed = "move"; }}
              onDragOver={(e) => { e.preventDefault(); if (overPageSlug !== p.slug) setOverPageSlug(p.slug); }}
              onDragLeave={() => setOverPageSlug(s => (s === p.slug ? null : s))}
              onDrop={(e) => { e.preventDefault(); reorderPages(dragPageIx.current, idx); dragPageIx.current = null; setOverPageSlug(null); }}
              onDragEnd={() => { dragPageIx.current = null; setOverPageSlug(null); }}
              onClick={() => setEditing(p.slug)}>
              <span className="page-grip" title="Drag to reorder" onClick={(e) => e.stopPropagation()}>⋮⋮</span>
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
      {modal === "replace" && site && <FindReplaceModal site={site.slug} flash={flash} onClose={() => setModal(null)} onDone={() => loadSites(site.slug)} />}
      {modal === "help" && <HelpModal onClose={() => setModal(null)} />}
      {modal === "versions" && site && <VersionHistory site={site.slug} flash={flash} onClose={() => setModal(null)} onRestored={() => loadSites(site.slug)} />}
      {modal === "admin" && <AdminSettings user={user} flash={flash} onClose={() => setModal(null)} onSitesChanged={() => loadSites()} />}
      {modal === "publish" && site && <PublishConfirm site={site.slug} isAdmin={isAdmin} flash={flash} onClose={() => setModal(null)} />}
      {modal === "pubhistory" && site && <PublishHistory site={site.slug} flash={flash} onClose={() => setModal(null)} />}
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
  const logoFileRef = useRef(null);
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
  const [showSeo, setShowSeo] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const scrollRef = useRef(0);

  const reload = useCallback(() => {
    try { scrollRef.current = iframeRef.current?.contentWindow?.scrollY || 0; } catch (e) { scrollRef.current = 0; }
    setNonce(n => n + 1);
  }, []);
  const onFrameLoad = () => {
    const y = scrollRef.current;
    if (!y) return;
    const restore = () => { try { iframeRef.current.contentWindow.scrollTo(0, y); } catch (e) {} };
    restore(); setTimeout(restore, 120); setTimeout(restore, 320);
  };

  useEffect(() => {
    axios.get(`${API}/pages/${site}/${page}`).then(r => setSeo(r.data.seo));
    axios.get(`${API}/sites/${site}/undo-status`).then(r => setCanUndo(r.data.can_undo)).catch(() => {});
  }, [site, page]);

  const undo = async () => {
    try {
      const { data } = await axios.post(`${API}/sites/${site}/undo`);
      if (data.ok) {
        flash("Undid your last change"); setCanUndo(data.can_undo); reload();
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
            setDirty(true); setCanUndo(true); reload();
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
    } else if (d.t === "logo") {
      pendingEid.current = d.eid;
      logoFileRef.current?.click();
    } else if (d.t === "alt") {
      setAltEdit({ eid: d.eid, alt: d.alt || "" });
    } else if (d.t === "status") {
      setStatusEdit({ eid: d.eid });
    } else if (d.t === "caption") {
      const cap = window.prompt("Caption shown under this photo (leave blank to show no caption):", d.caption || "");
      if (cap !== null) {
        await axios.put(`${API}/pages/${site}/${page}/caption`, { eid: d.eid, caption: cap });
        setDirty(true); setCanUndo(true); flash(cap.trim() ? "Caption saved" : "Caption removed"); reload();
      }
    } else if (d.t === "link") {
      const url = window.prompt("Link URL (where this button/link goes):", d.href || "");
      if (url !== null) {
        await axios.put(`${API}/pages/${site}/${page}/link`, { eid: d.eid, href: url });
        setDirty(true); setCanUndo(true); flash("Link updated"); reload();
      }
    } else if (d.t === "op") {
      if ((d.op === "delete" || d.op === "delete-block") &&
          !window.confirm(d.op === "delete-block"
            ? "Remove this whole card/block? A restore point is saved first, so you can undo it."
            : "Delete this element? It will be removed on the next publish (a backup is always kept).")) return;
      try {
        await axios.post(`${API}/pages/${site}/${page}/op`, { op: d.op, eid: d.eid, ref: d.ref, kind: d.kind });
        setDirty(true); setCanUndo(true);
        const msg = { "delete": "Deleted", "add-button": "Button added", "add-el": (d.kind === "image" ? "Image added — click it to replace" : (d.kind === "heading" ? "Heading added — click to edit" : (d.kind === "button" ? "Button added — click to edit" : "Text added — click to edit"))), "add-image": "Image added — click it to replace", "move-up": "Moved up", "move-down": "Moved down", "swap-image": "Photos reordered", "duplicate-block": "Card duplicated", "add-blank-block": "Blank card added — click to fill it in", "delete-block": "Card removed", "move-block-up": "Card moved", "move-block-down": "Card moved" }[d.op] || "Duplicated";
        flash(msg);
        reload(); // reload iframe to reflect structural change
      } catch (e) { flash(e.response?.data?.detail || "Could not apply change"); }
    }
  }, [site, page, flash, reload]);

  useEffect(() => {
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [onMessage]);

  const onFile = (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    setCropState({ file: f, aspect: pendingAspect.current, eid: pendingEid.current });
    e.target.value = "";
  };

  const onLogoFile = async (e) => {
    const f = e.target.files?.[0]; if (!f) return; e.target.value = "";
    flash("Uploading logo…");
    try {
      const fd = new FormData(); fd.append("file", f);
      const { data } = await axios.post(`${API}/media/${site}/upload`, fd);
      await axios.post(`${API}/pages/${site}/${page}/op`, { op: "set-logo", eid: pendingEid.current, url: data.url });
      setDirty(true); setCanUndo(true); flash("Logo replaced — click it again to swap or resize"); reload();
    } catch (err) { flash(err.response?.data?.detail || "Could not replace the logo"); }
  };

  const finishCrop = async (blob) => {
    const cs = cropState; setCropState(null);
    flash("Uploading image…");
    try {
      const fd = new FormData(); fd.append("file", new File([blob], "photo.jpg", { type: "image/jpeg" }));
      const { data } = await axios.post(`${API}/media/${site}/upload`, fd);
      await axios.put(`${API}/pages/${site}/${page}/region`, { eid: cs.eid, value: data.url });
      setDirty(true); setCanUndo(true); flash("Image replaced"); reload();
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
      reload();
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
          <button className="btn ghost" data-testid="editor-seo" onClick={() => setShowSeo(true)}>⚙ SEO title</button>
          <button className="btn ghost" data-testid="editor-help" onClick={() => setShowHelp(true)}>? Help</button>
          <button className="btn ghost" data-testid="editor-undo" disabled={!canUndo} onClick={undo}>↶ Undo</button>
          <button className="btn primary" data-testid="editor-publish-btn" onClick={() => setShowPublish(true)}>Publish</button>
        </div>
      </header>
      {dirty && <div className="dirty-bar" data-testid="dirty-bar">● Unsaved changes will go live on your next Publish</div>}
      <div className="editor-body">
        <iframe
          key={nonce}
          ref={iframeRef}
          title="page"
          className="page-frame full"
          data-testid="page-frame"
          onLoad={onFrameLoad}
          src={`${API}/editor/page/${site}/${page}?v=${nonce}`}
        />
      </div>
      <input ref={fileRef} type="file" accept="image/*" hidden onChange={onFile} data-testid="image-input" />
      <input ref={bulkFileRef} type="file" accept="image/*" multiple hidden onChange={onBulkFiles} data-testid="bulk-image-input" />
      <input ref={logoFileRef} type="file" accept="image/*,.svg" hidden onChange={onLogoFile} data-testid="logo-input" />
      {showSeo && seo && (
        <Modal title="SEO & page title" onClose={() => setShowSeo(false)}>
          <p className="hint">This is the headline Google shows and the name on the browser tab for this page.</p>
          <label className="modal-label">Page title</label>
          <input className="modal-input" data-testid="seo-title" value={seo.title || ""} onChange={e => setSeo({ ...seo, title: e.target.value })} />
          <div className="hint" style={{ marginTop: 8 }}>Your meta description, Open Graph, Twitter cards and JSON-LD ({(seo.metas || []).length}) are kept exactly and shipped on publish.</div>
          <button className="btn" style={{ marginTop: 16 }} data-testid="fill-alt-btn" disabled={fillingAlt} onClick={fillAllAlt}>
            {fillingAlt ? "✨ Filling…" : "✨ Fill missing alt text"}
          </button>
          <div className="hint" style={{ marginTop: 6 }}>Let AI write alt text for every image on this page that doesn't have one yet.</div>
          <div className="modal-actions">
            <button className="btn ghost" onClick={() => setShowSeo(false)}>Close</button>
            <button className="btn primary" data-testid="save-seo" onClick={async () => { await saveSeo(); setShowSeo(false); }}>Save title</button>
          </div>
        </Modal>
      )}
      {showHelp && <HelpModal onClose={() => setShowHelp(false)} />}
      {showPublish && <PublishConfirm site={site} flash={flash} onClose={() => setShowPublish(false)} />}
      {cropState && <CropModal file={cropState.file} aspect={cropState.aspect} onCancel={() => setCropState(null)} onDone={finishCrop} />}
      {altEdit && <AltModal site={site} page={page} eid={altEdit.eid} initial={altEdit.alt} flash={flash}
        onClose={() => setAltEdit(null)} onSaved={() => { setAltEdit(null); setDirty(true); setCanUndo(true); reload(); }} />}
      {statusEdit && <StatusModal site={site} page={page} eid={statusEdit.eid} flash={flash}
        onClose={() => setStatusEdit(null)} onDone={() => { setStatusEdit(null); setDirty(true); setCanUndo(true); reload(); }} />}
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
