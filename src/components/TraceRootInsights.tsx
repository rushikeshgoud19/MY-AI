import React, { useState } from 'react';

interface TraceRootInsightsProps {
  // If we had a prop to pass context, else we fetch internally
}

export const TraceRootInsights: React.FC<TraceRootInsightsProps> = () => {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError("");
    setResult(null);

    try {
      // Connects to the new Python backend endpoint we just added
      const response = await fetch("http://127.0.0.1:8001/api/traceroot_sql", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ question })
      });

      const data = await response.json();
      if (data.status === "error") {
        setError(data.message || data.error || "An error occurred");
      } else {
        setResult(data);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '20px', background: 'rgba(25,25,35,0.9)', borderRadius: '12px', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '15px' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '1.5rem' }}>📊</span>
          TraceRoot SQL Analyst
        </h2>
        <span style={{ marginLeft: 'auto', background: '#6366f1', fontSize: '0.7rem', padding: '2px 8px', borderRadius: '10px', fontWeight: 'bold' }}>Gateway Powered</span>
      </div>
      
      <p style={{ fontSize: '0.9rem', color: '#aaa', marginBottom: '15px' }}>
        Ask natural language questions about your telemetry data. Mizune will generate ClickHouse SQL and query the TraceRoot API.
      </p>

      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
        <input 
          type="text" 
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. What is the average duration of the orchestrator spans?"
          style={{ flex: 1, padding: '10px 15px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.3)', color: '#fff' }}
        />
        <button type="submit" disabled={loading} style={{ padding: '10px 20px', borderRadius: '8px', border: 'none', background: '#6366f1', color: '#fff', cursor: loading ? 'wait' : 'pointer', fontWeight: 'bold' }}>
          {loading ? "Querying..." : "Analyze"}
        </button>
      </form>

      {error && (
        <div style={{ padding: '10px', background: 'rgba(239,68,68,0.2)', color: '#ef4444', borderRadius: '8px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {result && (
        <div style={{ animation: 'fadeIn 0.3s ease' }}>
          <div style={{ padding: '15px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', marginBottom: '15px' }}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '1rem', color: '#a855f7' }}>Generated ClickHouse SQL:</h3>
            <pre style={{ margin: 0, padding: '10px', background: 'rgba(0,0,0,0.5)', borderRadius: '5px', overflowX: 'auto', color: '#38bdf8', fontSize: '0.85rem' }}>
              {result.sql}
            </pre>
          </div>

          <div style={{ padding: '15px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', marginBottom: '15px' }}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '1rem', color: '#10b981' }}>Summary:</h3>
            <p style={{ margin: 0, fontSize: '0.95rem', lineHeight: '1.5' }}>{result.summary}</p>
          </div>

          {result.data && result.data.rows && result.data.rows.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                <thead>
                  <tr style={{ background: 'rgba(255,255,255,0.1)' }}>
                    {result.data.columns?.map((col: string, i: number) => (
                      <th key={i} style={{ padding: '10px', textAlign: 'left', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.data.rows.map((row: any[], i: number) => (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      {row.map((cell: any, j: number) => (
                        <td key={j} style={{ padding: '10px', color: '#ccc' }}>{String(cell)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
