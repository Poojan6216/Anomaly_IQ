import { useEffect, useRef, useState } from 'react';
import useStore from './store/store';
import Dashboard from './pages/Dashboard';

const WS_URL = 'ws://localhost:8000/ws';

// Exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s (capped)
const BACKOFF_BASE_MS = 1_000;
const BACKOFF_MAX_MS = 30_000;

const styles = {
  app: {
    minHeight: '100vh',
    backgroundColor: '#0f172a',
    color: '#f1f5f9',
    fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
  },
  loading: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    flexDirection: 'column',
    gap: '16px',
    backgroundColor: '#0f172a',
    color: '#94a3b8',
  },
  spinner: {
    width: '40px',
    height: '40px',
    border: '3px solid #1e293b',
    borderTop: '3px solid #3b82f6',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
  },
};

function App() {
  const {
    setWsConnected,
    addAnomaly,
    addAlert,
    addBudgetWarning,
    setCostData,
  } = useStore();

  const [initialising, setInitialising] = useState(true);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const attemptRef = useRef(0);
  // Fallback: dismiss spinner after 3 s even if WS never connects
  const fallbackTimer = useRef(null);

  const scheduleReconnect = () => {
    const delay = Math.min(
      BACKOFF_BASE_MS * Math.pow(2, attemptRef.current),
      BACKOFF_MAX_MS,
    );
    attemptRef.current += 1;
    reconnectTimer.current = setTimeout(connectWs, delay);
  };

  const connectWs = () => {
    // Clear any pending reconnect timer
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        setInitialising(false);
        attemptRef.current = 0; // reset backoff on success
        if (fallbackTimer.current) {
          clearTimeout(fallbackTimer.current);
          fallbackTimer.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          handleWsMessage(msg);
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        setInitialising(false);
        scheduleReconnect();
      };

      ws.onerror = () => {
        setWsConnected(false);
        // onclose will fire next and schedule the reconnect
      };
    } catch {
      setInitialising(false);
      scheduleReconnect();
    }
  };

  const handleWsMessage = (msg) => {
    switch (msg.type) {
      case 'anomaly_detected':
        addAnomaly(msg.payload);
        break;
      case 'new_alert':
        addAlert(msg.payload);
        break;
      case 'cost_update':
        // Push live cost history update into the store so charts reflect it
        if (Array.isArray(msg.payload)) {
          setCostData(msg.payload);
        }
        break;
      case 'budget_warning':
        addBudgetWarning(msg.payload);
        break;
      case 'connected':
        console.log('[WS] Connected to AnomalyIQ');
        break;
      default:
        break;
    }
  };

  useEffect(() => {
    // Start connection attempt
    connectWs();

    // Fallback: if backend is offline, stop showing the spinner after 3 s
    // so the dashboard renders normally (it will show empty/offline state)
    fallbackTimer.current = setTimeout(() => {
      setInitialising(false);
    }, 3_000);

    return () => {
      if (fallbackTimer.current) clearTimeout(fallbackTimer.current);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  if (initialising) {
    return (
      <div style={styles.loading}>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        <div style={styles.spinner} />
        <span>Connecting to AnomalyIQ…</span>
      </div>
    );
  }

  return (
    <div style={styles.app}>
      <Dashboard />
    </div>
  );
}

export default App;
