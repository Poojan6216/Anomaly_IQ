import { useNavigate } from 'react-router-dom';

const clouds = [
  {
    id: 'aws',
    name: 'Amazon Web Services',
    short: 'AWS',
    path: '/dashboard/aws',
    gradient: 'linear-gradient(135deg, #ff9900, #ff6600)',
    iconBg: 'linear-gradient(135deg, #ff9900, #ff6600)',
    glowColor: 'rgba(255, 153, 0, 0.15)',
    borderColor: 'rgba(255, 153, 0, 0.3)',
    hoverBorder: 'rgba(255, 153, 0, 0.6)',
    tagColor: '#ff9900',
    tagBg: 'rgba(255, 153, 0, 0.12)',
    status: 'live',
    statusLabel: 'Connected',
    description: 'Monitor EC2, S3, RDS, Lambda and 200+ AWS services. Real-time cost anomaly detection with AI-powered recommendations.',
    services: ['EC2', 'S3', 'RDS', 'Lambda', 'CloudFront'],
    icon: (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        <path d="M16 6L6 12v8l10 6 10-6v-8L16 6z" stroke="#ff9900" strokeWidth="1.5" fill="none"/>
        <path d="M6 12l10 6 10-6" stroke="#ff9900" strokeWidth="1.5"/>
        <path d="M16 18v8" stroke="#ff9900" strokeWidth="1.5"/>
        <path d="M11 9.5l10 6" stroke="#ff9900" strokeWidth="1" opacity="0.5"/>
        <path d="M21 9.5l-10 6" stroke="#ff9900" strokeWidth="1" opacity="0.5"/>
      </svg>
    ),
  },
  {
    id: 'azure',
    name: 'Microsoft Azure',
    short: 'Azure',
    path: '/dashboard/azure',
    gradient: 'linear-gradient(135deg, #0078d4, #00bcf2)',
    iconBg: 'linear-gradient(135deg, #0078d4, #00bcf2)',
    glowColor: 'rgba(0, 120, 212, 0.15)',
    borderColor: 'rgba(0, 120, 212, 0.3)',
    hoverBorder: 'rgba(0, 120, 212, 0.6)',
    tagColor: '#00bcf2',
    tagBg: 'rgba(0, 188, 242, 0.12)',
    status: 'coming_soon',
    statusLabel: 'Coming Soon',
    description: 'Track Azure VMs, App Services, SQL Database, Functions and more. Cost management across all Azure subscriptions.',
    services: ['VMs', 'App Service', 'SQL DB', 'Functions', 'Storage'],
    icon: (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        <path d="M12 6l-6 14h6l-2 6 12-14h-6l4-6H12z" stroke="#00bcf2" strokeWidth="1.5" fill="none" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    id: 'gcp',
    name: 'Google Cloud Platform',
    short: 'GCP',
    path: '/dashboard/gcp',
    gradient: 'linear-gradient(135deg, #4285f4, #34a853)',
    iconBg: 'linear-gradient(135deg, #4285f4, #34a853)',
    glowColor: 'rgba(66, 133, 244, 0.15)',
    borderColor: 'rgba(66, 133, 244, 0.3)',
    hoverBorder: 'rgba(66, 133, 244, 0.6)',
    tagColor: '#34a853',
    tagBg: 'rgba(52, 168, 83, 0.12)',
    status: 'live',
    statusLabel: 'Connected',
    description: 'Monitor Compute Engine, BigQuery, Cloud Run, GKE and all GCP services. Unified billing analysis and forecasting.',
    services: ['Compute', 'BigQuery', 'Cloud Run', 'GKE', 'Storage'],
    icon: (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        <path d="M16 8l7 4v8l-7 4-7-4v-8l7-4z" stroke="#4285f4" strokeWidth="1.5" fill="none"/>
        <circle cx="16" cy="16" r="3" stroke="#34a853" strokeWidth="1.5" fill="none"/>
        <path d="M16 8v5M16 19v5M23 12l-4.5 2.5M13.5 17.5L9 20M9 12l4.5 2.5M18.5 17.5L23 20" stroke="#4285f4" strokeWidth="1" opacity="0.5"/>
      </svg>
    ),
  },
];

const styles = {
  page: {
    minHeight: '100vh',
    backgroundColor: '#0f172a',
    display: 'flex',
    flexDirection: 'column',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '20px 32px',
    borderBottom: '1px solid #1e293b',
  },
  logoIcon: {
    width: '40px',
    height: '40px',
    borderRadius: '10px',
    background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '18px',
    color: '#fff',
    fontWeight: '800',
    flexShrink: 0,
  },
  logoText: {
    fontSize: '22px',
    fontWeight: '800',
    background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  },
  logoSub: {
    fontSize: '12px',
    color: '#64748b',
    marginTop: '1px',
  },
  content: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '40px 32px 60px',
    gap: '48px',
  },
  titleBlock: {
    textAlign: 'center',
  },
  title: {
    fontSize: '32px',
    fontWeight: '800',
    color: '#f1f5f9',
    marginBottom: '12px',
  },
  titleAccent: {
    background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  },
  subtitle: {
    fontSize: '16px',
    color: '#64748b',
    maxWidth: '500px',
    margin: '0 auto',
    lineHeight: '1.6',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '24px',
    width: '100%',
    maxWidth: '1100px',
  },
  card: {
    position: 'relative',
    borderRadius: '16px',
    padding: '28px 24px',
    cursor: 'pointer',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    overflow: 'hidden',
  },
  cardTop: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
  },
  iconCircle: {
    width: '52px',
    height: '52px',
    borderRadius: '14px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  statusBadge: {
    fontSize: '11px',
    fontWeight: '600',
    padding: '4px 10px',
    borderRadius: '20px',
    letterSpacing: '0.02em',
  },
  cardName: {
    fontSize: '22px',
    fontWeight: '700',
    color: '#f1f5f9',
  },
  cardFull: {
    fontSize: '13px',
    color: '#64748b',
    marginTop: '2px',
  },
  cardDesc: {
    fontSize: '13px',
    color: '#94a3b8',
    lineHeight: '1.6',
    flex: 1,
  },
  tags: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '6px',
  },
  tag: {
    fontSize: '11px',
    fontWeight: '500',
    padding: '3px 10px',
    borderRadius: '6px',
  },
  cardArrow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '13px',
    fontWeight: '600',
    marginTop: '4px',
  },
};

function CloudSelector() {
  const navigate = useNavigate();

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div style={styles.logoIcon}>A</div>
        <div>
          <div style={styles.logoText}>AnomalyIQ</div>
          <div style={styles.logoSub}>Multi-Cloud Cost Guardian</div>
        </div>
      </div>

      <div style={styles.content}>
        <div style={styles.titleBlock}>
          <h1 style={styles.title}>
            Select Your <span style={styles.titleAccent}>Cloud Provider</span>
          </h1>
          <p style={styles.subtitle}>
            Choose a cloud platform to monitor costs, detect anomalies, and get AI-powered optimization recommendations.
          </p>
        </div>

        <div style={styles.grid}>
          {clouds.map((cloud) => {
            const isLive = cloud.status === 'live';
            return (
              <div
                key={cloud.id}
                style={{
                  ...styles.card,
                  backgroundColor: '#1e293b',
                  border: `1px solid ${cloud.borderColor}`,
                  boxShadow: `0 0 40px ${cloud.glowColor}`,
                  opacity: isLive ? 1 : 0.7,
                }}
                onClick={() => isLive && navigate(cloud.path)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.border = `1px solid ${cloud.hoverBorder}`;
                  e.currentTarget.style.transform = isLive ? 'translateY(-4px)' : 'none';
                  e.currentTarget.style.boxShadow = `0 0 60px ${cloud.glowColor}, 0 20px 40px rgba(0,0,0,0.3)`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.border = `1px solid ${cloud.borderColor}`;
                  e.currentTarget.style.transform = 'none';
                  e.currentTarget.style.boxShadow = `0 0 40px ${cloud.glowColor}`;
                }}
              >
                <div style={styles.cardTop}>
                  <div style={{ ...styles.iconCircle, background: cloud.iconBg + '22' }}>
                    {cloud.icon}
                  </div>
                  <span
                    style={{
                      ...styles.statusBadge,
                      backgroundColor: isLive ? 'rgba(34, 197, 94, 0.12)' : 'rgba(100, 116, 139, 0.15)',
                      color: isLive ? '#22c55e' : '#64748b',
                      border: `1px solid ${isLive ? 'rgba(34, 197, 94, 0.3)' : 'rgba(100, 116, 139, 0.3)'}`,
                    }}
                  >
                    {isLive ? '● ' : ''}{cloud.statusLabel}
                  </span>
                </div>

                <div>
                  <div style={styles.cardName}>{cloud.short}</div>
                  <div style={styles.cardFull}>{cloud.name}</div>
                </div>

                <div style={styles.cardDesc}>{cloud.description}</div>

                <div style={styles.tags}>
                  {cloud.services.map((svc) => (
                    <span
                      key={svc}
                      style={{
                        ...styles.tag,
                        color: cloud.tagColor,
                        backgroundColor: cloud.tagBg,
                      }}
                    >
                      {svc}
                    </span>
                  ))}
                </div>

                <div
                  style={{
                    ...styles.cardArrow,
                    color: isLive ? cloud.tagColor : '#475569',
                  }}
                >
                  {isLive ? 'Open Dashboard' : 'Coming Soon'}
                  {isLive && <span style={{ fontSize: '16px' }}>&rarr;</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default CloudSelector;
