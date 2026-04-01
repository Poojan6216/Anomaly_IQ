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
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '16px',
  },
  budgetItem: {
    backgroundColor: '#0f172a',
    borderRadius: '8px',
    padding: '14px',
    border: '1px solid #334155',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: '10px',
  },
  name: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#f1f5f9',
  },
  pct: {
    fontSize: '20px',
    fontWeight: '700',
  },
  barOuter: {
    height: '10px',
    backgroundColor: '#1e293b',
    borderRadius: '5px',
    overflow: 'hidden',
    marginBottom: '8px',
  },
  barInner: {
    height: '100%',
    borderRadius: '5px',
    transition: 'width 0.4s ease',
  },
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '12px',
    color: '#64748b',
  },
  breachRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginTop: '8px',
    padding: '6px 8px',
    borderRadius: '6px',
    fontSize: '12px',
  },
  empty: {
    textAlign: 'center',
    color: '#475569',
    padding: '40px 0',
    fontSize: '14px',
  },
};

function getBarColor(pct) {
  if (pct >= 90) return '#ef4444';
  if (pct >= 80) return '#f59e0b';
  return '#22c55e';
}

function getBreachStyle(prob) {
  if (prob >= 0.8) return { backgroundColor: '#7f1d1d', color: '#fca5a5' };
  if (prob >= 0.5) return { backgroundColor: '#78350f', color: '#fcd34d' };
  return { backgroundColor: '#14532d', color: '#86efac' };
}

const MOCK_FORECASTS = {
  'gcp-budget-001': { breach_probability: 0.72, days_until_breach: 8 },
  'gcp-budget-002': { breach_probability: 0.85, days_until_breach: 5 },
  'gcp-budget-003': { breach_probability: 0.60, days_until_breach: 11 },
  'gcp-budget-004': { breach_probability: 0.35, days_until_breach: null },
};

function GcpBudgetHealth({ budgets = [], currentCostByService = {} }) {
  if (!budgets.length) {
    return (
      <div style={styles.card}>
        <div style={styles.title}>Budget Health</div>
        <div style={styles.empty}>No budgets configured.</div>
      </div>
    );
  }

  const totalSpent = Object.values(currentCostByService).reduce((s, v) => s + v, 0);

  return (
    <div style={styles.card}>
      <div style={styles.title}>Budget Health</div>
      <div style={styles.grid}>
        {budgets.map((budget, i) => {
          const spent = budget.service_filter
            ? (currentCostByService[budget.service_filter] || 0)
            : totalSpent;
          const limit = budget.limit || 1;
          const pct = Math.min(100, (spent / limit) * 100);
          const color = getBarColor(pct);
          const forecast = MOCK_FORECASTS[budget._id] || null;

          return (
            <div key={budget._id || i} style={styles.budgetItem}>
              <div style={styles.header}>
                <span style={styles.name}>{budget.name}</span>
                <span style={{ ...styles.pct, color }}>{pct.toFixed(1)}%</span>
              </div>
              <div style={styles.barOuter}>
                <div
                  style={{
                    ...styles.barInner,
                    width: `${pct}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
              <div style={styles.footer}>
                <span>${spent.toFixed(2)} spent</span>
                <span>${limit.toFixed(2)} limit</span>
                <span style={{ textTransform: 'capitalize' }}>{budget.budget_type}</span>
              </div>

              {forecast && forecast.breach_probability != null && (
                <div style={{ ...styles.breachRow, ...getBreachStyle(forecast.breach_probability) }}>
                  <span>⚡ Breach probability:</span>
                  <strong>{(forecast.breach_probability * 100).toFixed(0)}%</strong>
                  {forecast.days_until_breach != null && (
                    <span style={{ marginLeft: 'auto' }}>
                      ~{forecast.days_until_breach}d
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default GcpBudgetHealth;
