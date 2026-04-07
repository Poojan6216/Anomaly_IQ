import useStore, { getTheme } from '../store/store';

const EFFORT_COLORS = {
  low: '#22c55e',
  medium: '#f59e0b',
  high: '#ef4444',
};

function RecommendationCards({ recommendations = [] }) {
  const { theme } = useStore();
  const t = getTheme(theme);

  const styles = {
    card: {
      backgroundColor: t.cardBg,
      borderRadius: '12px',
      padding: '20px',
      border: `1px solid ${t.border}`,
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
      gap: '10px',
      maxHeight: '360px',
      overflowY: 'auto',
    },
    item: {
      backgroundColor: t.cardInnerBg,
      borderRadius: '8px',
      padding: '12px 14px',
      border: `1px solid ${t.border}`,
    },
    itemHeader: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      marginBottom: '6px',
      gap: '8px',
    },
    action: {
      fontSize: '14px',
      fontWeight: '600',
      color: t.textPrimary,
      flex: 1,
      lineHeight: '1.4',
    },
    savings: {
      fontSize: '16px',
      fontWeight: '700',
      color: '#22c55e',
      whiteSpace: 'nowrap',
    },
    savingsLabel: {
      fontSize: '10px',
      color: t.textMuted,
      textAlign: 'right',
    },
    detail: {
      fontSize: '12px',
      color: t.textSecondary,
      lineHeight: '1.5',
      marginBottom: '8px',
    },
    meta: {
      display: 'flex',
      gap: '8px',
      alignItems: 'center',
      flexWrap: 'wrap',
    },
    tag: {
      fontSize: '11px',
      padding: '2px 7px',
      borderRadius: '4px',
      backgroundColor: t.cardBg,
      color: t.textSecondary,
    },
    effortTag: {
      fontSize: '11px',
      padding: '2px 7px',
      borderRadius: '4px',
      fontWeight: '600',
    },
    empty: {
      textAlign: 'center',
      color: t.textDimmer,
      padding: '40px 0',
      fontSize: '14px',
    },
  };

  if (!recommendations.length) {
    return (
      <div style={styles.card}>
        <div style={styles.title}>Recommendations</div>
        <div style={styles.empty}>No recommendations yet.</div>
      </div>
    );
  }

  return (
    <div style={styles.card}>
      <div style={styles.title}>Recommendations</div>
      <div style={styles.list}>
        {recommendations.map((rec, i) => {
          const effortColor = EFFORT_COLORS[rec.effort] || t.textMuted;
          return (
            <div key={rec._id || i} style={styles.item}>
              <div style={styles.itemHeader}>
                <div style={styles.action}>{rec.action}</div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={styles.savings}>${(rec.estimated_savings || 0).toFixed(2)}</div>
                  <div style={styles.savingsLabel}>/ month</div>
                </div>
              </div>
              {rec.detail && <div style={styles.detail}>{rec.detail}</div>}
              <div style={styles.meta}>
                {rec.service && <span style={styles.tag}>{rec.service}</span>}
                {rec.region && <span style={styles.tag}>{rec.region}</span>}
                {rec.effort && (
                  <span style={{ ...styles.effortTag, color: effortColor, backgroundColor: `${effortColor}20` }}>
                    {rec.effort} effort
                  </span>
                )}
                {rec.priority && (
                  <span style={{ ...styles.tag, color: t.textSecondary }}>P{rec.priority}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default RecommendationCards;
