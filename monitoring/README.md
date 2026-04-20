# Monitoring Stack

This directory contains everything needed to stand up the full observability stack for the SRE Hello World project:
**Prometheus · Alertmanager · Grafana** — deployed via the Prometheus Operator using Helm and Kubernetes CRDs.

---

## Directory Layout

```
monitoring/
├── kube-prometheus-stack-values.yaml   # Helm values — installs Operator, Prometheus, Alertmanager, Grafana
├── alertmanager-config.yaml            # AlertmanagerConfig CRD — Slack + PagerDuty routing
├── alertmanager-secret.yaml            # Secret template — Slack webhook + PagerDuty integration key
├── grafana-dashboard-configmap.yaml    # ConfigMap — auto-provisions SLI/SLO dashboard into Grafana
├── grafana-dashboards/
│   └── sre-hello-world.json            # Raw Grafana dashboard JSON (import manually if needed)
└── prometheus.yml                      # Prometheus scrape config for docker-compose (local dev only)
```

---

## Prerequisites

| Tool | Minimum version | Check |
|------|----------------|-------|
| `kubectl` | 1.28 | `kubectl version --client` |
| `helm` | 3.14 | `helm version` |
| Kubernetes cluster | 1.28 | `kubectl cluster-info` |
| Storage class (for PVCs) | any | `kubectl get storageclass` |

---

## Deployment Order

```
1. Install kube-prometheus-stack  →  Operator + Prometheus + Alertmanager + Grafana
2. Create credential secrets       →  Slack webhook + PagerDuty key
3. Apply AlertmanagerConfig        →  Slack + PagerDuty routing
4. Apply Grafana dashboard         →  SLI/SLO dashboard auto-loaded
```

---

## Step 1 — Install kube-prometheus-stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --version 66.x \
  --values monitoring/kube-prometheus-stack-values.yaml

# Wait for all pods to be Running (~2 min)
kubectl get pods -n monitoring -w
```

### What gets installed

| Component | Kind | Description |
|-----------|------|-------------|
| Prometheus Operator | Deployment | Watches CRDs and manages Prometheus/Alertmanager instances |
| Prometheus | `Prometheus` CRD | Scrapes metrics, evaluates recording + alert rules |
| Alertmanager | `Alertmanager` CRD | Routes alerts to Slack and PagerDuty |
| Grafana | Deployment | Visualises metrics; sidecar auto-loads dashboards from ConfigMaps |
| kube-state-metrics | Deployment | Kubernetes object metrics (pod status, deployment replicas, etc.) |
| node-exporter | DaemonSet | Node-level metrics (CPU, memory, disk, network) |
| Default rules | `PrometheusRule` CRDs | Kubernetes system alerts (APIServer SLOs, node alerts, etc.) |

### Key selector policies (set in values)

```yaml
serviceMonitorSelectorNilUsesHelmValues: false
serviceMonitorNamespaceSelector: {}    # watch ALL namespaces
ruleNamespaceSelector: {}              # pick up PrometheusRules from ALL namespaces
```

These ensure the `ServiceMonitor` and `PrometheusRule` deployed by the app's Helm chart (in the `sre-demo` namespace) are automatically discovered without any extra configuration.

---

## Step 2 — Create Credential Secrets

All sensitive values are stored in Kubernetes Secrets and referenced by name from the `AlertmanagerConfig` — no credentials ever appear in YAML committed to git.

### Slack

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create App** → **From scratch**
2. Enable **Incoming Webhooks** → **Add New Webhook to Workspace** → select `#prod-alerts`
3. Copy the webhook URL (`https://hooks.slack.com/services/T.../B.../...`)

```bash
kubectl create secret generic alertmanager-slack-secret \
  --from-literal=webhook-url='https://hooks.slack.com/services/TXXX/BXXX/xxxx' \
  --namespace sre-demo
```

### PagerDuty

1. In PagerDuty go to **Services** → your service → **Integrations** tab
2. **Add Integration** → select **Events API v2**
3. Copy the **Integration Key** (32-character hex string)

```bash
kubectl create secret generic alertmanager-pagerduty-secret \
  --from-literal=routing-key='your-32-char-integration-key' \
  --namespace sre-demo
```

> **Production tip:** Use [External Secrets Operator](https://external-secrets.io) or [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) to sync these from Vault / AWS Secrets Manager rather than running `kubectl create secret` manually.

---

## Step 3 — Apply AlertmanagerConfig

```bash
# Namespace must exist first
kubectl create namespace sre-demo --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f monitoring/alertmanager-config.yaml --namespace sre-demo

# Verify the sub-route was merged into the global Alertmanager config
kubectl port-forward svc/kube-prometheus-stack-alertmanager 9093:9093 -n monitoring &
curl -s http://localhost:9093/api/v1/status | jq '.data.configJSON | fromjson | .route.routes'
# You should see a route with matchers: namespace="sre-demo"
```

### Alert routing summary

| Severity | PagerDuty | Slack `#prod-alerts` | Repeat interval |
|----------|:---------:|:--------------------:|-----------------|
| `critical` | Pages on-call immediately | Also posted | 1 h |
| `warning` | — | Posted | 12 h |
| all others | — | Posted | 4 h |

**Inhibit rule:** when a `critical` alert fires, the matching `warning` for the same `alertname` is suppressed to avoid duplicate noise.

### Slack message format

Critical messages include:
- Alert name, summary, and description
- SLO label (`availability` / `latency`)
- Per-alert label dump for quick triage
- Action buttons → **Prometheus alerts page** and **Grafana SLO dashboard**

---

## Step 4 — Apply Grafana Dashboard

The dashboard ConfigMap is labelled `grafana_dashboard: "1"`. The Grafana sidecar (`sidecar.dashboards.enabled: true` in values) detects it across all namespaces and hot-loads it — no Grafana restart needed.

```bash
kubectl apply -f monitoring/grafana-dashboard-configmap.yaml --namespace monitoring

# Access Grafana
kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring
# http://localhost:3000  →  admin / changeme  (set GF_SECURITY_ADMIN_PASSWORD in values)
# Navigate: Dashboards → Browse → SRE → "SRE Hello World — SLI/SLO"
```

### Dashboard panels

| Row | Panels |
|-----|--------|
| **SLO Overview** | Availability %, Error Rate %, P95 latency gauge, P99 latency gauge, Error Budget remaining (30 d), Throughput (RPS) |
| **Traffic & Latency** | Request rate by status code (2xx / 4xx / 5xx); Latency percentiles P50 / P95 / P99 over time |
| **Error Budget Burn** | Multi-window error ratio (1 h and 6 h); Burn rate multiples with SLO threshold line |
| **Redis** | Key count, Cache hit rate gauge, P99 op latency gauge, Ops/s by operation type |

---

## Verifying the Full Pipeline

```bash
# 1. Prometheus targets — backend job should show State: UP
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring
# http://localhost:9090/targets  →  sre-hello-world-backend

# 2. Recording rules loaded
# http://localhost:9090/rules  →  group: sre-hello-world.recording

# 3. Alert rules loaded (all Inactive = system is healthy)
# http://localhost:9090/alerts  →  AvailabilitySLOFastBurn, LatencyP99SLOBreach, ...

# 4. Fire synthetic errors to trigger AvailabilitySLOFastBurn (fires after ~1 min)
for i in $(seq 1 60); do
  curl -s "http://localhost:8000/api/simulate/error?rate=1.0" &
done; wait
# Watch in Prometheus: job:http_error_ratio:rate5m
# Expect: Slack message in #prod-alerts + PagerDuty incident opened

# 5. Trigger latency breach
for i in $(seq 1 10); do
  curl -s "http://localhost:8000/api/simulate/slow?delay=3.0" &
done; wait
# Expect: LatencyP99SLOBreach fires after 5 min → Slack warning message
```

---

## Upgrading the Stack

```bash
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values monitoring/kube-prometheus-stack-values.yaml \
  --version 66.x
```

> Check the [chart changelog](https://github.com/prometheus-community/helm-charts/blob/main/charts/kube-prometheus-stack/CHANGELOG.md) before upgrading — CRD schema changes occasionally require manual migration steps.

---

## Uninstalling

```bash
helm uninstall kube-prometheus-stack -n monitoring

# CRDs are NOT deleted by helm uninstall — remove manually if needed
kubectl get crds | grep monitoring.coreos.com | awk '{print $1}' | xargs kubectl delete crd
```
