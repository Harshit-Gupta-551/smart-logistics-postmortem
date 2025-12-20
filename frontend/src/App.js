import React, { useEffect, useState } from "react";
import "./App.css";

const API_BASE = "http://127.0.0.1:9000";

function App() {
  const [incidents, setIncidents] = useState([]);
  const [loadingInc, setLoadingInc] = useState(false);
  const [selected, setSelected] = useState(null);
  const [postmortem, setPostmortem] = useState("");
  const [loadingPm, setLoadingPm] = useState(false);
  const [error, setError] = useState("");

  // Load incidents on first render
  useEffect(() => {
    async function fetchIncidents() {
      try {
        setLoadingInc(true);
        setError("");
        const res = await fetch(`${API_BASE}/incidents`);
        if (!res.ok) {
          throw new Error(`Failed to load incidents: ${res.status}`);
        }
        const data = await res.json();
        setIncidents(data);
      } catch (e) {
        console.error(e);
        setError(e.message || "Failed to load incidents");
      } finally {
        setLoadingInc(false);
      }
    }

    fetchIncidents();
  }, []);

  async function handleSelect(incident) {
    setSelected(incident);
    setPostmortem("");
    setError("");

    try {
      setLoadingPm(true);
      const res = await fetch(
        `${API_BASE}/incidents/${encodeURIComponent(
          incident.order_id
        )}/postmortem`
      );
      if (!res.ok) {
        throw new Error(`Failed to load postmortem: ${res.status}`);
      }
      const data = await res.json();
      setPostmortem(data.postmortem);
    } catch (e) {
      console.error(e);
      setError(e.message || "Failed to load postmortem");
    } finally {
      setLoadingPm(false);
    }
  }

  return (
    <div className="App">
      <h1>Smart Logistics – Incident Postmortem Dashboard</h1>
      {error && <p className="error">{error}</p>}

      <div className="main">
        <div className="left">
          <h2>Incidents</h2>
          {loadingInc && <p>Loading incidents...</p>}
          {!loadingInc && incidents.length === 0 && <p>No incidents.</p>}

          {incidents.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Order ID</th>
                  <th>Status</th>
                  <th>Failure</th>
                  <th>Duration (s)</th>
                  <th>Events</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => (
                  <tr
                    key={inc.order_id}
                    onClick={() => handleSelect(inc)}
                    className={
                      selected && selected.order_id === inc.order_id
                        ? "selected"
                        : ""
                    }
                    style={{ cursor: "pointer" }}
                  >
                    <td>{inc.order_id}</td>
                    <td className={inc.status === "FAILED" ? "failed" : "ok"}>
                      {inc.status}
                    </td>
                    <td>{inc.failure_detail || "-"}</td>
                    <td>{inc.duration_seconds.toFixed(3)}</td>
                    <td>{inc.event_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="right">
          <h2>Postmortem</h2>
          {!selected && <p>Select an incident.</p>}
          {selected && loadingPm && <p>Loading postmortem...</p>}
          {selected && !loadingPm && postmortem && (
            <pre className="postmortem">{postmortem}</pre>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;