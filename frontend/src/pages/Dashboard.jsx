import { useEffect, useState } from 'react';
import axios from 'axios';
import useStore from '../store/store';
import CostMeter from '../components/CostMeter';
import AnomalyTimeline from '../components/AnomalyTimeline';
import ServiceBreakdown from '../components/ServiceBreakdown';
import ForecastChart from '../components/ForecastChart';
import BudgetHealth from '../components/BudgetHealth';
import AlertFeed from '../components/AlertFeed';
import RecommendationCards from '../components/RecommendationCards';

const API = 'http://localhost:8000';

const styles = {
  page: {
    padding: '0',
    minHeight: '100vh',
    backgroundColor: '#0f172a',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 24px',
    backgroundColor: '#1e293b',
    borderBottom: '1px solid #334155',
    position: 'sticky',
    top: 0,
    zIndex: 100,
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  logoIcon: {
    width: '32px',
    height: '32px',
    borderRadius: '8px',
    background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '16px',
  },
  logoText: {
    fontSize: '20px',
    fontWeight: '800',
    background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  },
  subtitle: {
    fontSize: '12px',
    color: '#475569',
    marginTop: '1px',
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  wsDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    display: 'inline-block',
    marginRight: '6px',
  },
  wsLabel: {
    fontSize: '12px',
    color: '#64748b',
  },
  bell: {
    position: 'relative',
    cursor: 'pointer',
    fontSize: '20px',
    padding: '4px',
  },
  badge: {
    position: 'absolute',
    top: '-2px',
    right: '-4px',
    backgroundColor: '#ef4444',
    color: '#fff',
    borderRadius: '10px',
    fontSize: '10px',
    fontWeight: '700',
    padding: '1px 5px',
    minWidth: '16px',
    textAlign: 'center',
  },
  refreshBtn: {
    padding: '6px 14px',
    borderRadius: '6px',
    fontSize: '12px',
    fontWeight: '600',
    cursor: 'pointer',
    backgroundColor: '#334155',
    color: '#94a3b8',
    border: '1px solid #475569',
  },
  triggerBtn: {
    padding: '6px 14px',
    borderRadius: '6px',
    fontSize: '12px',
    fontWeight: '600',
    cursor: 'pointer',
    border: 'none',
  },
  triggerStatus: {
    fontSize: '11px',
    color: '#64748b',
    fontStyle: 'italic',
  },
  main: {
    padding: '20px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  row: {
    display: 'grid',
    gap: '20px',
  },
  row2: {
    gridTemplateColumns: '1fr 1fr',
  },
  row4: {
    gridTemplateColumns: '1fr 1fr',
  },
  loadingOverlay: {
    position: 'fixed',
    top: '60px',
    right: '16px',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '8px 14px',
    fontSize: '12px',
    color: '#94a3b8',
    zIndex: 200,
  },
};

function Dashboard() {
  const {
    costData,
    setCostData,
    anomalies,
    setAnomalies,
    forecasts,
    setForecasts,
    budgets,
    setBudgets,
    alerts,
    setAlerts,
    recommendations,
    setRecommendations,
    wsConnected,
  } = useStore();

  const [currentBilling, setCurrentBilling] = useState({ total_cost: 0 });
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [triggerStatus, setTriggerStatus] = useState('');
  const [showNotifications, setShowNotifications] = useState(false);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [
        billingCurrent,
        billingHistory,
        billingServices,
        anomalyList,
        forecastData,
        budgetList,
        alertList,
        recList,
      ] = await Promise.allSettled([
        axios.get(`${API}/api/billing/current`),
        axios.get(`${API}/api/billing/history?days=2`),
        axios.get(`${API}/api/billing/services?days=7`),
        axios.get(`${API}/api/anomalies?page=1&page_size=50`),
        axios.get(`${API}/api/forecasts/latest`),
        axios.get(`${API}/api/budgets`),
        axios.get(`${API}/api/alerts?page=1&page_size=30`),
        axios.get(`${API}/api/recommendations`),
      ]);

      if (billingCurrent.status === 'fulfilled') setCurrentBilling(billingCurrent.value.data);
      if (billingHistory.status === 'fulfilled') setCostData(billingHistory.value.data || []);
      if (billingServices.status === 'fulfilled') setServices(billingServices.value.data || []);
      if (anomalyList.status === 'fulfilled') setAnomalies(anomalyList.value.data?.items || []);
      if (forecastData.status === 'fulfilled') setForecasts(forecastData.value.data);
      if (budgetList.status === 'fulfilled') setBudgets(budgetList.value.data || []);
      if (alertList.status === 'fulfilled') setAlerts(alertList.value.data?.items || []);
      if (recList.status === 'fulfilled') setRecommendations(recList.value.data || []);

      setLastRefresh(new Date());
    } catch (err) {
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    // Auto-refresh every 60 seconds
    const interval = setInterval(fetchAll, 60_000);
    return () => clearInterval(interval);
  }, []);

  // Build a map of service -> cost for BudgetHealth
  const costByService = {};
  services.forEach((s) => {
    costByService[s.service] = s.total_cost;
  });

  const handleTrigger = async (job) => {
    const endpoint = job === 'collect' ? '/api/trigger/collect' : '/api/trigger/detect';
    const label = job === 'collect' ? 'Collecting…' : 'Detecting…';
    setTriggerStatus(label);
    try {
      const res = await axios.post(`${API}${endpoint}`);
      const collected = res.data?.records_collected;
      setTriggerStatus(
        job === 'collect'
          ? `Done — ${collected ?? 0} records`
          : 'Detection started'
      );
      // Refresh immediately now that the collect call has finished
      await fetchAll();
    } catch {
      setTriggerStatus('Failed — is backend running?');
    } finally {
      setTimeout(() => setTriggerStatus(''), 4000);
    }
  };

  const unacknowledgedAlerts = alerts.filter((a) => !a.acknowledged).length;
  const defaultBudget = budgets[0]?.limit || 1000;

  return (
    <div style={styles.page}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.logo}>
          <div style={styles.logoIcon}>
            <span style={{ color: '#fff', fontSize: '16px' }}>A</span>
          </div>
          <div>
            <div style={styles.logoText}>AnomalyIQ</div>
            <div style={styles.subtitle}>AWS Cost Guardian</div>
          </div>
        </div>
        <div style={styles.headerRight}>
          <span style={styles.wsLabel}>
            <span
              style={{
                ...styles.wsDot,
                backgroundColor: wsConnected ? '#22c55e' : '#ef4444',
              }}
            />
            {wsConnected ? 'Live' : 'Disconnected'}
          </span>
          {lastRefresh && (
            <span style={{ fontSize: '11px', color: '#475569' }}>
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <div style={{ position: 'relative' }}>
            <div style={styles.bell} onClick={() => setShowNotifications((v) => !v)}>
              <span>&#128276;</span>
              {unacknowledgedAlerts > 0 && (
                <span style={styles.badge}>{unacknowledgedAlerts}</span>
              )}
            </div>
            {showNotifications && (
              <div style={{
                position: 'absolute',
                top: '36px',
                right: 0,
                width: '340px',
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '10px',
                boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                zIndex: 300,
                overflow: 'hidden',
              }}>
                <div style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid #334155',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                  <span style={{ fontWeight: '700', fontSize: '13px', color: '#f1f5f9' }}>
                    Notifications {unacknowledgedAlerts > 0 && (
                      <span style={{ color: '#ef4444' }}>({unacknowledgedAlerts} new)</span>
                    )}
                  </span>
                  <span
                    style={{ cursor: 'pointer', color: '#64748b', fontSize: '16px' }}
                    onClick={() => setShowNotifications(false)}
                  >✕</span>
                </div>
                <div style={{ maxHeight: '360px', overflowY: 'auto' }}>
                  {alerts.filter((a) => !a.acknowledged).length === 0 ? (
                    <div style={{ padding: '20px 16px', color: '#64748b', fontSize: '13px', textAlign: 'center' }}>
                      No unacknowledged alerts
                    </div>
                  ) : (
                    alerts.filter((a) => !a.acknowledged).map((alert) => {
                      const severityColors = {
                        Critical: { bg: '#450a0a', border: '#ef4444', text: '#fca5a5' },
                        High: { bg: '#431407', border: '#f97316', text: '#fdba74' },
                        Medium: { bg: '#422006', border: '#eab308', text: '#fde047' },
                        Low: { bg: '#0c1a3a', border: '#3b82f6', text: '#93c5fd' },
                      };
                      const c = severityColors[alert.severity] || severityColors.Low;
                      return (
                        <div key={alert._id} style={{
                          padding: '12px 16px',
                          borderBottom: '1px solid #1e293b',
                          borderLeft: `3px solid ${c.border}`,
                          backgroundColor: c.bg,
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                            <span style={{ fontSize: '11px', fontWeight: '700', color: c.text }}>
                              {alert.severity}
                            </span>
                            <span style={{ fontSize: '10px', color: '#475569' }}>
                              {new Date(alert.timestamp).toLocaleString()}
                            </span>
                          </div>
                          <div style={{ fontSize: '12px', color: '#cbd5e1', lineHeight: '1.4' }}>
                            {alert.message?.slice(0, 120)}{alert.message?.length > 120 ? '…' : ''}
                          </div>
                          <div style={{ fontSize: '10px', color: '#475569', marginTop: '4px' }}>
                            via {alert.channel}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>
          {triggerStatus && <span style={styles.triggerStatus}>{triggerStatus}</span>}
          <button
            style={{ ...styles.triggerBtn, backgroundColor: '#0f4c81', color: '#93c5fd' }}
            onClick={() => handleTrigger('collect')}
            disabled={!!triggerStatus}
            title="Force Agent 1 to pull latest AWS cost data now"
          >
            Collect Data
          </button>
          <button
            style={{ ...styles.triggerBtn, backgroundColor: '#3b1f6e', color: '#c4b5fd' }}
            onClick={() => handleTrigger('detect')}
            disabled={!!triggerStatus}
            title="Force Agent 2 to run anomaly detection now"
          >
            Detect Now
          </button>
          <button style={styles.refreshBtn} onClick={fetchAll} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      <div style={styles.main}>
        {/* Row 1: CostMeter + AnomalyTimeline */}
        <div style={{ ...styles.row, ...styles.row2 }}>
          <CostMeter
            currentSpend={currentBilling.total_cost || 0}
            budget={defaultBudget}
          />
          <AnomalyTimeline costHistory={costData} anomalies={anomalies} />
        </div>

        {/* Row 2: ServiceBreakdown + ForecastChart */}
        <div style={{ ...styles.row, ...styles.row2 }}>
          <ServiceBreakdown services={services} />
          <ForecastChart forecasts={forecasts} />
        </div>

        {/* Row 3: BudgetHealth (full width) */}
        <BudgetHealth budgets={budgets} currentCostByService={costByService} />

        {/* Row 4: AlertFeed + RecommendationCards */}
        <div style={{ ...styles.row, ...styles.row4 }}>
          <AlertFeed alerts={alerts} />
          <RecommendationCards recommendations={recommendations} />
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
