import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import useStore from '../store/store';
import CostMeter from '../components/CostMeter';
import AnomalyTimeline from '../components/AnomalyTimeline';
import ServiceBreakdown from '../components/ServiceBreakdown';
import ForecastChart from '../components/ForecastChart';
import GcpBudgetHealth from '../components/GcpBudgetHealth';
import GcpAlertFeed from '../components/GcpAlertFeed';
import RecommendationCards from '../components/RecommendationCards';

const API = 'http://localhost:8000';

const styles = {
  page: { padding: '0', minHeight: '100vh', backgroundColor: '#0f172a' },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '16px 24px', backgroundColor: '#1e293b',
    borderBottom: '1px solid #334155', position: 'sticky', top: 0, zIndex: 100,
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: '12px' },
  backBtn: {
    display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 14px',
    borderRadius: '8px', border: '1px solid #334155', backgroundColor: 'transparent',
    color: '#94a3b8', fontSize: '13px', fontWeight: '500', cursor: 'pointer',
  },
  logo: { display: 'flex', alignItems: 'center', gap: '10px' },
  logoIcon: {
    width: '32px', height: '32px', borderRadius: '8px',
    background: 'linear-gradient(135deg, #4285f4, #34a853)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  logoText: {
    fontSize: '20px', fontWeight: '800',
    background: 'linear-gradient(135deg, #4285f4, #34a853)',
    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
  },
  subtitle: { fontSize: '12px', color: '#475569', marginTop: '1px' },
  headerRight: { display: 'flex', alignItems: 'center', gap: '16px' },
  liveBadge: {
    fontSize: '11px', fontWeight: '600', padding: '4px 12px', borderRadius: '20px',
    backgroundColor: 'rgba(34,197,94,0.12)', color: '#22c55e',
    border: '1px solid rgba(34,197,94,0.3)',
  },
  triggerBtn: {
    padding: '6px 14px', borderRadius: '6px', fontSize: '12px',
    fontWeight: '600', cursor: 'pointer', border: 'none',
  },
  refreshBtn: {
    padding: '6px 14px', borderRadius: '6px', fontSize: '12px',
    fontWeight: '600', cursor: 'pointer', backgroundColor: '#334155',
    color: '#94a3b8', border: '1px solid #475569',
  },
  triggerStatus: { fontSize: '11px', color: '#64748b', fontStyle: 'italic' },
  bell: { position: 'relative', cursor: 'pointer', fontSize: '20px', padding: '4px' },
  badge: {
    position: 'absolute', top: '-2px', right: '-4px', backgroundColor: '#ef4444',
    color: '#fff', borderRadius: '10px', fontSize: '10px', fontWeight: '700',
    padding: '1px 5px', minWidth: '16px', textAlign: 'center',
  },
  main: { padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '20px' },
  row: { display: 'grid', gap: '20px' },
  row2: { gridTemplateColumns: '1fr 1fr' },
};

function GcpDashboard() {
  const navigate = useNavigate();
  const { wsConnected } = useStore();

  const [currentBilling, setCurrentBilling] = useState({ total_cost: 0 });
  const [costData, setCostData] = useState([]);
  const [services, setServices] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [forecasts, setForecasts] = useState(null);
  const [budgets, setBudgets] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [triggerStatus, setTriggerStatus] = useState('');
  const [showNotifications, setShowNotifications] = useState(false);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [billing, history, svc, anom, fc, bdg, alt, rec] = await Promise.allSettled([
        axios.get(`${API}/api/gcp/billing/current`),
        axios.get(`${API}/api/gcp/billing/history?days=2`),
        axios.get(`${API}/api/gcp/billing/services?days=7`),
        axios.get(`${API}/api/gcp/anomalies?page=1&page_size=50`),
        axios.get(`${API}/api/gcp/forecasts/latest`),
        axios.get(`${API}/api/gcp/budgets`),
        axios.get(`${API}/api/gcp/alerts?page=1&page_size=30`),
        axios.get(`${API}/api/gcp/recommendations`),
      ]);
      if (billing.status === 'fulfilled') setCurrentBilling(billing.value.data);
      if (history.status === 'fulfilled') setCostData(history.value.data || []);
      if (svc.status === 'fulfilled') setServices(svc.value.data || []);
      if (anom.status === 'fulfilled') setAnomalies(anom.value.data?.items || []);
      if (fc.status === 'fulfilled') setForecasts(fc.value.data);
      if (bdg.status === 'fulfilled') setBudgets(bdg.value.data || []);
      if (alt.status === 'fulfilled') setAlerts(alt.value.data?.items || []);
      if (rec.status === 'fulfilled') setRecommendations(rec.value.data || []);
      setLastRefresh(new Date());
    } catch (err) {
      console.error('GCP Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 60_000);
    return () => clearInterval(interval);
  }, []);

  const costByService = {};
  services.forEach((s) => { costByService[s.service] = s.total_cost; });

  const handleTrigger = async (job) => {
    const endpoint = job === 'collect' ? '/api/gcp/trigger/collect' : '/api/gcp/trigger/detect';
    const label = job === 'collect' ? 'Collecting…' : 'Detecting…';
    setTriggerStatus(label);
    try {
      const res = await axios.post(`${API}${endpoint}`);
      const collected = res.data?.records_collected;
      setTriggerStatus(job === 'collect' ? `Done — ${collected ?? 0} records` : 'Detection started');
      await fetchAll();
    } catch { setTriggerStatus('Failed — is backend running?'); }
    finally { setTimeout(() => setTriggerStatus(''), 4000); }
  };

  const unacknowledgedAlerts = alerts.filter((a) => !a.acknowledged).length;
  const defaultBudget = budgets[0]?.limit || 2000;

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <button style={styles.backBtn} onClick={() => navigate('/')}>&larr; Back</button>
          <div style={styles.logo}>
            <div style={styles.logoIcon}>
              <svg width="18" height="18" viewBox="0 0 32 32" fill="none">
                <path d="M16 8l7 4v8l-7 4-7-4v-8l7-4z" stroke="#fff" strokeWidth="2" fill="none"/>
                <circle cx="16" cy="16" r="3" stroke="#fff" strokeWidth="1.5" fill="none"/>
              </svg>
            </div>
            <div>
              <div style={styles.logoText}>AnomalyIQ</div>
              <div style={styles.subtitle}>GCP Cost Guardian</div>
            </div>
          </div>
        </div>
        <div style={styles.headerRight}>
          <span style={styles.liveBadge}>● Live</span>
          {lastRefresh && (
            <span style={{ fontSize: '11px', color: '#475569' }}>
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <div style={{ position: 'relative' }}>
            <div style={styles.bell} onClick={() => setShowNotifications((v) => !v)}>
              <span>&#128276;</span>
              {unacknowledgedAlerts > 0 && <span style={styles.badge}>{unacknowledgedAlerts}</span>}
            </div>
            {showNotifications && (
              <div style={{
                position: 'absolute', top: '36px', right: 0, width: '340px',
                backgroundColor: '#1e293b', border: '1px solid #334155',
                borderRadius: '10px', boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                zIndex: 300, overflow: 'hidden',
              }}>
                <div style={{
                  padding: '12px 16px', borderBottom: '1px solid #334155',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}>
                  <span style={{ fontWeight: '700', fontSize: '13px', color: '#f1f5f9' }}>
                    Notifications {unacknowledgedAlerts > 0 && (
                      <span style={{ color: '#ef4444' }}>({unacknowledgedAlerts} new)</span>
                    )}
                  </span>
                  <span style={{ cursor: 'pointer', color: '#64748b', fontSize: '16px' }}
                    onClick={() => setShowNotifications(false)}>✕</span>
                </div>
                <div style={{ maxHeight: '360px', overflowY: 'auto' }}>
                  {alerts.filter((a) => !a.acknowledged).length === 0 ? (
                    <div style={{ padding: '20px 16px', color: '#64748b', fontSize: '13px', textAlign: 'center' }}>
                      No unacknowledged alerts
                    </div>
                  ) : alerts.filter((a) => !a.acknowledged).map((alert) => {
                    const sc = {
                      Critical: { bg: '#450a0a', border: '#ef4444', text: '#fca5a5' },
                      High: { bg: '#431407', border: '#f97316', text: '#fdba74' },
                      Medium: { bg: '#422006', border: '#eab308', text: '#fde047' },
                      Low: { bg: '#0c1a3a', border: '#3b82f6', text: '#93c5fd' },
                    };
                    const c = sc[alert.severity] || sc.Low;
                    return (
                      <div key={alert._id} style={{
                        padding: '12px 16px', borderBottom: '1px solid #1e293b',
                        borderLeft: `3px solid ${c.border}`, backgroundColor: c.bg,
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ fontSize: '11px', fontWeight: '700', color: c.text }}>{alert.severity}</span>
                          <span style={{ fontSize: '10px', color: '#475569' }}>
                            {new Date(alert.timestamp).toLocaleString()}
                          </span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#cbd5e1', lineHeight: '1.4' }}>
                          {alert.message?.slice(0, 120)}{alert.message?.length > 120 ? '…' : ''}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
          {triggerStatus && <span style={styles.triggerStatus}>{triggerStatus}</span>}
          <button
            style={{ ...styles.triggerBtn, backgroundColor: '#1a5632', color: '#86efac' }}
            onClick={() => handleTrigger('collect')}
            disabled={!!triggerStatus}
          >Collect Data</button>
          <button
            style={{ ...styles.triggerBtn, backgroundColor: '#1e3a5f', color: '#93c5fd' }}
            onClick={() => handleTrigger('detect')}
            disabled={!!triggerStatus}
          >Detect Now</button>
          <button style={styles.refreshBtn} onClick={fetchAll} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      <div style={styles.main}>
        <div style={{ ...styles.row, ...styles.row2 }}>
          <CostMeter currentSpend={currentBilling.total_cost || 0} budget={defaultBudget} />
          <AnomalyTimeline costHistory={costData} anomalies={anomalies} />
        </div>
        <div style={{ ...styles.row, ...styles.row2 }}>
          <ServiceBreakdown services={services} />
          <ForecastChart forecasts={forecasts} />
        </div>
        <GcpBudgetHealth budgets={budgets} currentCostByService={costByService} />
        <div style={{ ...styles.row, ...styles.row2 }}>
          <GcpAlertFeed alerts={alerts} />
          <RecommendationCards recommendations={recommendations} />
        </div>
      </div>
    </div>
  );
}

export default GcpDashboard;
