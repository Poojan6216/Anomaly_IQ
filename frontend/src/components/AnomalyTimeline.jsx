import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
  Legend,
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
    marginBottom: '16px',
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
  const d = payload[0]?.payload;
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
      <div style={{ color: '#94a3b8', marginBottom: '4px' }}>{label}</div>
      <div style={{ color: '#f1f5f9' }}>
        Cost: <strong>${Number(payload[0]?.value || 0).toFixed(4)}</strong>
      </div>
      {d?.isAnomaly && (
        <div style={{ color: '#ef4444', marginTop: '4px' }}>
          Anomaly: {d.service} — {d.severity}
        </div>
      )}
    </div>
  );
};

function AnomalyTimeline({ costHistory = [], anomalies = [] }) {
  // Merge cost history with anomaly markers
  const anomalyMap = {};
  anomalies.forEach((a) => {
    const ts = a.timestamp?.slice(0, 13); // "YYYY-MM-DDTHH"
    if (!anomalyMap[ts]) {
      anomalyMap[ts] = { ...a, isAnomaly: true };
    }
  });

  const data = costHistory.map((point) => {
    const ts = point.timestamp?.slice(0, 13);
    const anomaly = anomalyMap[ts];
    return {
      time: point.timestamp
        ? new Date(point.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        : '',
      fullTs: point.timestamp,
      cost: Number(point.total_cost || 0),
      isAnomaly: !!anomaly,
      service: anomaly?.service || '',
      severity: anomaly?.severity || '',
    };
  });

  const anomalyPoints = data.filter((d) => d.isAnomaly);

  if (!data.length) {
    return (
      <div style={styles.card}>
        <div style={styles.title}>Cost + Anomaly Timeline</div>
        <div style={styles.empty}>No cost history available.</div>
      </div>
    );
  }

  return (
    <div style={styles.card}>
      <div style={styles.title}>Cost + Anomaly Timeline</div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="time"
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
            width={60}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }}
          />
          <Line
            type="monotone"
            dataKey="cost"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            name="Hourly Cost ($)"
            activeDot={{ r: 4, fill: '#3b82f6' }}
          />
          {anomalyPoints.map((pt, i) => (
            <ReferenceDot
              key={i}
              x={pt.time}
              y={pt.cost}
              r={6}
              fill="#ef4444"
              stroke="#fff"
              strokeWidth={1.5}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default AnomalyTimeline;
