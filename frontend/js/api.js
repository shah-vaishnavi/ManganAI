// Centralised API client. All pages use API.get / API.post / API.upload.
const API = (() => {
  const base = (new URLSearchParams(location.search).get("api") || "") + "/api";
  async function req(path, opts = {}) {
    let res;
    try { res = await fetch(base + path, opts); }
    catch (e) { throw new Error("Cannot reach the ManganAI backend. Is the server running?"); }
    let body = null;
    try { body = await res.json(); } catch (e) { /* non-JSON */ }
    if (!res.ok || !body || body.status !== "ok") throw new Error((body && (body.message || (body.details || []).join("; "))) || `Request failed (${res.status})`);
    return body;
  }
  return {
    get: (p) => req(p),
    post: (p, data) => req(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data || {}) }),
    upload: (dataset, file) => { const f = new FormData(); f.append("dataset", dataset); f.append("file", file); return req("/data/upload", { method: "POST", body: f }); },
  };
})();
