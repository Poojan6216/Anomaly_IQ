import axios from 'axios';
import useStore from '../store/store';

const API = 'http://localhost:8000';

const SEVERITY_COLORS = {
  Critical: { bg: '#7f1d1d', text: '#fca5a5', border: '#991b1b' },
  High: { bg: '#431407', text: '#fb923c', border: '#7c2d12' },
  Medium: { bg: '#451a03', text: '#fbbf24', border: '#78350f' },
  Low: { bg: '#1c2a1c', text: '#86efac', border: '#166534' },
};

const styles = {
  card: {
    backgroundColor: '#1e293b',
    borderRadius: '12px',
    padding: '20px',
    border: '1px solid #334155',
    display: 'flex',
    flexDirection: 'column',
    gap: '0',
  },
  title: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#94a3b8',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '16px',
  },
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    overflowY: 'auto',
    maxHeight: '360px',
  },
  item: {
    borderRadius: '8px',
    padding: '10px 12px',
    cursor: 'pointer',
    transition: 'opacity 0.15s',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '4px',
  },
  badge: {
    fontSize: '10px',
    fontWeight: '700',
    padding: '2px 7px',
    borderRadius: '4px',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  time: {
    fontSize: '11px',
    color: '#64748b',
  },
  message: {
    fontSize: '13px',
    color: '#cbd5e1',
    lineHeight: '1.4',
    wordBreak: 'break-word',
  },
  ack: {
    fontSize: '11px',
    color: '#22c55e',
    marginTop: '4px',
  },
  empty: {
    textAlign: 'center',
    color: '#475569',
    padding: '40px 0',
    fontSize: '14px',
  },
};

function AlertFeed({ alerts = [] }) {
  const { acknowledgeAlert } = useStore();

  const handleAck = async (alertId) => {
    try {
      await axios.post(`${API}/api/alerts/${alertId}/acknowledge`);
      acknowledgeAlert(alertId);
    } catch {
      // Acknowledge optimistically
      acknowledgeAlert(alertId);
    }
  };

  if (!alerts.length) {
    return (
      <div style={styles.card}>
        <div style={styles.title}>Recent Alerts</div>
        <div style={styles.empty}>No alerts yet.</div>
      </div>
    );
  }

  return (
    <div style={styles.card}>
      <div style={styles.title}>Recent Alerts</div>
      <div style={styles.list}>
        {alerts.map((alert, i) => {
          const colors = SEVERITY_COLORS[alert.severity] || SEVERITY_COLORS.Low;
          return (
            <div
              key={alert._id || i}
              style={{
                ...styles.item,
                backgroundColor: colors.bg,
                border: `1px solid ${colors.border}`,
                opacity: alert.acknowledged ? 0.6 : 1,
              }}
              onClick={() => !alert.acknowledged && handleAck(alert._id)}
              title={alert.acknowledged ? 'Acknowledged' : 'Click to acknowledge'}
            >
              <div style={styles.header}>
                <span
                  style={{
                    ...styles.badge,
                    backgroundColor: colors.border,
                    color: colors.text,
                  }}
                >
                  {alert.severity}
                </span>
                <span style={styles.time}>
                  {alert.timestamp
                    ? new Date(alert.timestamp).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : ''}
                </span>
              </div>
              <div style={{ ...styles.message, color: colors.text }}>
                {alert.message?.slice(0, 120) || `Anomaly ${alert.anomaly_id}`}
              </div>
              <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                Channel: {alert.channel} · ID: {alert.anomaly_id?.slice(-6)}
              </div>
              {alert.acknowledged && <div style={styles.ack}>Acknowledged</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default AlertFeed;
