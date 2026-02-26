/** Portfolio data accessor — works in both dev and production modes. */

let _data = null;

export async function getData() {
  if (_data) return _data;

  // Production: data is embedded via placeholder replacement
  if (window.__PORTFOLIO_DATA__ && typeof window.__PORTFOLIO_DATA__ === "object") {
    _data = window.__PORTFOLIO_DATA__;
    return _data;
  }

  // Dev mode: fetch from Python API server
  const r = await fetch("/api/data");
  if (!r.ok) throw new Error("Failed to fetch portfolio data: " + r.status);
  _data = await r.json();
  window.__PORTFOLIO_DATA__ = _data;
  return _data;
}
