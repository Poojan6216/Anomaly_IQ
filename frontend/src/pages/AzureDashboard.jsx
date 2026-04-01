import { useNavigate } from 'react-router-dom';

const styles = {
  page: {
    minHeight: '100vh',
    backgroundColor: '#0f172a',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    padding: '16px 24px',
    backgroundColor: '#1e293b',
    borderBottom: '1px solid #334155',
    position: 'sticky',
    top: 0,
    zIndex: 100,
    gap: '16px',
  },
  backBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 14px',
    borderRadius: '8px',
    border: '1px solid #334155',
    backgroundColor: 'transparent',
    color: '#94a3b8',
    fontSize: '13px',
    fontWeight: '500',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  logoIcon: {
    width: '32px',
    height: '32px',
    borderRadius: '8px',
    background: 'linear-gradient(135deg, #0078d4, #00bcf2)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
    fontSize: '14px',
    fontWeight: '700',
  },
  logoText: {
    fontSize: '20px',
    fontWeight: '800',
    background: 'linear-gradient(135deg, #0078d4, #00bcf2)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  },
  subtitle: {
    fontSize: '12px',
    color: '#475569',
    marginTop: '1px',
  },
  content: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '120px 32px',
    textAlign: 'center',
    gap: '24px',
  },
  iconLarge: {
    width: '80px',
    height: '80px',
    borderRadius: '20px',
    background: 'linear-gradient(135deg, rgba(0,120,212,0.15), rgba(0,188,242,0.15))',
    border: '1px solid rgba(0,120,212,0.3)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '36px',
  },
  title: {
    fontSize: '28px',
    fontWeight: '700',
    color: '#f1f5f9',
  },
  desc: {
    fontSize: '15px',
    color: '#64748b',
    maxWidth: '440px',
    lineHeight: '1.6',
  },
  badge: {
    padding: '8px 20px',
    borderRadius: '24px',
    backgroundColor: 'rgba(0, 120, 212, 0.1)',
    border: '1px solid rgba(0, 120, 212, 0.3)',
    color: '#00bcf2',
    fontSize: '13px',
    fontWeight: '600',
  },
};

function AzureDashboard() {
  const navigate = useNavigate();

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <button style={styles.backBtn} onClick={() => navigate('/')}>
          &larr; Back
        </button>
        <div style={styles.logo}>
          <div style={styles.logoIcon}>Az</div>
          <div>
            <div style={styles.logoText}>AnomalyIQ</div>
            <div style={styles.subtitle}>Azure Cost Guardian</div>
          </div>
        </div>
      </div>

      <div style={styles.content}>
        <div style={styles.iconLarge}>
          <svg width="40" height="40" viewBox="0 0 32 32" fill="none">
            <path d="M12 6l-6 14h6l-2 6 12-14h-6l4-6H12z" stroke="#00bcf2" strokeWidth="1.5" fill="none" strokeLinejoin="round"/>
          </svg>
        </div>
        <h1 style={styles.title}>Azure Dashboard</h1>
        <p style={styles.desc}>
          Azure cost monitoring, anomaly detection, and optimization recommendations are currently under development.
        </p>
        <span style={styles.badge}>Coming Soon</span>
      </div>
    </div>
  );
}

export default AzureDashboard;
