import { create } from 'zustand';

const useStore = create((set, get) => ({
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

}));

export default useStore;
