import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import useStore, { getTheme } from '../store/store';

const COLORS = [
  '#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b',
  '#ef4444', '#ec4899', '#84cc16', '#f97316', '#6366f1',
];

const CustomTooltip = ({ active, payload, t }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0];
  return (
    <div style={{
      backgroundColor: t.tooltipBg,
      border: `1px solid ${t.border}`,
      borderRadius: '8px',
      padding: '8px 12px',
      fontSize: '13px',
    }}>
      <div style={{ color: d.payload.fill, fontWeight: '600' }}>{d.name}</div>
      <div style={{ color: t.textPrimary }}>${d.value.toFixed(4)}</div>
      <div style={{ color: t.textSecondary }}>{d.payload.pct?.toFixed(1)}%</div>
    </div>
  );
};

function ServiceBreakdown({ services = [] }) {
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
    legend: {
      marginTop: '16px',
      overflowY: 'auto',
      maxHeight: '140px',
    },
    row: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '6px 0',
      borderBottom: `1px solid ${t.borderSub}`,
    },
    dot: {
      width: '10px',
      height: '10px',
      borderRadius: '50%',
      marginRight: '8px',
      flexShrink: 0,
    },
    serviceName: {
      fontSize: '13px',
      color: t.serviceName,
      flex: 1,
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
    },
    costText: {
      fontSize: '13px',
      fontWeight: '600',
      color: t.textPrimary,
      marginLeft: '8px',
    },
    pctText: {
      fontSize: '11px',
      color: t.textMuted,
      marginLeft: '6px',
      width: '40px',
      textAlign: 'right',
    },
    empty: {
      textAlign: 'center',
      color: t.textDimmer,
      padding: '40px 0',
      fontSize: '14px',
    },
  };

  const total = services.reduce((s, x) => s + (x.total_cost || 0), 0);
  const data = services
    .map((s, i) => ({
      name: s.service || 'Unknown',
      value: s.total_cost || 0,
      pct: total > 0 ? (s.total_cost / total) * 100 : 0,
      fill: COLORS[i % COLORS.length],
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);

  if (!data.length) {
    return (
      <div style={styles.card}>
        <div style={styles.title}>Cost by Service</div>
        <div style={styles.empty}>No service data available.</div>
      </div>
    );
  }

  return (
    <div style={styles.card}>
      <div style={styles.title}>Cost by Service</div>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={85}
            paddingAngle={3}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={index} fill={entry.fill} />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip t={t} />} />
        </PieChart>
      </ResponsiveContainer>
      <div style={styles.legend}>
        {data.map((entry, i) => (
          <div key={i} style={styles.row}>
            <div style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
              <div style={{ ...styles.dot, backgroundColor: entry.fill }} />
              <span style={styles.serviceName}>{entry.name}</span>
            </div>
            <span style={styles.costText}>${entry.value.toFixed(2)}</span>
            <span style={styles.pctText}>{entry.pct.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ServiceBreakdown;
