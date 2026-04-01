function generateCostHistory() {
  const points = [];
  const now = new Date();
  const baseHourlyCost = 2.8;

  for (let h = 47; h >= 0; h--) {
    const ts = new Date(now.getTime() - h * 3600 * 1000);
    const hourOfDay = ts.getHours();
    const dayFactor = hourOfDay >= 8 && hourOfDay <= 20 ? 1.4 : 0.7;
    const noise = (Math.random() - 0.5) * 1.2;
    const spike = (h === 12 || h === 28) ? 6.5 : 0;
    points.push({
      timestamp: ts.toISOString(),
      total_cost: Math.max(0.3, baseHourlyCost * dayFactor + noise + spike),
    });
  }
  return points;
}

function generateAnomalies() {
  const now = new Date();
  return [
    {
      _id: 'gcp-anom-001',
      timestamp: new Date(now.getTime() - 12 * 3600 * 1000).toISOString(),
      service: 'BigQuery',
      severity: 'Critical',
      expected_cost: 2.80,
      actual_cost: 9.30,
      deviation_pct: 232,
      root_cause: 'Unoptimized query scanning 4.2 TB across 3 datasets triggered by scheduled analytics pipeline.',
    },
    {
      _id: 'gcp-anom-002',
      timestamp: new Date(now.getTime() - 28 * 3600 * 1000).toISOString(),
      service: 'Compute Engine',
      severity: 'High',
      expected_cost: 3.10,
      actual_cost: 8.90,
      deviation_pct: 187,
      root_cause: 'Auto-scaler provisioned 12 additional n2-standard-4 instances due to traffic spike from load test.',
    },
    {
      _id: 'gcp-anom-003',
      timestamp: new Date(now.getTime() - 6 * 3600 * 1000).toISOString(),
      service: 'Cloud Storage',
      severity: 'Medium',
      expected_cost: 1.20,
      actual_cost: 3.50,
      deviation_pct: 191,
      root_cause: 'Multi-region replication triggered for 800 GB of new objects in production bucket.',
    },
  ];
}

function generateServices() {
  return [
    { service: 'Compute Engine', total_cost: 487.32 },
    { service: 'BigQuery', total_cost: 312.18 },
    { service: 'Cloud Storage', total_cost: 198.45 },
    { service: 'Cloud Run', total_cost: 145.67 },
    { service: 'GKE', total_cost: 134.20 },
    { service: 'Cloud SQL', total_cost: 98.50 },
    { service: 'Cloud Functions', total_cost: 67.80 },
    { service: 'Pub/Sub', total_cost: 34.25 },
    { service: 'Cloud CDN', total_cost: 28.90 },
    { service: 'Memorystore', total_cost: 22.15 },
  ];
}

function generateForecasts() {
  const predictions = [];
  const now = new Date();
  const baseDailyCost = 52;

  for (let d = 0; d < 30; d++) {
    const ds = new Date(now.getTime() + d * 86400 * 1000);
    const trend = d * 0.35;
    const weekday = ds.getDay();
    const weekendDip = (weekday === 0 || weekday === 6) ? -8 : 0;
    const noise = (Math.random() - 0.5) * 6;
    const yhat = baseDailyCost + trend + weekendDip + noise;
    predictions.push({
      ds: ds.toISOString(),
      yhat: Math.max(20, yhat),
      yhat_lower: Math.max(10, yhat - 12 - Math.random() * 5),
      yhat_upper: yhat + 12 + Math.random() * 5,
    });
  }

  return {
    predictions,
    model_used: 'prophet',
    mape: 8.3,
  };
}

function generateBudgets() {
  return [
    {
      _id: 'gcp-budget-001',
      name: 'GCP Monthly Total',
      limit: 2000,
      service_filter: null,
      budget_type: 'monthly',
    },
    {
      _id: 'gcp-budget-002',
      name: 'Compute Engine',
      limit: 600,
      service_filter: 'Compute Engine',
      budget_type: 'monthly',
    },
    {
      _id: 'gcp-budget-003',
      name: 'BigQuery',
      limit: 400,
      service_filter: 'BigQuery',
      budget_type: 'monthly',
    },
    {
      _id: 'gcp-budget-004',
      name: 'Cloud Storage',
      limit: 250,
      service_filter: 'Cloud Storage',
      budget_type: 'monthly',
    },
  ];
}

function generateAlerts() {
  const now = new Date();
  return [
    {
      _id: 'gcp-alert-001',
      severity: 'Critical',
      acknowledged: false,
      timestamp: new Date(now.getTime() - 1 * 3600 * 1000).toISOString(),
      message: 'BigQuery cost spike detected: $9.30/hr vs expected $2.80/hr. Unoptimized query scanning 4.2 TB across 3 datasets.',
      anomaly_id: 'gcp-anom-001',
      channel: 'email',
    },
    {
      _id: 'gcp-alert-002',
      severity: 'High',
      acknowledged: false,
      timestamp: new Date(now.getTime() - 4 * 3600 * 1000).toISOString(),
      message: 'Compute Engine auto-scaler provisioned 12 additional instances. Hourly cost jumped from $3.10 to $8.90.',
      anomaly_id: 'gcp-anom-002',
      channel: 'slack',
    },
    {
      _id: 'gcp-alert-003',
      severity: 'Medium',
      acknowledged: false,
      timestamp: new Date(now.getTime() - 6 * 3600 * 1000).toISOString(),
      message: 'Cloud Storage multi-region replication cost increased 191%. 800 GB of new objects replicated across regions.',
      anomaly_id: 'gcp-anom-003',
      channel: 'email',
    },
    {
      _id: 'gcp-alert-004',
      severity: 'Low',
      acknowledged: true,
      timestamp: new Date(now.getTime() - 12 * 3600 * 1000).toISOString(),
      message: 'Cloud Run cold start frequency increased by 45% in us-central1. Consider min-instances configuration.',
      anomaly_id: 'gcp-anom-004',
      channel: 'slack',
    },
    {
      _id: 'gcp-alert-005',
      severity: 'High',
      acknowledged: true,
      timestamp: new Date(now.getTime() - 24 * 3600 * 1000).toISOString(),
      message: 'GKE cluster node pool scaled to 18 nodes. Monthly projected cost exceeds budget by $340.',
      anomaly_id: 'gcp-anom-005',
      channel: 'email',
    },
  ];
}

function generateRecommendations() {
  return [
    {
      _id: 'gcp-rec-001',
      action: 'Use BigQuery slot reservations instead of on-demand pricing',
      estimated_savings: 156.00,
      detail: 'Current on-demand usage averages 2,400 slot-hours/day. A 500-slot flex commitment would reduce costs by ~50%.',
      service: 'BigQuery',
      region: 'us-central1',
      effort: 'medium',
      priority: 1,
    },
    {
      _id: 'gcp-rec-002',
      action: 'Apply committed use discounts for Compute Engine',
      estimated_savings: 142.50,
      detail: '8 n2-standard-4 instances have been running 24/7 for 45+ days. A 1-year CUD would save 37%.',
      service: 'Compute Engine',
      region: 'us-east1',
      effort: 'low',
      priority: 1,
    },
    {
      _id: 'gcp-rec-003',
      action: 'Move infrequently accessed Cloud Storage to Nearline',
      estimated_savings: 68.30,
      detail: '340 GB of objects in Standard class have not been accessed in 60+ days. Nearline pricing would reduce storage cost by 45%.',
      service: 'Cloud Storage',
      region: 'multi-region',
      effort: 'low',
      priority: 2,
    },
    {
      _id: 'gcp-rec-004',
      action: 'Right-size Cloud SQL instance from db-n1-standard-8 to db-n1-standard-4',
      estimated_savings: 49.25,
      detail: 'Average CPU utilization is 22% and memory usage is 31% over the last 14 days.',
      service: 'Cloud SQL',
      region: 'us-central1',
      effort: 'medium',
      priority: 2,
    },
    {
      _id: 'gcp-rec-005',
      action: 'Enable Cloud CDN for static assets served from Cloud Run',
      estimated_savings: 35.00,
      detail: 'Cloud Run serving 2.1M requests/day for static assets. CDN caching would reduce origin traffic by ~80%.',
      service: 'Cloud Run',
      region: 'us-central1',
      effort: 'low',
      priority: 3,
    },
  ];
}

export function getGcpMockData() {
  const services = generateServices();
  const totalSpend = services.reduce((sum, s) => sum + s.total_cost, 0);

  const costByService = {};
  services.forEach((s) => {
    costByService[s.service] = s.total_cost;
  });

  return {
    currentBilling: { total_cost: totalSpend },
    costHistory: generateCostHistory(),
    services,
    anomalies: generateAnomalies(),
    forecasts: generateForecasts(),
    budgets: generateBudgets(),
    alerts: generateAlerts(),
    recommendations: generateRecommendations(),
    costByService,
  };
}
