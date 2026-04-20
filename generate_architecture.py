"""Generates architecture.png for the SRE Hello World project."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(20, 14))
ax.set_xlim(0, 20)
ax.set_ylim(0, 14)
ax.axis("off")
fig.patch.set_facecolor("#0f1117")
ax.set_facecolor("#0f1117")

# ── Colour palette ────────────────────────────────────────────────────────────
C = {
    "bg":       "#0f1117",
    "surface":  "#1a1d27",
    "surface2": "#22263a",
    "border":   "#2e3350",
    "accent":   "#6c8ef7",
    "purple":   "#a78bfa",
    "green":    "#34d399",
    "yellow":   "#fbbf24",
    "red":      "#f87171",
    "orange":   "#fb923c",
    "text":     "#e2e8f0",
    "muted":    "#64748b",
    "teal":     "#2dd4bf",
    "pink":     "#f472b6",
}

# ── Helper: rounded box ───────────────────────────────────────────────────────
def box(ax, x, y, w, h, label, sublabel="", color=C["accent"],
        bg=C["surface"], icon=""):
    rect = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.06",
        linewidth=1.6,
        edgecolor=color,
        facecolor=bg,
        zorder=3,
    )
    ax.add_patch(rect)
    # top colour bar
    bar = FancyBboxPatch(
        (x - w / 2, y + h / 2 - 0.18), w, 0.18,
        boxstyle="round,pad=0.0",
        linewidth=0,
        facecolor=color,
        zorder=4,
        clip_on=True,
    )
    ax.add_patch(bar)
    # icon + label
    full_label = f"{icon}  {label}" if icon else label
    ax.text(x, y + (0.1 if sublabel else 0), full_label,
            ha="center", va="center", color=C["text"],
            fontsize=9, fontweight="bold", zorder=5)
    if sublabel:
        ax.text(x, y - 0.32, sublabel,
                ha="center", va="center", color=C["muted"],
                fontsize=7.5, zorder=5)


# ── Helper: arrow ─────────────────────────────────────────────────────────────
def arrow(ax, x1, y1, x2, y2, label="", color=C["muted"], style="->",
          lw=1.4, rad=0.0):
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle=style,
            color=color,
            lw=lw,
            connectionstyle=f"arc3,rad={rad}",
        ),
        zorder=2,
    )
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.08, my, label,
                ha="left", va="center", color=color,
                fontsize=7, style="italic", zorder=6)


# ── Helper: group lane ────────────────────────────────────────────────────────
def lane(ax, x, y, w, h, label, color):
    rect = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.1",
        linewidth=1,
        edgecolor=color,
        facecolor=color + "18",
        zorder=1,
    )
    ax.add_patch(rect)
    ax.text(x + 0.18, y + h - 0.22, label,
            ha="left", va="top", color=color,
            fontsize=7.5, fontweight="bold", zorder=2)


# ═════════════════════════════════════════════════════════════════════════════
# LAYOUT  (x, y  = centre of box)
# ═════════════════════════════════════════════════════════════════════════════

# ── Kubernetes cluster lane ───────────────────────────────────────────────────
lane(ax, 3.5, 0.6, 15.8, 12.6, "Kubernetes Cluster", C["border"])

# ── Namespace lanes ───────────────────────────────────────────────────────────
lane(ax, 3.8, 1.0, 7.0,  7.8,  "namespace: sre-demo",  C["accent"])
lane(ax, 3.8, 9.2, 7.0,  3.7,  "namespace: monitoring", C["green"])
lane(ax, 11.2, 1.0, 7.8, 4.2,  "namespace: redis",      C["red"])
lane(ax, 11.2, 5.6, 7.8, 7.3,  "namespace: monitoring (cont.)", C["green"])

# ── User ──────────────────────────────────────────────────────────────────────
box(ax, 1.5, 7.0, 2.2, 0.85, "Browser / User", "HTTP / HTTPS",
    color=C["muted"], bg=C["surface2"])

# ── Ingress ───────────────────────────────────────────────────────────────────
box(ax, 5.3, 7.0, 2.6, 0.85, "ingress-nginx", "IngressClass: nginx",
    color=C["yellow"])

# ── Frontend ──────────────────────────────────────────────────────────────────
box(ax, 5.3, 5.2, 2.6, 1.1, "Frontend", "nginx  |  2 pods\nHTML / JS SPA",
    color=C["purple"])

# ── Backend ───────────────────────────────────────────────────────────────────
box(ax, 5.3, 3.0, 2.6, 1.3, "Backend", "FastAPI  |  2-10 pods\nHPA (CPU 70% / Mem 80%)",
    color=C["accent"])

# ── HPA badge ─────────────────────────────────────────────────────────────────
hpa = FancyBboxPatch((6.4, 2.1), 1.2, 0.35,
                     boxstyle="round,pad=0.04", linewidth=1,
                     edgecolor=C["yellow"], facecolor="#2a2500", zorder=5)
ax.add_patch(hpa)
ax.text(7.0, 2.27, "HPA v2", ha="center", va="center",
        color=C["yellow"], fontsize=7, fontweight="bold", zorder=6)

# ── Redis HA ──────────────────────────────────────────────────────────────────
box(ax, 13.5, 2.8, 3.0, 1.3, "Redis HA (Sentinel)", "1 master + 2 replicas\nPDB minAvailable=2",
    color=C["red"])

# sentinel nodes
for i, (nx, ny, lbl) in enumerate([
    (12.2, 1.5, "master"),
    (13.5, 1.5, "replica-1"),
    (14.8, 1.5, "replica-2"),
]):
    clr = C["red"] if lbl == "master" else C["orange"]
    r = FancyBboxPatch((nx - 0.55, ny - 0.28), 1.1, 0.56,
                       boxstyle="round,pad=0.04", linewidth=1,
                       edgecolor=clr, facecolor=C["surface2"], zorder=3)
    ax.add_patch(r)
    ax.text(nx, ny, lbl, ha="center", va="center",
            color=clr, fontsize=7, fontweight="bold", zorder=4)

# ── Prometheus ────────────────────────────────────────────────────────────────
box(ax, 13.5, 7.5, 3.0, 1.1, "Prometheus", "retention: 15 d  |  20 Gi\nRecording + Alert rules",
    color=C["orange"])

# ── Alertmanager ──────────────────────────────────────────────────────────────
box(ax, 13.5, 9.8, 3.0, 1.0, "Alertmanager", "Slack + PagerDuty routing\nInhibit & burn-rate rules",
    color=C["yellow"])

# ── Grafana ───────────────────────────────────────────────────────────────────
box(ax, 17.5, 7.5, 2.4, 1.1, "Grafana", "SLI/SLO Dashboard\nConfigMap provisioning",
    color=C["orange"], bg=C["surface2"])

# ── Slack ─────────────────────────────────────────────────────────────────────
box(ax, 12.2, 12.0, 2.2, 0.85, "Slack", "#prod-alerts  (all)",
    color=C["green"], bg=C["surface2"])

# ── PagerDuty ─────────────────────────────────────────────────────────────────
box(ax, 15.0, 12.0, 2.2, 0.85, "PagerDuty", "critical -> on-call page",
    color=C["red"], bg=C["surface2"])

# ── Prometheus Operator ───────────────────────────────────────────────────────
box(ax, 5.5, 10.9, 3.0, 1.0, "Prometheus Operator", "Watches CRDs\nServiceMonitor / PrometheusRule",
    color=C["green"])

# ── CRD badges ────────────────────────────────────────────────────────────────
crd_items = [
    (4.5, 9.55, "ServiceMonitor"),
    (6.5, 9.55, "PrometheusRule"),
]
for cx, cy, lbl in crd_items:
    r = FancyBboxPatch((cx - 0.75, cy - 0.22), 1.5, 0.44,
                       boxstyle="round,pad=0.04", linewidth=1,
                       edgecolor=C["teal"], facecolor="#0d2e2e", zorder=3)
    ax.add_patch(r)
    ax.text(cx, cy, lbl, ha="center", va="center",
            color=C["teal"], fontsize=7, fontweight="bold", zorder=4)

# ═════════════════════════════════════════════════════════════════════════════
# ARROWS
# ═════════════════════════════════════════════════════════════════════════════

# User → Ingress
arrow(ax, 2.62, 7.0, 4.0, 7.0, color=C["muted"])
# Ingress → Frontend
arrow(ax, 5.3, 6.57, 5.3, 5.76, label="/", color=C["purple"])
# Ingress → Backend
arrow(ax, 5.3, 6.57, 5.3, 5.76, color=C["purple"])  # shared stem
arrow(ax, 5.3, 4.76, 5.3, 3.66, label="/api", color=C["accent"])
# Frontend → Backend (api proxy)
arrow(ax, 6.62, 5.2, 6.62, 3.66, label="proxy /api", color=C["accent"], rad=0.15)
# Backend → Redis
arrow(ax, 6.62, 3.0, 11.95, 2.8, label="get/set/del", color=C["red"])
# Backend → /metrics (Prometheus scrape)
arrow(ax, 6.62, 3.35, 11.95, 7.3, label="/metrics", color=C["orange"], rad=-0.25)
# Prometheus Operator → Prometheus (manages)
arrow(ax, 7.06, 10.9, 11.95, 7.8, label="manages", color=C["green"], rad=0.1)
# Prometheus Operator → ServiceMonitor
arrow(ax, 5.5, 10.4, 5.0, 9.77, color=C["teal"])
# Prometheus Operator → PrometheusRule
arrow(ax, 5.5, 10.4, 6.5, 9.77, color=C["teal"])
# Prometheus → Alertmanager
arrow(ax, 13.5, 6.94, 13.5, 10.3, label="fires alerts", color=C["yellow"])
# Prometheus → Grafana
arrow(ax, 15.01, 7.5, 16.28, 7.5, label="query", color=C["orange"])
# Alertmanager → Slack
arrow(ax, 12.5, 9.3, 12.2, 12.0 - 0.43, label="warning+critical", color=C["green"])
# Alertmanager → PagerDuty
arrow(ax, 14.5, 9.3, 15.0, 12.0 - 0.43, label="critical only", color=C["red"])
# Redis replicas sentinel lines
arrow(ax, 12.75, 2.15, 13.5, 2.16, color=C["orange"], style="-", lw=0.8)
arrow(ax, 13.5, 2.16, 14.25, 2.16, color=C["orange"], style="-", lw=0.8)

# ═════════════════════════════════════════════════════════════════════════════
# LEGEND
# ═════════════════════════════════════════════════════════════════════════════
legend_x, legend_y = 0.15, 13.5
ax.text(legend_x, legend_y, "Legend", color=C["text"],
        fontsize=8, fontweight="bold")
legend_items = [
    (C["accent"],  "App (sre-demo namespace)"),
    (C["red"],     "Redis HA (Sentinel)"),
    (C["orange"],  "Prometheus / Grafana"),
    (C["yellow"],  "Alertmanager"),
    (C["green"],   "Prometheus Operator / CRDs"),
    (C["teal"],    "Kubernetes CRDs"),
]
for i, (clr, lbl) in enumerate(legend_items):
    lx = legend_x
    ly = legend_y - 0.42 * (i + 1)
    ax.plot([lx, lx + 0.28], [ly, ly], color=clr, linewidth=2.5, solid_capstyle="round")
    ax.text(lx + 0.38, ly, lbl, color=C["muted"], fontsize=7.5, va="center")

# ── Title ─────────────────────────────────────────────────────────────────────
ax.text(10.0, 13.65, "SRE Hello World — Architecture",
        ha="center", va="center", color=C["text"],
        fontsize=15, fontweight="bold")
ax.text(10.0, 13.25, "Python/FastAPI  ·  Redis HA Sentinel  ·  Prometheus Operator  ·  Grafana  ·  Slack + PagerDuty",
        ha="center", va="center", color=C["muted"], fontsize=8.5)

plt.tight_layout(pad=0.2)
plt.savefig(
    "/home/izad/Documents/SRE-Hello-World/architecture.png",
    dpi=180,
    bbox_inches="tight",
    facecolor=fig.get_facecolor(),
)
print("Saved architecture.png")
