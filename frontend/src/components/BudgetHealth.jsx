import { useEffect, useState } from 'react';
import useStore, { getTheme } from '../store/store';

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

function getBarColor(pct) {
  if (pct >= 90) return '#ef4444';
  if (pct >= 80) return '#f59e0b';
  return '#22c55e';
}

function getBreachStyle(prob, isDark) {
  if (isDark) {
    if (prob >= 0.8) return { backgroundColor: '#7f1d1d', color: '#fca5a5' };
    if (prob >= 0.5) return { backgroundColor: '#78350f', color: '#fcd34d' };
    return { backgroundColor: '#14532d', color: '#86efac' };
  }
  if (prob >= 0.8) return { backgroundColor: '#fee2e2', color: '#b91c1c' };
  if (prob >= 0.5) return { backgroundColor: '#ffedd5', color: '#92400e' };
  return { backgroundColor: '#dcfce7', color: '#166534' };
}

function BudgetHealth({ budgets = [], currentCostByService = {} }) {
  const { selectedProvider, theme } = useStore();
  const t = getTheme(theme);
  const [forecasts, setForecasts] = useState({});

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
    grid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
      gap: '16px',
    },
    budgetItem: {
      backgroundColor: t.cardInnerBg,
      borderRadius: '8px',
      padding: '14px',
      border: `1px solid ${t.border}`,
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
      color: t.textPrimary,
    },
    pct: {
      fontSize: '20px',
      fontWeight: '700',
    },
    barOuter: {
      height: '10px',
      backgroundColor: t.cardBg,
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
      color: t.textMuted,
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
      color: t.textDimmer,
      padding: '40px 0',
      fontSize: '14px',
    },
  };

  useEffect(() => {
    if (!budgets.length) return;
    budgets.forEach((budget) => {
      if (!budget._id) return;
      fetch(`${API}/api/budgets/${budget._id}/forecast?provider=${selectedProvider}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data) setForecasts((prev) => ({ ...prev, [budget._id]: data }));
        })
        .catch(() => {});
    });
  }, [budgets]);

  if (!budgets.length) {
    return (
      <div style={styles.card}>
        <div style={styles.title}>Budget Health</div>
        <div style={styles.empty}>No budgets configured.</div>
      </div>
    );
  }

  return (
    <div style={styles.card}>
      <div style={styles.title}>Budget Health</div>
      <div style={styles.grid}>
        {budgets.map((budget, i) => {
          const spent =
            budget.service_filter && currentCostByService[budget.service_filter]
              ? currentCostByService[budget.service_filter]
              : 0;
          const limit = budget.limit || 1;
          const pct = Math.min(100, (spent / limit) * 100);
          const color = getBarColor(pct);
          const forecast = budget._id ? forecasts[budget._id] : null;

          return (
            <div key={budget._id || i} style={styles.budgetItem}>
              <div style={styles.header}>
                <span style={styles.name}>{budget.name}</span>
                <span style={{ ...styles.pct, color }}>{pct.toFixed(1)}%</span>
              </div>
              <div style={styles.barOuter}>
                <div style={{ ...styles.barInner, width: `${pct}%`, backgroundColor: color }} />
              </div>
              <div style={styles.footer}>
                <span>${spent.toFixed(2)} spent</span>
                <span>${limit.toFixed(2)} limit</span>
                <span style={{ textTransform: 'capitalize' }}>{budget.budget_type}</span>
              </div>
              {forecast && forecast.breach_probability != null && (
                <div style={{ ...styles.breachRow, ...getBreachStyle(forecast.breach_probability, theme === 'dark') }}>
                  <span>⚡ Breach probability:</span>
                  <strong>{(forecast.breach_probability * 100).toFixed(0)}%</strong>
                  {forecast.days_until_breach != null && (
                    <span style={{ marginLeft: 'auto' }}>~{forecast.days_until_breach}d</span>
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

export default BudgetHealth;
