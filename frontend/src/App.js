import React, { useEffect, useState } from "react";
import "./App.css";

const API_BASE = "http://127.0.0.1:9001";

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [selectedIncident, setSelectedIncident] = useState(null);

  const [postmortem, setPostmortem] = useState("");
  const [cachedFlag, setCachedFlag] = useState(null);

  const [kpis, setKpis] = useState(null);

  const [onlyFailed, setOnlyFailed] = useState(true);
  const [search, setSearch] = useState("");

  const [loadingList, setLoadingList] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [loadingPM, setLoadingPM] = useState(false);
  const [loadingKPIs, setLoadingKPIs] = useState(false);

  const [error, setError] = useState("");

  async function fetchKPIs() {
    try {
      setLoadingKPIs(true);
      const res = await fetch(`${API_BASE}/kpis`);
      if (!res.ok) throw new Error(`Failed KPIs: ${res.status}`);
      const data = await res.json();
      setKpis(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingKPIs(false);
    }
  }

  async function fetchIncidents() {
    try {
      setLoadingList(true);
      setError("");

      const params = new URLSearchParams();
      if (onlyFailed) params.set("status", "FAILED");
      if (search.trim()) params.set("search", search.trim());

      const res = await fetch(`${API_BASE}/incidents?${params.toString()}`);
      if (!res.ok) throw new Error(`Failed incidents list: ${res.status}`);
      const data = await res.json();
      setIncidents(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingList(false);
    }
  }

  async function refreshFromCsv() {
    try {
      setError("");
      // trigger refresh
      const res = await fetch(`${API_BASE}/refresh`, { method: "POST" });
      if (!res.ok) throw new Error(`Refresh failed: ${res.status}`);
      // reload data
      await fetchKPIs();
      await fetchIncidents();
      // clear selection
      setSelectedId("");
      setSelectedIncident(null);
      setPostmortem("");
      setCachedFlag(null);
    } catch (e) {
      setError(e.message);
    }
  }

  async function loadIncidentDetails(orderId) {
    try {
      setLoadingDetails(true);
      setError("");
      setSelectedId(orderId);
      setSelectedIncident(null);
      setPostmortem("");
      setCachedFlag(null);

      const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(orderId)}`);
      if (!res.ok) throw new Error(`Failed incident detail: ${res.status}`);
      const data = await res.json();
      setSelectedIncident(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingDetails(false);
    }
  }

  async function loadPostmortem(regenerate = false) {
    if (!selectedId) return;
    try {
      setLoadingPM(true);
      setError("");

      const url =
        `${API_BASE}/incidents/${encodeURIComponent(selectedId)}/postmortem` +
        (regenerate ? "?regenerate=true" : "");

      const res = await fetch(url);
      if (!res.ok) throw new Error(`Failed postmortem: ${res.status}`);
      const data = await res.json();

      setPostmortem(data.postmortem || "");
      setCachedFlag(Boolean(data.cached));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingPM(false);
    }
  }

  useEffect(() => {
    // initial load
    fetchKPIs();
    fetchIncidents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // reload list when filters change
    fetchIncidents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onlyFailed]);

  return (
    <div className="App">
      <h1>Smart Logistics – Incident & Postmortem Dashboard (Azure SQL)</h1>

      <div className="toolbar">
        <button onClick={refreshFromCsv}>Refresh from CSV → Save to Azure SQL</button>

        <label className="toggle">
          <input
            type="checkbox"
            checked={onlyFailed}
            onChange={(e) => setOnlyFailed(e.target.checked)}
          />
          Failed only
        </label>

        <input
          className="search"
          placeholder="Search order id (e.g. ORD-PROC)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button onClick={fetchIncidents}>Apply</button>
      </div>

      {error && <p className="error">{error}</p>}

      {/* KPI cards */}
      <div className="kpi-row">
        {loadingKPIs && <div className="kpi">Loading KPIs...</div>}
        {kpis && (
          <>
            <div className="kpi">
              <div className="kpi-label">Total Incidents</div>
              <div className="kpi-value">{kpis.total_incidents}</div>
            </div>
            <div className="kpi">
              <div className="kpi-label">Failed Incidents</div>
              <div className="kpi-value">{kpis.failed_incidents}</div>
            </div>
            <div className="kpi">
              <div className="kpi-label">Failure Rate</div>
              <div className="kpi-value">
                {(kpis.failure_rate * 100).toFixed(1)}%
              </div>
            </div>
            <div className="kpi">
              <div className="kpi-label">Top Failure</div>
              <div className="kpi-value small">
                {kpis.top_failure_detail || "-"}
              </div>
            </div>
          </>
        )}
      </div>

      <div className="main">
        <div className="left">
          <h2>Incidents (from Azure SQL)</h2>
          {loadingList && <p>Loading incidents…</p>}

          <table>
            <thead>
              <tr>
                <th>Order</th>
                <th>Status</th>
                <th>Failure</th>
                <th>Events</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((x) => (
                <tr
                  key={x.order_id}
                  className={x.order_id === selectedId ? "selected" : ""}
                  onClick={() => loadIncidentDetails(x.order_id)}
                  style={{ cursor: "pointer" }}
                >
                  <td>{x.order_id}</td>
                  <td className={x.status === "FAILED" ? "failed" : "ok"}>
                    {x.status}
                  </td>
                  <td>{x.failure_detail || "-"}</td>
                  <td>{x.event_count}</td>
                  <td>{x.source || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="right">
          <h2>Incident Details</h2>

          {!selectedId && <p>Select an incident.</p>}
          {loadingDetails && <p>Loading incident…</p>}

          {selectedIncident && (
            <>
              <div className="card">
                <div><b>Order:</b> {selectedIncident.order_id}</div>
                <div><b>Status:</b> {selectedIncident.status}</div>
                <div><b>Failure:</b> {selectedIncident.failure_detail || "-"}</div>
                <div><b>Duration:</b> {selectedIncident.duration_seconds}s</div>
                <div><b>Events:</b> {selectedIncident.event_count}</div>
              </div>

              <div className="pm-actions">
                <button onClick={() => loadPostmortem(false)} disabled={loadingPM}>
                  Get Postmortem
                </button>
                <button onClick={() => loadPostmortem(true)} disabled={loadingPM}>
                  Regenerate
                </button>

                {cachedFlag !== null && (
                  <span className={cachedFlag ? "badge cached" : "badge fresh"}>
                    {cachedFlag ? "CACHED" : "GENERATED"}
                  </span>
                )}
              </div>

              {loadingPM && <p>Generating postmortem…</p>}
              {postmortem && <pre className="postmortem">{postmortem}</pre>}

              <h3>Timeline</h3>
              <ul className="timeline">
                {selectedIncident.messages.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </div>
  );
}