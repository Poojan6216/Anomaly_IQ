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

const styles = {
  card: {
    backgroundColor: '#1e293b',
    borderRadius: '12px',
    padding: '20px',
    border: '1px solid #334155',
  },
  title: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#94a3b8',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '4px',
  },
  modelBadge: {
    display: 'inline-block',
    fontSize: '11px',
    backgroundColor: '#0f172a',
    color: '#64748b',
    borderRadius: '4px',
    padding: '2px 6px',
    marginBottom: '12px',
  },
  empty: {
    textAlign: 'center',
    color: '#475569',
    padding: '40px 0',
    fontSize: '14px',
  },
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        backgroundColor: '#0f172a',
        border: '1px solid #334155',
        borderRadius: '8px',
        padding: '10px 14px',
        fontSize: '13px',
      }}
    >
      <div style={{ color: '#94a3b8', marginBottom: '6px' }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || '#f1f5f9', marginBottom: '2px' }}>
          {p.name}: <strong>${Number(p.value || 0).toFixed(4)}</strong>
        </div>
      ))}
    </div>
  );
};

function ForecastChart({ forecasts = null }) {
  if (!forecasts?.predictions?.length) {
    return (
      <div style={styles.card}>
        <div style={styles.title}>30-Day Forecast</div>
        <div style={styles.empty}>No forecast data available.</div>
      </div>
    );
  }

  // Sample to max 120 points for performance
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
    range: [Math.max(0, p.yhat_lower), Math.max(0, p.yhat_upper)],
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
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#64748b', fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: '#64748b', fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
            tickFormatter={(v) => `$${v.toFixed(2)}`}
            width={65}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }} />
          {/* Confidence band: upper */}
          <Area
            type="monotone"
            dataKey="upper"
            stroke="none"
            fill="url(#colorUpper)"
            name="Upper bound"
            legendType="none"
          />
          {/* Confidence band: lower */}
          <Area
            type="monotone"
            dataKey="lower"
            stroke="none"
            fill="#0f172a"
            name="Lower bound"
            legendType="none"
          />
          {/* Predicted line */}
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
