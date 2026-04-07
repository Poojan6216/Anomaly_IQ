import {
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import useStore, { getTheme } from '../store/store';

function getColor(pct) {
  if (pct >= 90) return '#ef4444';
  if (pct >= 80) return '#f59e0b';
  return '#22c55e';
}

function CostMeter({ currentSpend = 0, budget = 1000 }) {
  const { theme } = useStore();
  const t = getTheme(theme);

  const pct = budget > 0 ? Math.min(100, (currentSpend / budget) * 100) : 0;
  const color = getColor(pct);
  const data = [{ name: 'spend', value: pct, fill: color }];

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
    centerLabel: {
      position: 'absolute',
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      textAlign: 'center',
      pointerEvents: 'none',
    },
    amount: {
      fontSize: '24px',
      fontWeight: '700',
      color: t.textPrimary,
    },
    sub: {
      fontSize: '12px',
      color: t.textSecondary,
    },
    chartWrap: {
      position: 'relative',
      width: '100%',
      height: '200px',
    },
    meta: {
      display: 'flex',
      justifyContent: 'space-between',
      marginTop: '12px',
    },
    metaItem: {
      textAlign: 'center',
    },
    metaVal: {
      fontSize: '18px',
      fontWeight: '700',
      color: t.textPrimary,
    },
    metaLabel: {
      fontSize: '11px',
      color: t.textMuted,
    },
  };

  return (
    <div style={styles.card}>
      <div style={styles.title}>Month-to-Date Spend</div>
      <div style={styles.chartWrap}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="50%"
            innerRadius="65%"
            outerRadius="90%"
            barSize={14}
            data={data}
            startAngle={180}
            endAngle={0}
          >
            <PolarAngleAxis
              type="number"
              domain={[0, 100]}
              angleAxisId={0}
              tick={false}
            />
            <RadialBar
              background={{ fill: t.barBg }}
              dataKey="value"
              angleAxisId={0}
              cornerRadius={8}
            />
            <Tooltip
              formatter={(val) => [`${val.toFixed(1)}%`, 'Budget used']}
              contentStyle={{ backgroundColor: t.tooltipBg, border: `1px solid ${t.border}`, borderRadius: '8px' }}
              labelStyle={{ color: t.textSecondary }}
              itemStyle={{ color: t.textPrimary }}
            />
          </RadialBarChart>
        </ResponsiveContainer>
        <div style={styles.centerLabel}>
          <div style={{ ...styles.amount, color }}>${currentSpend.toFixed(2)}</div>
          <div style={styles.sub}>{pct.toFixed(1)}% of budget</div>
        </div>
      </div>
      <div style={styles.meta}>
        <div style={styles.metaItem}>
          <div style={{ ...styles.metaVal, color }}>${currentSpend.toFixed(2)}</div>
          <div style={styles.metaLabel}>Spent This Month</div>
        </div>
        <div style={styles.metaItem}>
          <div style={styles.metaVal}>${budget.toFixed(2)}</div>
          <div style={styles.metaLabel}>Monthly Budget</div>
        </div>
        <div style={styles.metaItem}>
          <div style={{ ...styles.metaVal, color: '#22c55e' }}>
            ${Math.max(0, budget - currentSpend).toFixed(2)}
          </div>
          <div style={styles.metaLabel}>Remaining</div>
        </div>
      </div>
    </div>
  );
}

export default CostMeter;
