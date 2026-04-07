import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import useStore, { getTheme } from '../store/store';

const CustomTooltip = ({ active, payload, label, t }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      backgroundColor: t.tooltipBg,
      border: `1px solid ${t.border}`,
      borderRadius: '8px',
      padding: '10px 14px',
      fontSize: '13px',
    }}>
      <div style={{ color: t.textSecondary, marginBottom: '6px', fontWeight: '600' }}>{label}</div>
      {payload.map((p, i) => (
        p.value != null && (
          <div key={i} style={{ color: p.color, marginBottom: '2px' }}>
            {p.name}: <strong>${Number(p.value).toLocaleString()}</strong>
          </div>
        )
      ))}
    </div>
  );
};

function YearlyComparison({ data }) {
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
    empty: {
      textAlign: 'center',
      color: t.textDimmer,
      padding: '40px 0',
      fontSize: '14px',
    },
  };

  if (!data?.months?.length) {
    return (
      <div style={styles.card}>
        <div style={styles.title}>Yearly Cost Trend</div>
        <div style={styles.empty}>No data available.</div>
      </div>
    );
  }

  const chartData = data.months.map((month, i) => ({
    month,
    '2025': data.year_2025[i] ?? null,
    '2026': data.year_2026[i] ?? null,
  }));

  return (
    <div style={styles.card}>
      <div style={styles.title}>Yearly Cost Trend</div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }} barCategoryGap="25%">
          <CartesianGrid strokeDasharray="3 3" stroke={t.gridLine} vertical={false} />
          <XAxis
            dataKey="month"
            tick={{ fill: t.textMuted, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: t.gridAxis }}
          />
          <YAxis
            tick={{ fill: t.textMuted, fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `$${v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v}`}
            width={48}
          />
          <Tooltip content={<CustomTooltip t={t} />} cursor={{ fill: t.borderSub }} />
          <Legend wrapperStyle={{ fontSize: '12px', color: t.textSecondary }} />
          <Bar dataKey="2025" fill="#3b82f6" radius={[3, 3, 0, 0]} maxBarSize={18} />
          <Bar dataKey="2026" fill="#8b5cf6" radius={[3, 3, 0, 0]} maxBarSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default YearlyComparison;
