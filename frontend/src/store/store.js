import { create } from 'zustand';

// ---- Theme tokens ----
export const darkTheme = {
  pageBg: '#0f172a',
  headerBg: '#1e293b',
  cardBg: '#1e293b',
  cardInnerBg: '#0f172a',
  border: '#334155',
  borderSub: '#1e293b',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textMuted: '#64748b',
  textDimmer: '#475569',
  tooltipBg: '#0f172a',
  gridLine: '#1e293b',
  gridAxis: '#334155',
  barBg: '#334155',
  btnBg: '#334155',
  btnColor: '#94a3b8',
  btnBorder: '#475569',
  serviceName: '#e2e8f0',
  messageColor: '#cbd5e1',
};

export const lightTheme = {
  pageBg: '#f1f5f9',
  headerBg: '#ffffff',
  cardBg: '#ffffff',
  cardInnerBg: '#f8fafc',
  border: '#e2e8f0',
  borderSub: '#f1f5f9',
  textPrimary: '#0f172a',
  textSecondary: '#475569',
  textMuted: '#64748b',
  textDimmer: '#94a3b8',
  tooltipBg: '#ffffff',
  gridLine: '#f1f5f9',
  gridAxis: '#e2e8f0',
  barBg: '#e2e8f0',
  btnBg: '#f1f5f9',
  btnColor: '#475569',
  btnBorder: '#cbd5e1',
  serviceName: '#334155',
  messageColor: '#334155',
};

export const getTheme = (mode) => (mode === 'light' ? lightTheme : darkTheme);

// ---- Zustand store ----
const useStore = create((set) => ({
  // ---- State ----
  selectedProvider: 'aws',
  costData: [],
  anomalies: [],
  forecasts: null,
  budgets: [],
  alerts: [],
  recommendations: [],
  budgetWarnings: [],
  wsConnected: false,
  theme: 'dark',

  // ---- Actions ----
  setSelectedProvider: (provider) => set({ selectedProvider: provider }),

  setCostData: (data) => set({ costData: data }),

  addAnomaly: (anomaly) =>
    set((state) => ({
      anomalies: [anomaly, ...state.anomalies].slice(0, 200),
    })),

  setAnomalies: (anomalies) => set({ anomalies }),

  setForecasts: (forecasts) => set({ forecasts }),

  setBudgets: (budgets) => set({ budgets }),

  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, 100),
    })),

  setAlerts: (alerts) => set({ alerts }),

  setRecommendations: (recommendations) => set({ recommendations }),

  addBudgetWarning: (warning) =>
    set((state) => ({
      budgetWarnings: [warning, ...state.budgetWarnings].slice(0, 20),
    })),

  setWsConnected: (wsConnected) => set({ wsConnected }),

  acknowledgeAlert: (alertId) =>
    set((state) => ({
      alerts: state.alerts.map((a) =>
        a._id === alertId ? { ...a, acknowledged: true } : a
      ),
    })),

  toggleTheme: () =>
    set((state) => ({ theme: state.theme === 'dark' ? 'light' : 'dark' })),

}));

export default useStore;
