import { render } from "preact";
import { useState, useEffect } from "preact/hooks";
import { getData } from "./data";
import { App } from "./App";
import "./styles/index.css";

function Root() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getData().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div class="container" style={{ paddingTop: "80px", textAlign: "center" }}>
        <p style={{ color: "var(--red)", fontSize: "16px" }}>Failed to load portfolio data</p>
        <p style={{ color: "var(--text3)", fontSize: "14px", marginTop: "8px" }}>{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div class="container" style={{ paddingTop: "80px", textAlign: "center" }}>
        <p style={{ color: "var(--text2)", fontSize: "14px" }}>Loading portfolio data…</p>
      </div>
    );
  }

  return <App data={data} />;
}

render(<Root />, document.getElementById("app"));
