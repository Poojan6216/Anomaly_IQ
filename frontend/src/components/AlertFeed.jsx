import axios from 'axios';
import useStore, { getTheme } from '../store/store';

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const SEVERITY_COLORS = {
  dark: {
    Critical: { bg: '#7f1d1d', text: '#fca5a5', border: '#991b1b' },
    High:     { bg: '#431407', text: '#fb923c', border: '#7c2d12' },
    Medium:   { bg: '#451a03', text: '#fbbf24', border: '#78350f' },
    Low:      { bg: '#1c2a1c', text: '#86efac', border: '#166534' },
  },
  light: {
    Critical: { bg: '#fee2e2', text: '#b91c1c', border: '#fca5a5' },
    High:     { bg: '#ffedd5', text: '#c2410c', border: '#fdba74' },
    Medium:   { bg: '#fef9c3', text: '#a16207', border: '#fde047' },
    Low:      { bg: '#dcfce7', text: '#166534', border: '#86efac' },
  },
};

function AlertFeed({ alerts = [] }) {
  const { acknowledgeAlert, selectedProvider, theme } = useStore();
  const t = getTheme(theme);
  const severityPalette = SEVERITY_COLORS[theme] ?? SEVERITY_COLORS.dark;

  const styles = {
    card: {
      backgroundColor: t.cardBg,
      borderRadius: '12px',
      padding: '20px',
      border: `1px solid ${t.border}`,
      display: 'flex',
      flexDirection: 'column',
      gap: '0',
    },
    title: {
      fontSize: '14px',
      fontWeight: '600',
      color: t.textSecondary,
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
      color: t.textMuted,
    },
    ack: {
      fontSize: '11px',
      color: '#22c55e',
      marginTop: '4px',
    },
    empty: {
      textAlign: 'center',
      color: t.textDimmer,
      padding: '40px 0',
      fontSize: '14px',
    },
  };

  const handleAck = async (alertId) => {
    try {
      await axios.post(`${API}/api/alerts/${alertId}/acknowledge?provider=${selectedProvider}`);
      acknowledgeAlert(alertId);
    } catch {
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
          const colors = severityPalette[alert.severity] || severityPalette.Low;
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
                <span style={{ ...styles.badge, backgroundColor: colors.border, color: colors.text }}>
                  {alert.severity}
                </span>
                <span style={styles.time}>
                  {alert.timestamp
                    ? new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : ''}
                </span>
              </div>
              <div style={{ fontSize: '13px', color: colors.text, lineHeight: '1.4', wordBreak: 'break-word' }}>
                {alert.message?.slice(0, 120) || `Anomaly ${alert.anomaly_id}`}
              </div>
              <div style={{ fontSize: '11px', color: t.textMuted, marginTop: '4px' }}>
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
