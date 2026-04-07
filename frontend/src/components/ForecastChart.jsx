import {
  AreaChart,
  Area,
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
      <div style={{ color: t.textSecondary, marginBottom: '6px' }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || t.textPrimary, marginBottom: '2px' }}>
          {p.name}: <strong>${Number(p.value || 0).toFixed(4)}</strong>
        </div>
      ))}
    </div>
  );
};

function ForecastChart({ forecasts = null }) {
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
      marginBottom: '4px',
    },
    modelBadge: {
      display: 'inline-block',
      fontSize: '11px',
      backgroundColor: t.cardInnerBg,
      color: t.textMuted,
      borderRadius: '4px',
      padding: '2px 6px',
      marginBottom: '12px',
    },
    empty: {
      textAlign: 'center',
      color: t.textDimmer,
      padding: '40px 0',
      fontSize: '14px',
    },
  };

  if (!forecasts?.predictions?.length) {
    return (
      <div style={styles.card}>
        <div style={styles.title}>30-Day Forecast</div>
        <div style={styles.empty}>No forecast data available.</div>
      </div>
    );
  }

  const preds = forecasts.predictions;
  const step = Math.max(1, Math.floor(preds.length / 120));
  const sampled = preds.filter((_, i) => i % step === 0);

  const data = sampled.map((p) => ({
    date: p.ds
      ? new Date(p.ds).toLocaleDateString([], { month: 'short', day: 'numeric' })
      : '',
    predicted: Math.max(0, p.yhat),
    lower: Math.max(0, p.yhat_lower),
    upper: Math.max(0, p.yhat_upper),
  }));

  return (
    <div style={styles.card}>
      <div style={styles.title}>30-Day Forecast</div>
      <div style={styles.modelBadge}>
        Model: {forecasts.model_used || 'prophet'}
        {forecasts.mape != null ? ` · MAPE ${forecasts.mape.toFixed(1)}%` : ''}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="colorUpper" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="colorPredicted" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={t.gridLine} />
          <XAxis
            dataKey="date"
            tick={{ fill: t.textMuted, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: t.gridAxis }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: t.textMuted, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: t.gridAxis }}
            tickFormatter={(v) => `$${v.toFixed(2)}`}
            width={65}
          />
          <Tooltip content={<CustomTooltip t={t} />} />
          <Legend wrapperStyle={{ fontSize: '12px', color: t.textSecondary }} />
          <Area
            type="monotone"
            dataKey="upper"
            stroke="none"
            fill="url(#colorUpper)"
            name="Upper bound"
            legendType="none"
          />
          <Area
            type="monotone"
            dataKey="lower"
            stroke="none"
            fill={t.pageBg}
            name="Lower bound"
            legendType="none"
          />
          <Area
            type="monotone"
            dataKey="predicted"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#colorPredicted)"
            name="Predicted ($)"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default ForecastChart;
