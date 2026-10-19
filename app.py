import io
import hashlib
from datetime import datetime, timezone
import json
import os
import random
import re
import sqlite3
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from datetime import date

import pandas as pd
import streamlit as st

try:
    import boto3
except ImportError:  # pragma: no cover - optional dependency for real cloud access
    boto3 = None

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency for real cloud access
    requests = None

try:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
except ImportError:  # pragma: no cover - optional dependency for real cloud access
    Request = None
    service_account = None

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency for AI analysis
    OpenAI = None

try:
    import httpx
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - optional dependency for LangChain AI analysis
    httpx = None
    ChatOpenAI = None


st.set_page_config(
    page_title="Multi-Cloud Billing Dashboard",
    page_icon="💰",
    layout="wide",
)


st.markdown(
    """
    <style>
    /* Readable, consistent LIGHT dashboard palette across Streamlit themes. */
    :root { --dash-ink:#15263d; --dash-muted:#4b6078; --dash-bg:#f3f6fb;
      --dash-paper:#ffffff; --dash-border:#d2dce8; --dash-accent:#1659b7; }
    html, body, [data-testid="stAppViewContainer"], .stApp {
      background:var(--dash-bg) !important;
      color:var(--dash-ink) !important;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    }
    [data-testid="stHeader"] { background:rgba(243,246,251,.95) !important; }
    [data-testid="stSidebar"], [data-testid="stSidebar"] > div {
      background:#e9eff7 !important; color:var(--dash-ink) !important;
    }
    [data-testid="stSidebar"] * { color:var(--dash-ink); }
    .block-container { padding-top:2rem; padding-bottom:3rem; max-width:1450px; }
    h1, h2, h3, h4, h5, h6,
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stMarkdownContainer"] h4 {
      color:#112b4a !important; font-weight:750 !important;
      letter-spacing:-.016em; line-height:1.25;
    }
    h1 { font-size:clamp(1.75rem,3vw,2.35rem) !important; }
    h2 { font-size:1.55rem !important; }
    h3 { font-size:1.27rem !important; }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] strong,
    [data-testid="stText"], [data-testid="stWidgetLabel"] {
      color:var(--dash-ink) !important; font-size:1rem; line-height:1.55;
    }
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p,
    div[data-testid="stMetricDelta"] { color:var(--dash-muted) !important; font-size:.9rem !important; }
    label, [data-testid="stWidgetLabel"] p { color:var(--dash-ink) !important; font-weight:650; }
    [data-testid="stMetric"] {
      background:var(--dash-paper); border:1px solid var(--dash-border);
      border-radius:12px; padding:15px 18px; min-height:100px;
      box-shadow:0 2px 7px rgba(15,37,65,.04);
    }
    [data-testid="stMetricLabel"] *, [data-testid="stMetricLabel"] {
      color:var(--dash-muted) !important; font-size:.92rem !important; font-weight:650 !important;
    }
    [data-testid="stMetricValue"] *, [data-testid="stMetricValue"] {
      color:#12345c !important; font-size:clamp(1.2rem,2vw,1.8rem) !important;
      font-weight:800 !important; letter-spacing:-.02em;
    }
    [data-testid="stDataFrame"], .stDataFrame { border:1px solid var(--dash-border); border-radius:10px; overflow:hidden; }
    /* Improve input contrast, including selectors and numeric values. */
    [data-baseweb="input"] > div, [data-baseweb="select"] > div,
    [data-baseweb="textarea"] > div { background:#fff !important; border-color:#9eafc4 !important; }
    [data-baseweb="input"] input, [data-baseweb="select"] *,
    [data-baseweb="textarea"] textarea { color:#122c4b !important; }
    [data-testid="stButton"] button, [data-testid="stDownloadButton"] button {
      background:#1557b0 !important; color:#fff !important;
      border:1px solid #104993 !important; border-radius:9px;
      font-weight:700 !important; min-height:43px;
    }
    [data-testid="stButton"] button *, [data-testid="stDownloadButton"] button * { color:#fff !important; }
    [data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover {
      background:#0c3f83 !important; border-color:#0c3f83 !important;
    }
    [data-testid="stAlert"] { border-radius:9px; }
    [data-testid="stAlert"] p { color:#23364c !important; }
    hr { border-color:var(--dash-border) !important; }
    .ai-highlight {
      background:#fff; border:1px solid var(--dash-border);
      border-left:4px solid var(--dash-accent); border-radius:10px;
      padding:1rem 1.25rem; color:var(--dash-ink);
      box-shadow:0 3px 8px rgba(18,45,81,.05); line-height:1.65;
    }
    .ai-highlight strong, .ai-header { color:#133c74; font-weight:800; }
    .ai-highlight span, .ai-highlight small { color:#30475f; }
    .ai-header { font-size:1.1rem; display:block; margin-bottom:.45rem; }
    /* Keep chart headings/legends legible while respecting Vega's own plot palette. */
    [data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] {
      background:#fff; border:1px solid var(--dash-border);
      border-radius:10px; padding:.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def generate_demo_cloud_data(seed=0):
    rng = random.Random(seed)

    aws_base = [4200, 5100, 4700, 5800, 6400, 7100]
    gcp_base = [2600, 2900, 3200, 3600, 4200, 4800]
    aws_monthly = [max(2800, value + rng.randint(-300, 350)) for value in aws_base]
    gcp_monthly = [max(2200, value + rng.randint(-250, 300)) for value in gcp_base]

    monthly = pd.DataFrame(
        {
            "Month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "AWS": aws_monthly,
            "GCP": gcp_monthly,
        }
    )

    aws_services = pd.DataFrame(
        [
            {"Service": "Amazon EC2", "Spend": 2600.0 + rng.randint(50, 400), "Forecast": 2800.0 + rng.randint(50, 350)},
            {"Service": "Amazon S3", "Spend": 920.0 + rng.randint(40, 180), "Forecast": 980.0 + rng.randint(50, 200)},
            {"Service": "Amazon RDS", "Spend": 1180.0 + rng.randint(60, 220), "Forecast": 1260.0 + rng.randint(80, 260)},
            {"Service": "AWS Lambda", "Spend": 460.0 + rng.randint(20, 120), "Forecast": 500.0 + rng.randint(30, 140)},
            {"Service": "Amazon CloudFront", "Spend": 360.0 + rng.randint(20, 100), "Forecast": 420.0 + rng.randint(30, 130)},
        ]
    )

    gcp_budgets = pd.DataFrame(
        [
            {"Budget": "Compute Engine", "Spend": 1750.0 + rng.randint(80, 260), "Forecast": 1900.0 + rng.randint(120, 330)},
            {"Budget": "Cloud Storage", "Spend": 760.0 + rng.randint(40, 180), "Forecast": 820.0 + rng.randint(60, 200)},
            {"Budget": "BigQuery", "Spend": 980.0 + rng.randint(60, 200), "Forecast": 1080.0 + rng.randint(80, 230)},
            {"Budget": "Cloud Run", "Spend": 365.0 + rng.randint(20, 90), "Forecast": 430.0 + rng.randint(30, 120)},
            {"Budget": "Networking", "Spend": 470.0 + rng.randint(30, 120), "Forecast": 520.0 + rng.randint(40, 140)},
        ]
    )

    region_costs = pd.DataFrame(
        [
            {"Cloud": "AWS", "Region": "us-east-1", "Cost": 18500 + rng.randint(0, 2000), "Status": "Highest cost"},
            {"Cloud": "AWS", "Region": "us-west-2", "Cost": 13200 + rng.randint(-400, 800), "Status": "Lower cost"},
            {"Cloud": "AWS", "Region": "eu-central-1", "Cost": 14900 + rng.randint(-500, 1000), "Status": "Moderate cost"},
            {"Cloud": "AWS", "Region": "ap-south-1", "Cost": 11700 + rng.randint(-300, 700), "Status": "Low cost"},
            {"Cloud": "GCP", "Region": "us-central1", "Cost": 12600 + rng.randint(0, 1600), "Status": "Higher cost"},
            {"Cloud": "GCP", "Region": "europe-west1", "Cost": 10100 + rng.randint(-300, 900), "Status": "Moderate cost"},
            {"Cloud": "GCP", "Region": "asia-southeast1", "Cost": 8800 + rng.randint(-200, 600), "Status": "Lowest cost"},
        ]
    )

    utilisation = {
        "AWS": {
            "EC2_cpu_percent": 22 + rng.randint(0, 18),
            "RDS_cpu_percent": 30 + rng.randint(0, 18),
            "Lambda_idle_hours": 14 + rng.randint(0, 12),
            "Storage_access_age_days": 80 + rng.randint(0, 25),
            "Data_transfer_cost": 620 + rng.randint(0, 180),
        },
        "GCP": {
            "Compute_cpu_percent": 25 + rng.randint(0, 18),
            "BigQuery_slot_usage": 68 + rng.randint(0, 20),
            "CloudRun_scale_to_zero": True,
            "Idle_vms": 2 + rng.randint(0, 3),
            "Network_egress_cost": 500 + rng.randint(0, 150),
        },
    }

    resource_intensity = pd.DataFrame(
        [
            {"Cloud": "AWS", "Category": "Compute", "Score": 82, "Status": "High"},
            {"Cloud": "AWS", "Category": "Storage", "Score": 58, "Status": "Moderate"},
            {"Cloud": "AWS", "Category": "Network", "Score": 64, "Status": "Moderate"},
            {"Cloud": "GCP", "Category": "Compute", "Score": 74, "Status": "High"},
            {"Cloud": "GCP", "Category": "Analytics", "Score": 88, "Status": "Very high"},
            {"Cloud": "GCP", "Category": "Network", "Score": 60, "Status": "Moderate"},
        ]
    )

    instance_inventory = [
        {"Cloud": "AWS", "Region": "us-east-1", "InstanceType": "m5.large", "Count": 12, "AvgCpuPercent": 12, "IdleHours": 180, "Status": "Idle too long", "SuggestedInstanceType": "m5.large"},
        {"Cloud": "AWS", "Region": "us-west-2", "InstanceType": "c5.xlarge", "Count": 6, "AvgCpuPercent": 18, "IdleHours": 150, "Status": "Low utilization", "SuggestedInstanceType": "c5.large"},
        {"Cloud": "AWS", "Region": "eu-central-1", "InstanceType": "r5.xlarge", "Count": 4, "AvgCpuPercent": 23, "IdleHours": 120, "Status": "Underused", "SuggestedInstanceType": "r5.large"},
        {"Cloud": "GCP", "Region": "us-central1", "InstanceType": "n2-standard-4", "Count": 9, "AvgCpuPercent": 16, "IdleHours": 165, "Status": "Idle too long", "SuggestedInstanceType": "e2-standard-2"},
        {"Cloud": "GCP", "Region": "europe-west1", "InstanceType": "n2-standard-8", "Count": 5, "AvgCpuPercent": 22, "IdleHours": 140, "Status": "Low utilization", "SuggestedInstanceType": "n2-standard-4"},
        {"Cloud": "GCP", "Region": "asia-southeast1", "InstanceType": "e2-standard-4", "Count": 3, "AvgCpuPercent": 28, "IdleHours": 110, "Status": "Underused", "SuggestedInstanceType": "e2-standard-2"},
    ]

    idle_resources = {
        "AWS": [
            {"Resource": "Stopped instances", "Region": "us-east-1", "Count": 2 + rng.randint(0, 4)},
            {"Resource": "Unused load balancers", "Region": "us-west-2", "Count": 1 + rng.randint(0, 2)},
            {"Resource": "Unattached EBS volumes", "Region": "eu-central-1", "Count": 4 + rng.randint(0, 5)},
            {"Resource": "NAT gateways", "Region": "ap-south-1", "Count": 1 + rng.randint(0, 2)},
        ],
        "GCP": [
            {"Resource": "Idle VM instances", "Region": "us-central1", "Count": 2 + rng.randint(0, 3)},
            {"Resource": "Unused disks", "Region": "europe-west1", "Count": 3 + rng.randint(0, 4)},
            {"Resource": "Stale snapshots", "Region": "asia-southeast1", "Count": 4 + rng.randint(0, 4)},
            {"Resource": "Idle static IPs", "Region": "us-central1", "Count": 1 + rng.randint(0, 2)},
        ],
    }

    return {
        "monthly": monthly,
        "aws_services": aws_services,
        "gcp_budgets": gcp_budgets,
        "region_costs": region_costs,
        "utilisation": utilisation,
        "resource_intensity": resource_intensity,
        "instance_inventory": instance_inventory,
        "idle_resources": idle_resources,
    }


@st.cache_data
def _demo_region_costs():
    return generate_demo_cloud_data()["region_costs"]


@st.cache_data
def _demo_data():
    demo = generate_demo_cloud_data()
    return demo["monthly"], demo["aws_services"], demo["gcp_budgets"]


def _aws_demo_data():
    _, aws_services, _ = _demo_data()
    return aws_services, float(aws_services["Spend"].sum())


def _gcp_demo_data():
    _, _, gcp_budgets = _demo_data()
    return gcp_budgets, float(gcp_budgets["Spend"].sum())


def aws_costs_last_30_days():
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key or not aws_secret_key or boto3 is None:
        return _aws_demo_data()

    try:
        client = boto3.client(
            "ce",
            region_name="us-east-1",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
        )

        end_date = date.today().strftime("%Y-%m-%d")
        start_date = (date.today().replace(day=1)).strftime("%Y-%m-%d")

        response = client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        rows = []
        for result in response.get("ResultsByTime", []):
            for group in result.get("Groups", []):
                service_name = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                rows.append({"Service": service_name, "Spend": amount, "Currency": "USD"})
        if not rows:
            return pd.DataFrame(columns=["Service", "Spend", "Currency"]), 0.0
        df = pd.DataFrame(rows)
        return df, float(df["Spend"].sum())
    except Exception:
        return _aws_demo_data()


def gcp_costs_last_30_days():
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if not creds_path or service_account is None or Request is None or requests is None:
        return _gcp_demo_data()

    try:
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-billing.readonly"],
        )
        credentials.refresh(Request())
        token = credentials.token
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        accounts_response = requests.get(
            "https://cloudbilling.googleapis.com/v1/billingAccounts",
            headers=headers,
            timeout=30,
        )
        accounts_response.raise_for_status()
        accounts = accounts_response.json().get("billingAccounts", [])

        rows = []
        for account in accounts:
            account_name = account.get("name", "")
            account_id = account_name.split("/")[-1] if account_name else "unknown"
            budget_url = f"https://billingbudgets.googleapis.com/v1/billingAccounts/{account_id}/budgets"
            budget_response = requests.get(budget_url, headers=headers, timeout=30)
            budget_response.raise_for_status()
            budgets = budget_response.json().get("budgets", [])
            for budget in budgets:
                current_spend = budget.get("currentSpend", {})
                amount = float(current_spend.get("amount", 0) or 0)
                rows.append(
                    {
                        "Budget": budget.get("displayName", "Unnamed budget"),
                        "Spend": round(amount, 2),
                        "Forecast": round(amount * 1.08, 2),
                    }
                )
        if not rows:
            return pd.DataFrame(columns=["Budget", "Spend", "Forecast"]), 0.0
        df = pd.DataFrame(rows)
        return df, float(df["Spend"].sum())
    except Exception:
        return _gcp_demo_data()


def render_sidebar():
    st.sidebar.title("Controls")
    st.sidebar.caption("Synthetic demo mode — no real cloud invoices")
    selected = st.sidebar.multiselect(
        "Providers",
        ["AWS", "GCP"],
        default=["AWS", "GCP"],
    )
    period = st.sidebar.radio("Period", ["30 days", "90 days", "6 months"], index=2)
    st.sidebar.markdown("---")
    st.sidebar.caption("Add real credentials later")
    st.sidebar.code(
        "AWS_ACCESS_KEY_ID=...\nAWS_SECRET_ACCESS_KEY=...\nGOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json"
    )
    st.sidebar.caption("AI integration")
    st.sidebar.code(
        "GENAI_API_KEY=...\nOPENAI_API_KEY=...\nGENAI_BASE_URL=https://genailab.tcs.in\nGENAI_MODEL=azure/genailab-maas-gpt-4o-mini"
    )
    return selected, period


def _normalize_idle_resources(idle_resources):
    normalized = {"AWS": [], "GCP": []}
    if not idle_resources:
        return normalized

    for cloud, items in idle_resources.items():
        if cloud not in normalized:
            continue
        if isinstance(items, list):
            normalized[cloud] = items
        elif isinstance(items, dict):
            for metric_name, value in items.items():
                normalized[cloud].append({
                    "Resource": metric_name.replace("_", " ").title(),
                    "Region": "N/A",
                    "Count": value,
                })
    return normalized


def _build_demo_recommendations(aws_services, gcp_budgets, idle_resources=None, utilisation=None, instance_inventory=None):
    idle_resources = _normalize_idle_resources(idle_resources or {"AWS": {}, "GCP": {}})
    utilisation = utilisation or {"AWS": {}, "GCP": {}}
    instance_inventory = instance_inventory or []

    aws_cpu = utilisation.get("AWS", {}).get("EC2_cpu_percent", 28)
    gcp_cpu = utilisation.get("GCP", {}).get("Compute_cpu_percent", 31)
    aws_rows = idle_resources.get("AWS", [])
    gcp_rows = idle_resources.get("GCP", [])
    aws_stopped = next((row.get("Count", 0) for row in aws_rows if "stopped" in str(row.get("Resource", "")).lower()), 0)
    gcp_idle = next((row.get("Count", 0) for row in gcp_rows if "idle" in str(row.get("Resource", "")).lower() or "vm" in str(row.get("Resource", "")).lower()), 0)
    aws_ebs = next((row.get("Count", 0) for row in aws_rows if "ebs" in str(row.get("Resource", "")).lower()), 0)
    gcp_disks = next((row.get("Count", 0) for row in gcp_rows if "disk" in str(row.get("Resource", "")).lower()), 0)
    aws_stop_region = next((row.get("Region", "us-east-1") for row in aws_rows if "stopped" in str(row.get("Resource", "")).lower()), "us-east-1")
    gcp_idle_region = next((row.get("Region", "us-central1") for row in gcp_rows if "idle" in str(row.get("Resource", "")).lower() or "vm" in str(row.get("Resource", "")).lower()), "us-central1")
    stale_instances = [entry for entry in instance_inventory if entry.get("AvgCpuPercent", 100) < 25 or "idle" in str(entry.get("Status", "")).lower()]

    def rec(title, details, savings, confidence, risk, priority, calculation):
        return {
            "title": title,
            "details": details,
            "estimated_savings": savings,
            "calculation": calculation,
            "confidence": confidence,
            "risk": risk,
            "risk_reason": {
                "Low": "Low operational risk: the change is reversible and does not require a risky migration.",
                "Medium": "Medium operational risk: check workload timing and capacity before implementation.",
                "High": "High operational risk: requires controlled testing because it affects critical workloads."
            }[risk],
            "priority": priority,
            "priority_reason": {
                "Immediate": "Priority is immediate because savings are material and the fix is quick to apply.",
                "Next 30 days": "Priority is within 30 days because the change is moderate effort and likely to reduce cost soon.",
                "Next quarter": "Priority is next quarter because it is lower impact or more planning-intensive."
            }[priority],
        }

    recs = []

    if stale_instances:
        top_entry = max(stale_instances, key=lambda x: x.get("IdleHours", 0))
        recs.append(rec(
            "Downsize idle instances in active regions",
            f"{top_entry.get('Cloud')} has {sum(item.get('Count', 0) for item in stale_instances)} low-utilization instances in {top_entry.get('Region')} running {top_entry.get('InstanceType')} for {top_entry.get('IdleHours')} idle hours; change to {top_entry.get('SuggestedInstanceType')} to lower cost.",
            "$2,100/month",
            "High",
            "Low",
            "Immediate",
            "3 idle instances × $15/hour × 730 hours/month = $32,850/year ≈ $2,737/month, reduced to a conservative demo estimate of $2,100/month."
        ))

    if aws_cpu < 35 or aws_stopped > 0:
        recs.append(rec(
            "Right-size EC2 instances",
            f"AWS EC2 utilization is around {aws_cpu}% and {aws_stopped} stopped instances were observed in {aws_stop_region}, indicating oversized compute capacity.",
            "$1,800/month",
            "High",
            "Low",
            "Immediate",
            f"({100 - aws_cpu:.0f}% idle capacity × estimated AWS compute spend factor × 730 hours/month) ≈ $1,800/month savings."
        ))

    if gcp_cpu < 40 or gcp_idle > 0:
        recs.append(rec(
            "Reduce idle GCP compute",
            f"GCP compute is at about {gcp_cpu}% utilization and {gcp_idle} idle VMs are present in {gcp_idle_region}; reduce machine size or shut down non-production workloads.",
            "$1,400/month",
            "High",
            "Low",
            "Immediate",
            f"({100 - gcp_cpu:.0f}% idle capacity + {gcp_idle} idle VM count) × typical GCP compute cost factor × 730 hours/month ≈ $1,400/month."
        ))

    if aws_ebs > 0 or gcp_disks > 0:
        recs.append(rec(
            "Clean up orphaned storage",
            f"There are {aws_ebs} unattached AWS EBS volumes and {gcp_disks} unused GCP disks, which are common sources of recurring waste across the active regions.",
            "$900/month",
            "High",
            "Low",
            "Immediate",
            f"({aws_ebs + gcp_disks} orphaned volumes × average monthly storage cost) ≈ $900/month conservative savings."
        ))

    if utilisation.get("AWS", {}).get("Lambda_idle_hours", 0) > 10 or utilisation.get("GCP", {}).get("CloudRun_scale_to_zero", False):
        recs.append(rec(
            "Improve autoscaling and scale-to-zero",
            "Lambda and Cloud Run workloads show idle time; align instance count with traffic patterns and pause non-critical workloads during off-hours.",
            "$1,200/month",
            "Medium",
            "Low",
            "Next 30 days",
            "Idle execution hours × hourly runtime rate × off-hours reduction = ~$1,200/month savings estimate."
        ))

    recs.append(rec(
        "Move non-critical workloads to cheaper regions",
        "Regional cost analysis shows a large gap between the current primary region and lower-cost regions; shift batch and non-latency-sensitive workloads to reduce spend.",
        "$1,500/month",
        "Medium",
        "Medium",
        "Next 30 days",
        "Regional rate difference × workload-hours in non-critical services = $1,500/month estimated savings."
    ))

    recs.append(rec(
        "Review storage tiering and analytics cost",
        "The demo data shows a high share of storage and analytics spend; archive old objects and optimize query windows to reduce monthly cost.",
        "$750/month",
        "Medium",
        "Medium",
        "Next 30 days",
        "Storage tier downgrade + analytics query reduction = ~$750/month in demo-model savings."
    ))

    while len(recs) < 5:
        recs.append(rec(
            "General optimization review",
            "Continue reviewing service utilization and cost trends to remove waste in the next planning cycle.",
            "$500/month",
            "Medium",
            "Low",
            "Next quarter",
            "Conservative review-based estimate: incremental cleanup + rightsizing = ~$500/month."
        ))

    return recs[:5]


def _parse_ai_analysis_payload(text):
    cleaned = str(text).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|```\s*$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE).strip()

    try:
        payload = json.loads(cleaned)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("recommendations"), list):
            return payload["recommendations"]
    except Exception:
        pass

    lines = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^(?:[-*]|\d+[\.)])\s+", line):
            lines.append(re.sub(r"^(?:[-*]|\d+[\.)])\s+", "", line))
        elif re.match(r"^(?:title|details|estimated_savings|confidence|risk|priority|reasoning)\s*:", line, flags=re.IGNORECASE):
            lines.append(line)

    if lines:
        return [{"title": f"Recommendation {idx + 1}", "details": item, "estimated_savings": "Estimated", "confidence": "Medium", "risk": "Medium", "priority": "Next 30 days"} for idx, item in enumerate(lines)]

    return None


def get_shared_ai_config():
    """One environment-driven configuration for all AI actions."""
    return {
        "api_key": os.getenv("GENAI_API_KEY") or os.getenv("OPENAI_API_KEY"),
        "base_url": os.getenv("GENAI_BASE_URL") or None,
        "model": os.getenv("GENAI_MODEL", "azure/genailab-maas-gpt-4o-mini"),
    }


# AI operations share this local database. Costs use USER-CONFIGURED USD per 1M
# input/output tokens; do not mistake these for a provider's published prices.
AI_USAGE_DB = Path(__file__).resolve().with_name("ai_usage.sqlite3")


def _ai_db():
    conn = sqlite3.connect(str(AI_USAGE_DB), timeout=10)
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
        month TEXT NOT NULL, action TEXT NOT NULL, model TEXT NOT NULL,
        input_tokens INTEGER, output_tokens INTEGER,
        tokens_measured INTEGER NOT NULL, billed_estimate_usd REAL NOT NULL,
        status TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_cache (
        cache_key TEXT PRIMARY KEY, response_text TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    return conn


def _ai_month():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _pricing_settings():
    # Configure these for your SPECIFIC GenAI deployment's actual rate card.
    # Defaults are zero to avoid presenting invented charges as real prices.
    return {
        "input": float(os.getenv("AI_INPUT_USD_PER_1M", "0")),
        "output": float(os.getenv("AI_OUTPUT_USD_PER_1M", "0")),
        "limit": float(os.getenv("AI_MONTHLY_BUDGET_USD", "10")),
    }


def _cost_usd(inp, out, rates):
    return (inp * rates["input"] + out * rates["output"]) / 1_000_000


def _month_spend(conn):
    return float(conn.execute(
        "SELECT COALESCE(SUM(billed_estimate_usd),0) FROM ai_usage WHERE month=? AND status='success'",
        (_ai_month(),)
    ).fetchone()[0])



# AI budget alert settings and delivery state live in the existing AI usage DB.
def _init_ai_alert_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_email_alert_settings (
        id INTEGER PRIMARY KEY CHECK(id=1), recipient TEXT NOT NULL,
        enabled INTEGER NOT NULL, cost_threshold REAL NOT NULL,
        token_threshold INTEGER NOT NULL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_email_alert_sent (
        month TEXT NOT NULL, metric TEXT NOT NULL, recipient TEXT NOT NULL,
        threshold TEXT NOT NULL, sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(month, metric, recipient, threshold)
    )""")
    conn.commit()


def _get_ai_alert_settings(conn):
    _init_ai_alert_tables(conn)
    row = conn.execute("""SELECT recipient, enabled, cost_threshold, token_threshold
        FROM ai_email_alert_settings WHERE id=1""").fetchone()
    return dict(zip(("recipient", "enabled", "cost_threshold", "token_threshold"), row)) if row else None


def _ai_alert_snapshot(conn):
    month = _ai_month()
    cost = _month_spend(conn)
    count = conn.execute("""SELECT COALESCE(SUM(input_tokens+output_tokens),0)
        FROM ai_usage WHERE month=? AND status='success'""", (month,)).fetchone()[0]
    return {"month": month, "estimated_cost": cost, "tokens": int(count),
            "monthly_limit": _pricing_settings()["limit"]}


def _dispatch_ai_alerts():
    """Send at most one email per recipient/month/metric/threshold.

    SMTP is optional; failures do not cause an otherwise successful AI request to fail.
    This synchronous check runs after new usage is saved; it is not a background job.
    """
    with _ai_db() as conn:
        settings = _get_ai_alert_settings(conn)
        if not settings or not settings["enabled"] or not settings["recipient"]:
            return []
        snapshot = _ai_alert_snapshot(conn)
        rates = _pricing_settings()
        candidates = []
        if rates["input"] <= 0 or rates["output"] <= 0:
            # Do not advertise a zero-priced or partially configured estimate as a meaningful spend alert.
            pass
        elif snapshot["monthly_limit"] > 0 and snapshot["estimated_cost"] >= snapshot["monthly_limit"] * settings["cost_threshold"] / 100:
            candidates.append(("cost", str(settings["cost_threshold"])))
        if settings["token_threshold"] > 0 and snapshot["tokens"] >= settings["token_threshold"]:
            candidates.append(("tokens", str(settings["token_threshold"])))

        notified = []
        for metric, threshold in candidates:
            already = conn.execute("""SELECT 1 FROM ai_email_alert_sent
                WHERE month=? AND metric=? AND recipient=? AND threshold=?""",
                (snapshot["month"], metric, settings["recipient"], threshold)).fetchone()
            if already:
                continue
            if metric == "cost":
                subject = f"AI budget alert: {snapshot['estimated_cost'] / snapshot['monthly_limit'] * 100:.1f}% of monthly limit"
            else:
                subject = f"AI token volume alert: {snapshot['tokens']:,} tokens this month"
            message = (f"AI usage alert for {snapshot['month']} (UTC)\n\n"
                f"Monthly AI cost estimate: ${snapshot['estimated_cost']:.6f} USD\n"
                f"Monthly AI cost limit: ${snapshot['monthly_limit']:.2f} USD\n"
                f"Input + output tokens recorded: {snapshot['tokens']:,}\n"
                f"Triggered rule: {metric} threshold {threshold}\n\n"
                "Costs are estimated from configured token rates, not verified provider invoices. "
                "Token totals may include estimated counts if the endpoint does not report usage.\n")
            # Only mark as sent if SMTP accepts the message.
            _send_smtp_alert(settings["recipient"], subject, message)
            conn.execute("""INSERT OR IGNORE INTO ai_email_alert_sent
                (month, metric, recipient, threshold) VALUES (?,?,?,?)""",
                (snapshot["month"], metric, settings["recipient"], threshold))
            conn.commit()
            notified.append(metric)
    return notified


def render_ai_email_alerts():
    st.markdown("#### AI Token & Cost Email Alerts")
    st.caption("Optional monitoring. If SMTP is not configured in the environment, the UI stays visible but sends nothing; the dashboard still works normally.")
    with _ai_db() as conn:
        saved = _get_ai_alert_settings(conn)
        snapshot = _ai_alert_snapshot(conn)
    rates = _pricing_settings()
    default_recipient = saved["recipient"] if saved else ""
    recipient = st.text_input("AI alert recipient email", value=default_recipient, key="ai_alert_recipient")
    enabled = st.checkbox("Enable AI usage email alerts", value=bool(saved["enabled"]) if saved else False,
                          key="ai_alert_enabled")
    threshold = st.slider("Alert at monthly AI budget usage (%)", min_value=50, max_value=100,
                          step=5, value=int(saved["cost_threshold"]) if saved else 80,
                          key="ai_alert_threshold")
    token_limit = st.number_input("Optional monthly token alert threshold (0 disables)", min_value=0,
                         max_value=1_000_000_000, step=10000,
                         value=int(saved["token_threshold"]) if saved else 0,
                         key="ai_alert_token_limit")
    limit = snapshot["monthly_limit"]
    usage_percentage = snapshot["estimated_cost"] / limit * 100 if limit > 0 else 0
    st.caption(f"Current month (UTC): {snapshot['month']} | Tokens recorded: {snapshot['tokens']:,} | "
               f"Estimated AI spend: ${snapshot['estimated_cost']:.6f} | "
               f"Budget usage: {usage_percentage:.1f}%")
    if rates["input"] <= 0 or rates["output"] <= 0:
        st.warning("Configure positive AI_INPUT_USD_PER_1M and AI_OUTPUT_USD_PER_1M to enable meaningful dollar-cost alerts. Token-count alerts can still work.")
    smtp_ready = bool(os.getenv("SMTP_HOST", "").strip()) and bool(os.getenv("SMTP_FROM", "").strip())
    if not smtp_ready:
        st.info("SMTP is not configured for this environment, so AI alerts will remain saved in the UI but will not actually be sent until SMTP_HOST and SMTP_FROM are set.")
    if st.button("Save AI alert settings", key="save_ai_alert_settings"):
        from email.utils import parseaddr
        valid = parseaddr(recipient.strip())[1] == recipient.strip() and "@" in recipient and "." in recipient.split("@")[-1]
        if enabled and not valid:
            st.error("Enter a valid recipient email address before enabling alerts.")
        else:
            with _ai_db() as conn:
                _init_ai_alert_tables(conn)
                conn.execute("""INSERT INTO ai_email_alert_settings
                    (id,recipient,enabled,cost_threshold,token_threshold) VALUES (1,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET recipient=excluded.recipient,
                      enabled=excluded.enabled,cost_threshold=excluded.cost_threshold,
                      token_threshold=excluded.token_threshold""",
                    (recipient.strip(), int(enabled), float(threshold), int(token_limit)))
            st.success("AI alert settings saved.")
    if st.button("Check AI alert thresholds and send if reached", key="check_ai_email_alerts"):
        try:
            delivered = _dispatch_ai_alerts()
            if delivered:
                st.success("AI email alert sent for: " + ", ".join(delivered))
            elif not smtp_ready:
                st.info("SMTP is not configured, so no live email can be sent from this environment.")
            else:
                st.info("No new AI alert is due (or alerts are disabled/already sent).")
        except Exception as exc:
            st.error(f"AI alert email not sent: {type(exc).__name__}: {exc}")

def _ai_http_client():
    """Temporary local workaround for internal GenAI endpoints using self-signed or untrusted certs."""
    if httpx is None:
        return None
    disable_ssl = str(os.getenv("GENAI_DISABLE_SSL_VERIFY", "true")).lower() in {"1", "true", "yes", "y", "on"}
    if not disable_ssl:
        return None
    return httpx.Client(verify=False)


def invoke_shared_ai(prompt, max_tokens=900, action="AI analysis"):
    """Shared model, cached successful results, per-request usage ledger and budget gate.

    Missing model-reported token counts are recorded as estimates, NOT measured.
    Cost rates are account-specific settings. This gate is best-effort for a single
    process, not an enterprise-grade multi-worker atomic quota system.
    """
    config = get_shared_ai_config()
    if not config["api_key"]:
        raise RuntimeError("Set GENAI_API_KEY (or OPENAI_API_KEY) before using AI analysis")
    settings = _pricing_settings()
    if min(settings["input"], settings["output"], settings["limit"]) < 0:
        raise ValueError("AI prices and budget cannot be negative")
    # Hash does not contain the actual key; changing key/endpoint invalidates cache.
    fingerprint = hashlib.sha256(str(config["api_key"]).encode()).hexdigest()[:12]
    cache_key = hashlib.sha256(json.dumps([
        config["model"], config["base_url"], fingerprint,
        max_tokens, prompt], ensure_ascii=False).encode()).hexdigest()
    with _ai_db() as conn:
        row = conn.execute("SELECT response_text FROM ai_cache WHERE cache_key=?", (cache_key,)).fetchone()
        if row:
            st.caption("AI response reused from local cache; no new model request or tokens.")
            return row[0]
        # Rough preflight upper-bound for ordinary English prompts; not tokenizer-accurate.
        # Unknown tokenization/overhead means this is not a hard billing guarantee.
        estimated_input = max(1, (len(prompt) + 2) // 3) + 150
        estimated_upper_cost = _cost_usd(estimated_input, max_tokens, settings)
        spent = _month_spend(conn)
        if spent + estimated_upper_cost > settings["limit"]:
            raise RuntimeError(
                "Local AI monthly cost limit would be exceeded by this request. "
                "Increase AI_MONTHLY_BUDGET_USD only after reviewing token prices and usage."
            )

    content, usage = None, None
    http_client = _ai_http_client()
    try:
        if ChatOpenAI is not None:
            kwargs = {"api_key": config["api_key"], "model": config["model"],
                      "temperature": 0.2, "max_tokens": max_tokens}
            if config["base_url"]:
                kwargs["base_url"] = config["base_url"]
            if http_client is not None:
                kwargs["http_client"] = http_client
            llm = ChatOpenAI(**kwargs)
            response = llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            usage = getattr(response, "usage_metadata", None)
            if not usage:
                metadata = getattr(response, "response_metadata", {}) or {}
                usage = metadata.get("token_usage", {})
        elif OpenAI is not None:
            kwargs = {"api_key": config["api_key"]}
            if config["base_url"]:
                kwargs["base_url"] = config["base_url"]
            if http_client is not None:
                kwargs["http_client"] = http_client
            client = OpenAI(**kwargs)
            response = client.chat.completions.create(
                model=config["model"], messages=[{"role": "user", "content": prompt}],
                temperature=0.2, max_tokens=max_tokens)
            content = response.choices[0].message.content or ""
            if response.usage:
                usage = {"input_tokens": response.usage.prompt_tokens,
                         "output_tokens": response.usage.completion_tokens}
        else:
            raise RuntimeError("Install langchain-openai or openai to enable AI analysis")
    finally:
        if http_client is not None:
            http_client.close()

    content = content if isinstance(content, str) else str(content)
    if not content.strip():
        raise RuntimeError("AI returned an empty response; nothing was cached")
    usage = usage or {}
    inp = usage.get("input_tokens", usage.get("prompt_tokens")) if isinstance(usage, dict) else None
    out = usage.get("output_tokens", usage.get("completion_tokens")) if isinstance(usage, dict) else None
    measured = inp is not None and out is not None
    inp = int(inp) if inp is not None else estimated_input
    out = int(out) if out is not None else max_tokens  # Conservative output reservation
    price = _cost_usd(inp, out, settings)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _ai_db() as conn:
        conn.execute("""INSERT INTO ai_usage
            (timestamp,month,action,model,input_tokens,output_tokens,
             tokens_measured,billed_estimate_usd,status)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (now, _ai_month(), action, config["model"], inp, out, int(measured), price, "success"))
        conn.execute("INSERT OR REPLACE INTO ai_cache(cache_key,response_text,created_at) VALUES(?,?,?)",
                     (cache_key, content, now))
    # AI alert delivery is intentionally disabled in this environment.
    return content


def render_ai_usage_monitor():
    st.markdown("---")
    st.subheader("AI Usage & Cost Monitor")
    st.caption("Local request log. Charges are ESTIMATES using rates you configure for your provider, "
               "not verified invoices. Budget gate works when AI requests pass through this app.")
    cfg = get_shared_ai_config()
    rates = _pricing_settings()
    st.write(f"**AI model:** `{cfg['model']}`")
    if rates["input"] == 0 and rates["output"] == 0:
        st.warning("AI token prices are not configured, so reported estimated costs are $0. "
                   "Set AI_INPUT_USD_PER_1M and AI_OUTPUT_USD_PER_1M using YOUR provider's rate card "
                   "before interpreting cost totals or expecting the USD limit to restrict usage.")
    a,b,c = st.columns(3)
    a.metric("Configured input / 1M tokens", f"${rates['input']:.4f}")
    b.metric("Configured output / 1M tokens", f"${rates['output']:.4f}")
    c.metric("Monthly AI limit", f"${rates['limit']:.2f}")
    with _ai_db() as conn:
        rows = conn.execute("""SELECT timestamp,action,model,input_tokens,output_tokens,
            tokens_measured,billed_estimate_usd FROM ai_usage WHERE month=?
            ORDER BY id DESC LIMIT 200""", (_ai_month(),)).fetchall()
        total = _month_spend(conn)
        cached = conn.execute("SELECT COUNT(*) FROM ai_cache").fetchone()[0]
    x,y,z = st.columns(3)
    x.metric("Monthly estimated AI spend", f"${total:.6f}")
    y.metric("Recorded model requests (up to 200 shown)", len(rows))
    z.metric("Cached analyses", cached)
    if rows:
        df = pd.DataFrame(rows, columns=["Time (UTC)", "Action", "Model", "Input tokens",
                                         "Output tokens", "Measured tokens", "Estimated cost (USD)"])
        df["Measured tokens"] = df["Measured tokens"].map({1: "Yes", 0: "No — estimate"})
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download AI usage (CSV)", df.to_csv(index=False),
                           file_name="ai_usage_log.csv", mime="text/csv")
    st.caption("Repeated identical prompts are cached locally. A different scenario, account, "
               "model, or dataset may create a new request. An in-memory cache alone is not used. "
               "Neither this estimate nor the local budget gate replaces your provider's usage billing/quotas.")


def get_ai_recommendations(aws_services, gcp_budgets, aws_total, gcp_total,
                           idle_resources=None, utilisation=None, instance_inventory=None):
    """AI recommendations using the shared model; demo fallback on failure."""
    default_recommendations = _build_demo_recommendations(
        aws_services, gcp_budgets, idle_resources, utilisation, instance_inventory
    )
    prompt = f"""
    Analyze this synthetic cloud spend summary and return exactly five cost-saving
    recommendations as a JSON array. Each recommendation must have keys:
    title, details, estimated_savings, calculation, confidence, risk, risk_reason, priority, priority_reason.
    estimated_savings must be an exact dollar value and time window like '$2,100/month' or '$14,400/year'.
    calculation must clearly show the formula used for the estimate in plain English.
    risk must be one of Low, Medium, High and risk_reason must explain why.
    priority must be one of Immediate, Next 30 days, Next quarter and priority_reason must explain why.
    Use the synthetic data provided; do not invent fabricated invoices or provider pricing. Keep the numbers realistic and conservative.

    AWS spending: {json.dumps(aws_services.sort_values('Spend', ascending=False).to_dict('records'), default=str)}
    GCP spending: {json.dumps(gcp_budgets.sort_values('Spend', ascending=False).to_dict('records'), default=str)}
    AWS total (USD): {aws_total:.2f}
    GCP total (USD): {gcp_total:.2f}
    Idle resources: {json.dumps(idle_resources or {}, default=str)}
    Inventory: {json.dumps(instance_inventory or [], default=str)}
    Utilization: {json.dumps(utilisation or {}, default=str)}
    """
    try:
        parsed = _parse_ai_analysis_payload(invoke_shared_ai(prompt, action="Dashboard recommendations"))
        if parsed:
            return parsed
        st.warning("AI response could not be parsed; showing synthetic fallback recommendations.")
    except Exception as exc:
        st.warning(f"Dashboard AI unavailable ({type(exc).__name__}); showing synthetic fallback recommendations.")
    return default_recommendations

# These profiles are fictional customer/accounts for interactive demonstrations.
DEMO_ACCOUNTS = {
    "Engineering": {"factor": 1.0, "seed": 11},
    "Marketing": {"factor": 0.57, "seed": 29},
    "Finance": {"factor": 1.42, "seed": 47},
}
PERIOD_DAYS = {"30 days": 30, "90 days": 90, "6 months": 180}


@st.cache_data
def generate_period_demo(account, seed=0):
    """Create a deterministic 365-day synthetic *daily* billing ledger per account.

    All selectable periods are subsets of this same ledger, not fresh random
    generations for each selection. Daily services aggregate to dashboard totals.
    """
    profile = DEMO_ACCOUNTS[account]
    rng = random.Random(profile["seed"] + seed * 1009)
    days = pd.date_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=365)
    services = {
        "AWS": {"Amazon EC2": 81, "Amazon S3": 31, "Amazon RDS": 41,
                "AWS Lambda": 14, "Amazon CloudFront": 12},
        "GCP": {"Compute Engine": 60, "Cloud Storage": 23,
                "BigQuery": 35, "Cloud Run": 13, "Networking": 17},
    }
    rows = []
    for day_index, day in enumerate(days):
        trend = 0.82 + 0.25 * day_index / (len(days) - 1)
        weekday_factor = 0.78 if day.weekday() >= 5 else 1.0
        for cloud, items in services.items():
            for service, daily_base in items.items():
                volatility = rng.uniform(0.83, 1.18)
                cost = round(daily_base * profile["factor"] * trend * weekday_factor * volatility, 2)
                rows.append({"Date": day, "Cloud": cloud, "Service": service, "Cost": cost})
    return pd.DataFrame(rows)



@st.cache_data
def synthetic_traffic_history(account, seed=0):
    """Fictional demand signal; deterministic across filter selections."""
    rng = random.Random(DEMO_ACCOUNTS[account]["seed"] * 23 + seed * 1009)
    dates = pd.date_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=365)
    base = 8800 * DEMO_ACCOUNTS[account]["factor"]
    rows = []
    for i, day in enumerate(dates):
        weekly = 0.75 if day.weekday() >= 5 else 1.08
        growth = 0.83 + 0.30 * i / 364
        seasonal = 1 + 0.10 * __import__('math').sin(i * 2 * __import__('math').pi / 28)
        requests = max(1, round(base * weekly * growth * seasonal * rng.uniform(0.88, 1.12)))
        rows.append({"Date": day, "Requests": requests})
    return pd.DataFrame(rows)


def forecast_traffic_from_history(history, forecast_days=30):
    """Deterministic weekday-aware synthetic-demand forecast, not an LLM guess.

    Estimate a bounded daily trend from the prior 84 days, then combine it with
    the recent 28-day weekday pattern. This requires historical request counts.
    """
    daily = history.copy().sort_values("Date")
    if len(daily) < 28:
        raise ValueError("At least 28 daily traffic observations are required")
    recent = daily.tail(28)
    weekday_mean = recent.groupby(recent["Date"].dt.weekday)["Requests"].mean().to_dict()
    recent_average = float(recent["Requests"].mean())
    lookback = daily.tail(84)
    # Smoothed trend from the first 28 to last 28 days of an 84-day window.
    early_avg = float(lookback.head(28)["Requests"].mean())
    late_avg = float(lookback.tail(28)["Requests"].mean())
    elapsed = max(1, len(lookback) - 28)
    daily_trend = (late_avg / early_avg - 1) / elapsed if early_avg > 0 else 0.0
    daily_trend = max(-0.005, min(0.005, daily_trend))  # prevent extreme extrapolation
    last_day = daily["Date"].max()
    rows = []
    for step, d in enumerate(pd.date_range(last_day + pd.Timedelta(days=1), periods=forecast_days), 1):
        weekday_baseline = weekday_mean.get(d.weekday(), recent_average)
        predicted = max(0, weekday_baseline * (1 + daily_trend * step))
        rows.append({"Date": d, "Historical forecast requests": round(predicted)})
    return pd.DataFrame(rows), {"recent_28_day_average": recent_average,
                                "daily_trend_percent": daily_trend * 100,
                                "history_days_used_for_trend": len(lookback)}


def simulate_future_impact(history, current_count, proposed_count, current_rate,
                           proposed_rate, hours_per_day, capacity_per_instance,
                           forecast_mode="Historical forecast", traffic_growth=0):
    """Price and capacity calculations from an explicit, reproducible forecast.

    A manual adjustment is applied *on top of* the historical demand forecast.
    Forecast demand doesn't automatically trigger autoscaling or extra spend.
    """
    projected, evidence = forecast_traffic_from_history(history)
    multiplier = 1 + (traffic_growth / 100 if forecast_mode == "Customer scenario" else 0)
    projected["Forecast requests"] = (projected["Historical forecast requests"] * multiplier).round().astype(int)
    available_capacity = proposed_count * capacity_per_instance * hours_per_day / 24
    projected["Illustrative daily capacity"] = round(available_capacity)
    monthly_hours = 730.0
    baseline_cost = current_count * current_rate * monthly_hours
    proposed_cost = proposed_count * proposed_rate * monthly_hours * hours_per_day / 24
    shortfall = (projected["Forecast requests"] > projected["Illustrative daily capacity"]).sum()
    return {"forecast": projected, "baseline_cost": baseline_cost,
            "proposed_cost": proposed_cost, "delta": proposed_cost - baseline_cost,
            "over_capacity_days": int(shortfall), "last_28_avg": evidence["recent_28_day_average"],
            "trend_percent_per_day": evidence["daily_trend_percent"],
            "trend_history_days": evidence["history_days_used_for_trend"],
            "forecast_mode": forecast_mode,
            "manual_adjustment_percent": traffic_growth if forecast_mode == "Customer scenario" else 0,
            "peak_forecast": int(projected["Forecast requests"].max()),
            "capacity": available_capacity}


def ai_simulation_explanation(payload):
    """Explain Python-calculated scenario with the same AI model/configuration."""
    prompt = (
        "Explain this illustrative cloud what-if scenario in 3 concise paragraphs: "
        "cost impact, traffic/capacity risk, and what must be checked before a real change. "
        "Use only the supplied Python-calculated cost figures and projected traffic. "
        "Explain how proposed values relate to the original AI recommendation, "
        "including when the change does not address the recommendation. "
        "Report calculated monthly and annualized savings exactly as supplied, "
        "and separate them from unverified savings estimates in original recommendations. "
        "Distinguish historical forecasts from manually adjusted customer scenarios. "
        "All values are synthetic. Never claim performance is validated, invent prices "
        "or recommend immediate production changes. Data: " + json.dumps(payload, default=str)
    )
    try:
        return invoke_shared_ai(prompt, max_tokens=700, action="What-if future impact")
    except Exception as exc:
        st.warning(f"AI simulation explanation unavailable ({type(exc).__name__}). Showing calculated results only.")
        return None


# FICTIONAL on-demand compute rates (USD per instance-hour) for the demo only.
# These are not AWS/GCP list prices and are not derived from customer invoices.
DEMO_COMPUTE_PRICES = {
    "AWS": {
        "m5.large": 0.10, "m5.xlarge": 0.20,
        "c5.large": 0.085, "c5.xlarge": 0.17,
        "r5.large": 0.13, "r5.xlarge": 0.26,
    },
    "GCP": {
        "n2-standard-4": 0.19, "n2-standard-8": 0.38,
        "e2-standard-2": 0.075, "e2-standard-4": 0.15,
    },
}
# All factors are fictional and intended to demonstrate region-aware lookups.
DEMO_REGION_FACTORS = {
    "AWS": {"us-east-1": 1.00, "us-west-2": 1.07, "eu-central-1": 1.12},
    "GCP": {"us-central1": 1.00, "europe-west1": 1.11, "asia-southeast1": 1.09},
}


def get_demo_hourly_price(provider, region, instance_type):
    """Return a fictional demo hourly rate; fail on missing combinations."""
    try:
        return round(DEMO_COMPUTE_PRICES[provider][instance_type] *
                     DEMO_REGION_FACTORS[provider][region], 5)
    except KeyError as exc:
        raise ValueError(f"No synthetic pricing for {provider}/{region}/{instance_type}") from exc


def render_what_if_simulator(account, selected, ledger, inventory, seed, recommendations):
    st.markdown("---")
    st.subheader("What-If Simulator — future cost and traffic impact")
    st.caption("Experimental synthetic scenario. Traffic is separately simulated: billing records "
               "do not contain measured request volume, CPU peaks or RAM. The model below is "
               "a demonstration, not production capacity planning.")
    if not recommendations:
        st.info("Generate AI analysis above, then select a recommendation to test its impact.")
        return
    choices = [r for r in recommendations if isinstance(r, dict)]
    selected_rec = st.selectbox(
        "AI recommendation to investigate",
        range(len(choices)),
        format_func=lambda i: choices[i].get("title", f"Recommendation {i+1}"),
        key="sim_recommendation",
    ) if choices else None
    recommendation = choices[selected_rec] if selected_rec is not None else {}
    st.caption("The selected recommendation is context for AI, not an automatic instruction to change resources. "
               "Set a proposed configuration below to calculate its impact.")
    eligible = [i for i in inventory if i["Cloud"] in selected]
    if not eligible:
        return
    labels = [f'{item["Cloud"]} • {item["Region"]} • {item["InstanceType"]}' for item in eligible]
    pick = st.selectbox("Choose an existing fleet to simulate", range(len(labels)),
                        format_func=lambda i: labels[i], key="sim_fleet")
    resource = eligible[pick]
    current_count = int(resource["Count"])
    st.write(f'Current synthetic fleet: **{current_count} × {resource["InstanceType"]}** '
             f'in **{resource["Region"]}**. Its {resource["AvgCpuPercent"]}% average CPU '
             'is illustrative, not measured from the traffic history.')
    # The user chooses the infrastructure; Python derives both hourly rates.
    provider, region, current_type = resource["Cloud"], resource["Region"], resource["InstanceType"]
    available_types = sorted(DEMO_COMPUTE_PRICES[provider])
    recommendation_type = resource.get("SuggestedInstanceType")
    default_type = recommendation_type if recommendation_type in available_types else current_type
    a, b = st.columns(2)
    with a:
        proposed_type = st.selectbox(
            "Proposed instance type", available_types,
            index=available_types.index(default_type),
            key=f"sim_type_{account}_{provider}_{region}_{pick}",
        )
        proposed_count = st.number_input(
            "Proposed instance count", min_value=1, max_value=500,
            value=current_count, step=1, key=f"sim_count_{account}_{pick}",
        )
        hours = st.slider("Proposed running hours/day", 1, 24, 24)
    with b:
        current_rate = get_demo_hourly_price(provider, region, current_type)
        proposed_rate = get_demo_hourly_price(provider, region, proposed_type)
        st.metric("Current price per instance (USD/hour)", f"${current_rate:.3f}")
        st.metric("Proposed price per instance (USD/hour)", f"${proposed_rate:.3f}")
        capacity = st.number_input(
            "Assumed requests / instance / 24-hour day",
            min_value=1, max_value=10000000, value=2500,
            step=250, help="Synthetic capacity assumption; not validated by monitoring or load testing.",
        )
    st.caption("Automatic pricing: fictional Python demo catalog for the selected provider, "
               "region, and instance type. Instance count changes total cost, not unit price. "
               "These are NOT published cloud rates or actual billed charges.")
    st.markdown("#### Future demand prediction")
    forecast_mode = st.radio(
        "Forecast mode", ["Historical forecast", "Customer scenario"],
        horizontal=True, key=f"forecast_mode_{account}",
        help="Automatic uses historical synthetic request patterns. Customer scenario applies a manual adjustment to that forecast."
    )
    growth = 0
    if forecast_mode == "Customer scenario":
        growth = st.slider("Expected traffic change relative to historical forecast (%)",
                           -50, 200, 0, 5, key=f"growth_{account}")
    else:
        st.caption("No future traffic input needed. The next 30 days are estimated using "
                   "weekday patterns from the last 28 days and a bounded trend from up to 84 days.")
    traffic = synthetic_traffic_history(account, seed)
    result = simulate_future_impact(traffic, current_count, int(proposed_count),
                                    float(current_rate), float(proposed_rate),
                                    hours, int(capacity), forecast_mode, growth)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Baseline compute/month", f'${result["baseline_cost"]:,.2f}')
    c2.metric("Proposed compute/month", f'${result["proposed_cost"]:,.2f}')
    c3.metric("Monthly cost change", f'${result["delta"]:+,.2f}')
    c4.metric("Days over assumed capacity", f'{result["over_capacity_days"]}/30')
    st.caption("Both baseline and proposed costs use 730 hours/month (proposed scaled by running hours/day). "
               "Compute only, fictional automatically looked-up rates; no storage, networking, commitments or migration costs.")
    st.caption(f"Forecast: {result['forecast_mode']} | recent 28-day average: "
               f"{result['last_28_avg']:,.0f} requests/day | bounded historical trend: "
               f"{result['trend_percent_per_day']:+.3f}%/day. Historical request data is synthetic.")
    st.write("Historical simulated demand (last 90 days)")
    st.line_chart(traffic.tail(90).set_index("Date")["Requests"])
    st.write("Projected next 30 days: historical forecast, scenario forecast, and assumed capacity")
    st.line_chart(result["forecast"].set_index("Date"))
    if result["over_capacity_days"]:
        st.warning("Some forecast days exceed the capacity you assumed. This is a model warning, "
                   "not evidence that actual cloud resources will fail.")
    else:
        st.info("No projected day exceeds the assumed capacity. This does NOT establish "
                "real-world performance or availability.")
    savings = max(0.0, -result["delta"])
    scenario_risk = ("Capacity warning: projected demand exceeds assumed capacity on "
                     f'{result["over_capacity_days"]} of 30 days.' if result["over_capacity_days"]
                     else "No modeled over-capacity days; real-world performance is unverified.")
    st.markdown("#### Deterministic simulation summary")
    st.write(f'**Calculated potential compute savings:** ${savings:,.2f}/month '
             f'(${savings*12:,.2f}/year annualized), excluding other costs.')
    st.write(f'**Risk indicator:** {scenario_risk}')
    explanation_payload = {
        "selected_original_ai_recommendation": {
            "title": recommendation.get("title", ""),
            "details": recommendation.get("details", ""),
            "original_estimated_savings_unverified": recommendation.get("estimated_savings", "N/A"),
            "original_risk_unverified": recommendation.get("risk", "N/A"),
        },
        "calculated_monthly_potential_savings_usd": round(savings, 2),
        "calculated_annualized_potential_savings_usd": round(savings * 12, 2),
        "simulated_capacity_risk_indicator": scenario_risk,
        "account": account, "cloud": resource["Cloud"], "region": resource["Region"],
        "instance_type": resource["InstanceType"], "proposed_instance_type": proposed_type,
        "current_instances": current_count,
        "proposed_instances": int(proposed_count), "hours_per_day": hours,
        "current_demo_catalog_hourly_rate_usd": float(current_rate),
        "proposed_demo_catalog_hourly_rate_usd": float(proposed_rate),
        "pricing_source": "fictional_region_aware_python_demo_catalog",
        "assumed_requests_per_instance_per_day": int(capacity),
        "traffic_forecast_mode": forecast_mode,
        "manual_traffic_adjustment_percent": result["manual_adjustment_percent"],
        "historical_trend_percent_per_day": round(result["trend_percent_per_day"], 4),
        "traffic_history_days_for_trend": result["trend_history_days"],
        "traffic_growth_percent": growth,
        "recent_28d_avg_requests_per_day": round(result["last_28_avg"]),
        "forecast_peak_daily_requests": result["peak_forecast"],
        "days_over_assumed_capacity": result["over_capacity_days"],
        "baseline_compute_monthly_usd": round(result["baseline_cost"],2),
        "proposed_compute_monthly_usd": round(result["proposed_cost"],2),
        "monthly_cost_delta_usd": round(result["delta"],2),
        "data_is_synthetic": True,
    }
    if st.button("Analyze future impact with AI", key="simulate_ai"):
        st.session_state["sim_ai_result"] = None
        st.session_state["sim_ai_input"] = None
        with st.spinner("Explaining the calculated scenario..."):
            explanation = ai_simulation_explanation(explanation_payload)
        if explanation:
            st.session_state["sim_ai_result"] = explanation
            st.session_state["sim_ai_input"] = explanation_payload
        else:
            st.session_state["sim_ai_result"] = None
            st.info("No configured AI response. Python simulation results above remain available.")
    if st.session_state.get("sim_ai_result") and st.session_state.get("sim_ai_input") == explanation_payload:
        st.markdown("**AI interpretation (synthetic scenario)**")
        st.write(st.session_state["sim_ai_result"])
    st.download_button("Download scenario assumptions/results (JSON)",
                       json.dumps(explanation_payload, indent=2),
                       file_name="what_if_scenario.json", mime="application/json")

def forecast_costs_from_history(ledger, selected_clouds, horizon_days, group_by_service=True):
    """Forecast next N days from exactly the previous N calendar days (N=30/90/180).

    The selected historical window determines weekday seasonality and trend.
    Uses a weekday-adjusted linear trend estimated from that entire window;
    trend is bounded to avoid runaway long-horizon extrapolation. Returns
    daily per-service projections and aggregated service predictions.
    """
    source = ledger.loc[ledger["Cloud"].isin(selected_clouds)].copy()
    if source.empty:
        return (pd.DataFrame(columns=["Date", "Cloud", "Service", "ForecastCost"]),
                pd.DataFrame(columns=["Cloud", "Service", "Forecast"]))
    last_date = source["Date"].max()
    start_date = last_date - pd.Timedelta(days=horizon_days - 1)
    source = source.loc[source["Date"] >= start_date]
    rows = []
    for (cloud, service), grp in source.groupby(["Cloud", "Service"]):
        history = grp.sort_values("Date")
        if len(history) != horizon_days:
            raise ValueError(f"Expected {horizon_days} historic observations for {cloud}/{service}; got {len(history)}")
        baseline = float(history["Cost"].mean())
        weekday_mean = history.groupby(history["Date"].dt.weekday)["Cost"].mean().to_dict()
        # Use all selected historical days to estimate trend after removing
        # weekday/weekend effects (the model is deterministic and auditable).
        seasonally_adjusted = [float(row.Cost) - weekday_mean[row.Date.weekday()] + baseline
                               for row in history.itertuples(index=False)]
        n = len(seasonally_adjusted)
        mean_x = (n - 1) / 2
        slope = (sum((i - mean_x) * value for i, value in enumerate(seasonally_adjusted)) /
                 sum((i - mean_x) ** 2 for i in range(n)))
        # Bound projected change to +/- 25% of baseline over the next N days.
        max_slope = baseline * 0.25 / horizon_days
        slope = max(-max_slope, min(max_slope, slope))
        for step in range(1, horizon_days + 1):
            future_date = last_date + pd.Timedelta(days=step)
            # Weekday baseline comes from the entire N-day history; trend
            # anchors that baseline at the center of the observed window.
            predicted = weekday_mean.get(future_date.weekday(), baseline) + slope * (n - 1 - mean_x + step)
            rows.append({"Date": future_date, "Cloud": cloud, "Service": service,
                         "ForecastCost": round(max(0.0, predicted), 2)})
    forecast_daily = pd.DataFrame(rows)
    summary = (forecast_daily.groupby(["Cloud", "Service"], as_index=False)["ForecastCost"]
               .sum().rename(columns={"ForecastCost": "Forecast"}))
    return forecast_daily, summary


# Persistent configuration and notification deduplication for the demo.
# The SQLite database is created locally beside this Python script.
ALERT_DB = Path(__file__).resolve().with_name("cloud_budget_alerts.sqlite3")


def _alert_db():
    conn = sqlite3.connect(str(ALERT_DB), timeout=10)
    conn.execute("""CREATE TABLE IF NOT EXISTS alert_settings (
        scope TEXT PRIMARY KEY, recipient TEXT NOT NULL,
        threshold REAL NOT NULL, enabled INTEGER NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS sent_alerts (
        scope TEXT NOT NULL, period_key TEXT NOT NULL,
        recipient TEXT NOT NULL, threshold REAL NOT NULL,
        sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (scope, period_key, recipient, threshold)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS configured_budgets (
        scope TEXT PRIMARY KEY, monthly_budget REAL NOT NULL
        CHECK(monthly_budget > 0)
    )""")
    conn.commit()
    return conn


def _budget_scope(account, providers):
    """A monthly budget belongs to an account/provider selection, not the viewing period."""
    return json.dumps([account, sorted(providers)])


def _get_monthly_budget(scope):
    with _alert_db() as conn:
        row = conn.execute("SELECT monthly_budget FROM configured_budgets WHERE scope=?", (scope,)).fetchone()
    return float(row[0]) if row else None


def _save_monthly_budget(scope, value):
    with _alert_db() as conn:
        conn.execute("""INSERT INTO configured_budgets(scope, monthly_budget) VALUES (?, ?)
            ON CONFLICT(scope) DO UPDATE SET monthly_budget=excluded.monthly_budget""",
            (scope, float(value)))


def _alert_scope(account, providers, days):
    return json.dumps([account, sorted(providers), int(days)])


def _get_alert_settings(scope):
    with _alert_db() as conn:
        row = conn.execute(
            "SELECT recipient, threshold, enabled FROM alert_settings WHERE scope=?", (scope,)
        ).fetchone()
    return {"recipient": row[0], "threshold": row[1], "enabled": bool(row[2])} if row else None


def _save_alert_settings(scope, recipient, threshold, enabled):
    with _alert_db() as conn:
        conn.execute("""INSERT INTO alert_settings (scope, recipient, threshold, enabled)
            VALUES (?, ?, ?, ?) ON CONFLICT(scope) DO UPDATE SET
            recipient=excluded.recipient, threshold=excluded.threshold,
            enabled=excluded.enabled""", (scope, recipient, threshold, int(enabled)))


def _send_smtp_alert(recipient, subject, body):
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender:
        raise RuntimeError("SMTP_HOST and SMTP_FROM must be configured before sending emails")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    security_mode = os.getenv("SMTP_SECURITY", "starttls").strip().lower()
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    if security_mode == "ssl":
        with smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context()) as server:
            if username:
                server.login(username, password)
            server.send_message(message)
    elif security_mode == "starttls":
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            if username:
                server.login(username, password)
            server.send_message(message)
    else:
        raise RuntimeError("SMTP_SECURITY must be starttls or ssl")


def _smtp_configured():
    return bool(os.getenv("SMTP_HOST", "").strip()) and bool(os.getenv("SMTP_FROM", "").strip())


def _send_threshold_test_email(recipient_email: str, threshold_pct: float = 80.0, spent_pct: float = 86.0):
    if not recipient_email:
        raise ValueError("A recipient email is required.")
    subject = f"[TEST] Budget threshold crossed: {spent_pct:.1f}% of budget"
    body = (
        "This is a test email sent from the dashboard to simulate a threshold-crossed alert.\n\n"
        f"Budget threshold reached: {threshold_pct:.0f}%\n"
        f"Current usage: {spent_pct:.1f}%\n"
        "Status: threshold crossed / exceeded\n\n"
        "This message is only for SMTP testing and demo validation."
    )
    _send_smtp_alert(recipient_email, subject, body)


def render_budget_email_alerts(account, selected, days, period_start, period_end,
                               total_spend, total_budget):
    st.markdown("---")
    st.subheader("Budget email alerts")
    st.caption("Optional monitoring. If SMTP is not configured, the dashboard keeps the alert settings UI and local state but does not attempt a live email send.")
    if total_budget <= 0:
        st.warning("No budget is configured for the selected providers.")
        return
    usage_pct = total_spend / total_budget * 100
    scope = _alert_scope(account, selected, days)
    saved = _get_alert_settings(scope)
    previous_scope = st.session_state.get("budget_alert_loaded_scope")
    if previous_scope != scope:
        st.session_state.budget_alert_loaded_scope = scope
        st.session_state.budget_alert_recipient = saved["recipient"] if saved else ""
        st.session_state.budget_alert_threshold = int(saved["threshold"]) if saved else 80
        st.session_state.budget_alert_enabled = saved["enabled"] if saved else False

    st.text_input("Notification recipient email", key="budget_alert_recipient",
                  placeholder="recipient@company.com")
    st.slider("Budget threshold (%)", min_value=50, max_value=100, step=5,
              key="budget_alert_threshold")
    st.checkbox("Enable budget email alerts for this selection", key="budget_alert_enabled")
    recipient = st.session_state.budget_alert_recipient.strip()
    threshold = int(st.session_state.budget_alert_threshold)
    enabled = bool(st.session_state.budget_alert_enabled)
    valid_email = bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", recipient))
    exceeded = usage_pct >= threshold
    remaining = max(0.0, total_budget - total_spend)
    subject = f"[SYNTHETIC DEMO] Cloud budget alert: {account} at {usage_pct:.1f}%"
    message = (f"Synthetic multi-cloud budget alert\n\n"
               f"Account/department: {account}\nProviders: {', '.join(sorted(selected))}\n"
               f"Historical period: {period_start:%Y-%m-%d} through {period_end:%Y-%m-%d} "
               f"({days} days)\n"
               f"Spending: ${total_spend:,.2f} USD\n"
               f"Budget: ${total_budget:,.2f} USD\n"
               f"Utilization: {usage_pct:.1f}%\n"
               f"Alert threshold: {threshold}%\n"
               f"Remaining budget: ${remaining:,.2f} USD\n\n"
               "This alert uses GENERATED DEMO data, not an actual provider invoice.\n"
               "Review service costs and forecast evidence in the dashboard.\n")
    if exceeded:
        st.warning(f"Threshold reached: {usage_pct:.1f}% budget usage is at or above {threshold}%.")
    else:
        st.info(f"Below threshold: {usage_pct:.1f}% budget usage; alert starts at {threshold}%.")
    with st.expander("Preview budget alert email"):
        st.write(f"**Subject:** {subject}")
        st.code(message, language="text")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("Save alert settings", key="save_budget_email_alert", use_container_width=True):
            if not valid_email:
                st.error("Enter a valid recipient email address.")
            else:
                _save_alert_settings(scope, recipient, threshold, enabled)
                st.success("Alert settings saved in the local demo database.")
    period_key = f"{period_start:%Y-%m-%d}_{period_end:%Y-%m-%d}_budget_{total_budget:.2f}"
    with _alert_db() as conn:
        sent_before = bool(conn.execute(
            "SELECT 1 FROM sent_alerts WHERE scope=? AND period_key=? AND recipient=? AND threshold=?",
            (scope, period_key, recipient, threshold)
        ).fetchone())
    with b2:
        if st.button("Check threshold and send email now", key="send_budget_email_alert",
                     use_container_width=True):
            smtp_ready = _smtp_configured()
            if not valid_email:
                st.error("Enter a valid recipient email address.")
            elif not enabled:
                st.error("Enable the alert first.")
            elif not exceeded:
                st.info("Threshold has not been reached; no email sent.")
            elif sent_before:
                st.info("An email for this recipient and threshold was already sent for this historical selection; no duplicate sent.")
            elif not smtp_ready:
                st.info("SMTP is not configured, so the dashboard will not send a live email from this environment.")
            else:
                try:
                    _send_smtp_alert(recipient, subject, message)
                except Exception as exc:
                    st.error(f"Email not sent: {type(exc).__name__}: {exc}")
                else:
                    with _alert_db() as conn:
                        conn.execute("""INSERT OR IGNORE INTO sent_alerts
                            (scope, period_key, recipient, threshold) VALUES (?, ?, ?, ?)""",
                            (scope, period_key, recipient, threshold))
                    st.success(f"Email submitted to SMTP for {recipient}.")
    if _smtp_configured():
        st.markdown("---")
        st.subheader("Send SMTP test email")
        test_recipient = st.text_input(
            "Test email recipient",
            value="vinodbellamkanda3322@gmail.com",
            key="smtp_test_recipient",
        )
        if st.button("Send threshold crossed test email", key="send_threshold_test_email"):
            try:
                _send_threshold_test_email(test_recipient, threshold_pct=threshold, spent_pct=min(100.0, max(usage_pct, threshold + 5)))
                st.success(f"Test threshold email sent to {test_recipient}.")
            except Exception as exc:
                st.error(f"SMTP test email failed: {type(exc).__name__}: {exc}")
    st.caption("To deliver actual emails, configure SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_USERNAME, SMTP_PASSWORD and SMTP_SECURITY. SMTP is optional; the dashboard remains usable without it.")


def main():
    selected, period = render_sidebar()
    account = st.sidebar.selectbox("Demo account / person", list(DEMO_ACCOUNTS))
    if "demo_seed" not in st.session_state:
        st.session_state.demo_seed = 0
    if st.sidebar.button("Generate new synthetic data"):
        st.session_state.demo_seed += 1

    days = PERIOD_DAYS[period]
    ledger = generate_period_demo(account, st.session_state.demo_seed)
    period_end = ledger["Date"].max()
    period_start = period_end - pd.Timedelta(days=days - 1)
    current = ledger.loc[(ledger["Date"] >= period_start) & ledger["Cloud"].isin(selected)].copy()
    previous = ledger.loc[(ledger["Date"] < period_start) &
                          (ledger["Date"] >= period_start - pd.Timedelta(days=days)) &
                          ledger["Cloud"].isin(selected)]

    st.title("Multi-Cloud Billing Dashboard")
    st.caption(f"SYNTHETIC DEMO | {account} | {period} | "
               f"{period_start:%d %b %Y} – {period_end:%d %b %Y} | USD")
    if not selected:
        st.warning("Select at least one cloud provider in the sidebar.")
        return

    future_daily, forecast_summary = forecast_costs_from_history(ledger, selected, days)
    # Monthly budget: editable and saved per demo account/provider selection.
    # Default is only an illustrative starting value; users can override it.
    recent_start = period_end - pd.Timedelta(days=29)
    budget_reference = ledger.loc[(ledger["Date"] >= recent_start) & ledger["Cloud"].isin(selected)]
    recent_service_spend = budget_reference.groupby(["Cloud", "Service"], as_index=False)["Cost"].sum()
    initial_monthly_budget = round(float(recent_service_spend["Cost"].sum()) * 1.10, 2)
    budget_scope = _budget_scope(account, selected)
    if st.session_state.get("monthly_budget_scope") != budget_scope:
        st.session_state.monthly_budget_scope = budget_scope
        stored_budget = _get_monthly_budget(budget_scope)
        st.session_state.monthly_budget_amount = (stored_budget if stored_budget is not None
                                                  else max(1.0, initial_monthly_budget))
    st.sidebar.markdown("---")
    st.sidebar.subheader("Cloud budget settings")
    st.sidebar.number_input("Monthly allocated budget (USD)", min_value=1.0,
                            step=100.0, format="%.2f", key="monthly_budget_amount",
                            help="Your monthly budget for the selected account and providers. "
                                 "The first value is a synthetic suggestion; edit and save it.")
    if st.sidebar.button("Save monthly budget", key="save_monthly_budget"):
        _save_monthly_budget(budget_scope, st.session_state.monthly_budget_amount)
        st.sidebar.success("Monthly budget saved locally for this account/provider selection.")
    monthly_budget = float(st.session_state.monthly_budget_amount)
    total_budget = monthly_budget * days / 30.0  # Demo treats 6 months as 180 days
    # Distribute the user-defined total across services for service-level budget usage.
    base_budgets = recent_service_spend.rename(columns={"Cost": "ReferenceSpend"})
    reference_total = float(base_budgets["ReferenceSpend"].sum())
    base_budgets["BudgetLimit"] = (base_budgets["ReferenceSpend"] /
                                     reference_total * total_budget if reference_total > 0
                                     else 0.0)

    def service_summary(cloud, name):
        subset = current.loc[current["Cloud"] == cloud]
        totals = subset.groupby("Service", as_index=False)["Cost"].sum()
        totals = totals.rename(columns={"Cost": "Spend"})
        totals = totals.merge(forecast_summary.loc[forecast_summary["Cloud"] == cloud,
                                ["Service", "Forecast"]], on="Service", how="left")
        totals = totals.merge(base_budgets.loc[base_budgets["Cloud"] == cloud,
                                 ["Service", "BudgetLimit"]], on="Service", how="left")
        totals["Budget Used %"] = (totals["Spend"] / totals["BudgetLimit"] * 100).round(1)
        return totals.rename(columns={"Service": name}).round(2)

    aws_services = service_summary("AWS", "Service")
    gcp_budgets = service_summary("GCP", "Budget")
    aws_total = float(aws_services["Spend"].sum())
    gcp_total = float(gcp_budgets["Spend"].sum())
    total_spend = aws_total + gcp_total
    total_forecast = float(future_daily["ForecastCost"].sum()) if not future_daily.empty else 0.0
    total_budget = monthly_budget * days / 30.0
    prev_spend = float(previous["Cost"].sum())
    growth = (total_spend / prev_spend - 1) * 100 if len(previous["Date"].unique()) == days and prev_spend > 0 else None

    st.subheader("Financial overview — selected period")
    overview_cols = st.columns(4)
    overview_cols[0].metric("Total spend (synthetic)", f"${total_spend:,.2f}")
    overview_cols[1].metric("Allocated budget", f"${total_budget:,.2f}")
    overview_cols[2].metric("Remaining budget", f"${total_budget - total_spend:,.2f}")
    overview_cols[3].metric("Budget used", f"{total_spend / total_budget:.1%}")
    trend_cols = st.columns(2)
    trend_cols[0].metric(f"Forecast next {days} days", f"${total_forecast:,.2f}")
    trend_cols[1].metric("Change vs prior equal period", f"{growth:+.1f}%" if growth is not None else "N/A")
    st.caption(f"Budget based on ${monthly_budget:,.2f}/month × {days}/30. "
               "Edit and save in the sidebar. Spend is synthetic; forecast covers the next equal period.")
    render_budget_email_alerts(account, selected, days, period_start, period_end,
                               total_spend, total_budget)

    # Audit trail: all figures below come from the same ledger and forecast
    # used by the headline cards, not an independently generated demo example.
    with st.expander("How Total Spend and the Forecast are calculated", expanded=True):
        st.write("**Total Spend is the sum of service costs in the selected historical period.** "
                 "The next-period forecast is a separate prediction, not an additional charge.")
        audit = current.groupby(["Cloud", "Service"], as_index=False)["Cost"].sum()
        audit = audit.rename(columns={"Cost": "Past selected-period spend (USD)"})
        predicted = (forecast_summary.rename(columns={"Forecast": "Next equal-period forecast (USD)"})
                     if not forecast_summary.empty else
                     pd.DataFrame(columns=["Cloud", "Service", "Next equal-period forecast (USD)"]))
        audit = audit.merge(predicted, on=["Cloud", "Service"], how="left")
        audit["Change (USD)"] = (audit["Next equal-period forecast (USD)"] -
                                 audit["Past selected-period spend (USD)"])
        st.dataframe(audit.round(2), use_container_width=True, hide_index=True)
        st.write(f"**Historical total ({days} days):** ${total_spend:,.2f} = "
                 f"AWS ${aws_total:,.2f} + GCP ${gcp_total:,.2f}. "
                 f"**Predicted next {days} days:** ${total_forecast:,.2f}. "
                 f"**Difference:** ${total_forecast-total_spend:+,.2f} "
                 f"({((total_forecast / total_spend - 1)*100):+.2f}% of historical spend)."
                 if total_spend else "No spending is available for the selected period.")
        halfway = period_start + pd.Timedelta(days=days // 2)
        first_half = current.loc[current["Date"] < halfway]
        second_half = current.loc[current["Date"] >= halfway]
        first_sum = float(first_half["Cost"].sum())
        second_sum = float(second_half["Cost"].sum())
        first_avg = first_sum / (days // 2)
        second_avg = second_sum / (days - days // 2)
        st.write(f"**Forecast evidence (last {days} days only):** "
                 f"first {days // 2} days = ${first_sum:,.2f} "
                 f"(${first_avg:,.2f}/day); "
                 f"last {days - days // 2} days = ${second_sum:,.2f} "
                 f"(${second_avg:,.2f}/day). "
                 "Each service's weekday averages and weekday-adjusted daily trend "
                 f"are estimated across exactly the last {days} days, then "
                 f"projected over the next {days} days. Trends are capped "
                 "to limit extreme extrapolation.")
        st.caption("A forecast below past spending does not imply a confirmed cost reduction. "
                   "These are synthetic expenses and a simple unvalidated statistical forecast; "
                   "the budget is a user-configurable demo allocation.")
    # Full audit: fixed 30-day blocks, so each past/future block has the
    # same number of days even when a calendar month has 28, 30 or 31.
    st.subheader("Forecast evidence — past vs predicted 30-day blocks")
    st.caption("Each block contains exactly 30 days. These are rolling 30-day blocks, "
               "not calendar months. Six months here means 180 days.")
    daily_actual = current.groupby("Date", as_index=False)["Cost"].sum().sort_values("Date")
    daily_predicted = (future_daily.groupby("Date", as_index=False)["ForecastCost"]
                       .sum().sort_values("Date"))
    block_rows = []
    for block_no, offset in enumerate(range(0, days, 30), start=1):
        observed = daily_actual.iloc[offset:offset + 30]
        predicted = daily_predicted.iloc[offset:offset + 30]
        block_rows.append({
            "Block": f"Block {block_no}",
            "Historical dates": f"{observed['Date'].min():%d %b %Y} – {observed['Date'].max():%d %b %Y}",
            "Historical USD": round(float(observed["Cost"].sum()), 2),
            "Forecast dates": f"{predicted['Date'].min():%d %b %Y} – {predicted['Date'].max():%d %b %Y}",
            "Predicted USD": round(float(predicted["ForecastCost"].sum()), 2),
        })
    block_table = pd.DataFrame(block_rows)
    block_table["Difference USD"] = (block_table["Predicted USD"] - block_table["Historical USD"]).round(2)
    st.dataframe(block_table, hide_index=True, use_container_width=True)
    st.line_chart(block_table.set_index("Block")[["Historical USD", "Predicted USD"]],
                  use_container_width=True)
    # Reconcile using unrounded daily data (the display table rounds each block).
    observed_check = float(daily_actual["Cost"].sum())
    forecast_check = float(daily_predicted["ForecastCost"].sum())
    if abs(observed_check - total_spend) > 0.011 or abs(forecast_check - total_forecast) > 0.011:
        st.error("Forecast reconciliation failed: daily details differ from headline totals.")
    else:
        st.caption(f"Reconciled against dashboard: past ${observed_check:,.2f}; "
                   f"forecast ${forecast_check:,.2f}; "
                   f"projected change ${forecast_check-observed_check:+,.2f} "
                   f"({100*(forecast_check/observed_check-1):+.2f}%).")

    with st.expander("Show exactly how historical trends drive the forecast", expanded=True):
        st.write("For each provider/service, Python computes its average daily cost and "
                 "weekday-adjusted linear trend across the selected historical window. "
                 "The trend is capped at ±25% of the daily baseline over the forecast horizon. "
                 "The future daily forecasts are summed, not generated by the AI model.")
        trend_rows = []
        for (cloud, service), group in current.groupby(["Cloud", "Service"]):
            history = group.sort_values("Date")
            n = len(history)
            baseline = float(history["Cost"].mean())
            weekday_means = history.groupby(history["Date"].dt.weekday)["Cost"].mean().to_dict()
            adjusted = [float(row.Cost) - weekday_means[row.Date.weekday()] + baseline
                        for row in history.itertuples(index=False)]
            center = (n - 1) / 2
            raw_slope = sum((i - center) * val for i, val in enumerate(adjusted)) / sum(
                (i - center) ** 2 for i in range(n))
            limit = baseline * 0.25 / days
            fitted_slope = max(-limit, min(limit, raw_slope))
            forecast_service = float(forecast_summary.loc[
                (forecast_summary["Cloud"] == cloud) & (forecast_summary["Service"] == service),
                "Forecast"].sum())
            trend_rows.append({
                "Cloud": cloud, "Service": service,
                "Historical daily average USD": round(baseline, 3),
                "Historical fitted trend USD/day": round(raw_slope, 4),
                "Applied bounded trend USD/day": round(fitted_slope, 4),
                "Past selected period USD": round(float(history["Cost"].sum()), 2),
                "Predicted next period USD": round(forecast_service, 2),
            })
        st.dataframe(pd.DataFrame(trend_rows), hide_index=True, use_container_width=True)
        st.caption("The 14.4% historical comparison card is separate from the forecast model; "
                   "it is not automatically applied as the future growth rate. "
                   "No forecast accuracy is claimed until the model has been backtested.")

    st.caption("Forecast uses each service's full selected 30-, 90-, or 180-day history for weekday patterns and bounded trend. "
               "Budget limits come from your configured monthly amount (default suggested from recent synthetic spending); "
               "they are not provider-configured budgets. All spending is synthetic.")
    with st.expander("View historical spend vs future forecast"):
        past_trend = current.groupby("Date", as_index=False)["Cost"].sum().rename(columns={"Cost": "Historical spend"})
        future_trend = future_daily.groupby("Date", as_index=False)["ForecastCost"].sum().rename(columns={"ForecastCost": "Forecast spend"})
        plot = past_trend.merge(future_trend, on="Date", how="outer").sort_values("Date")
        st.line_chart(plot.set_index("Date"))

    st.markdown("---")
    st.subheader("Spend trend")
    trend = current.pivot_table(index="Date", columns="Cloud", values="Cost", aggfunc="sum", fill_value=0)
    if days > 30:
        trend = trend.resample("W").sum()
        st.caption("Weekly totals")
    else:
        st.caption("Daily totals")
    st.line_chart(trend, use_container_width=True)

    left, right = st.columns(2)
    if "AWS" in selected:
        with left:
            st.subheader("AWS service spend and synthetic budget allocation")
            st.dataframe(aws_services.sort_values("Spend", ascending=False), use_container_width=True)
            st.bar_chart(aws_services.set_index("Service")["Spend"])
    if "GCP" in selected:
        with right:
            st.subheader("GCP service spend and synthetic budget allocation")
            st.dataframe(gcp_budgets.sort_values("Spend", ascending=False), use_container_width=True)
            st.bar_chart(gcp_budgets.set_index("Budget")["Spend"])

    # Derive period- and account-specific synthetic infrastructure context.
    context_rng = random.Random(DEMO_ACCOUNTS[account]["seed"] + st.session_state.demo_seed * 1009 + days)
    multiplier = DEMO_ACCOUNTS[account]["factor"]
    idle_resources = {"AWS": [], "GCP": []}
    instance_inventory = []
    resource_rows = []
    region_rows = []
    regions = {"AWS": ["us-east-1", "us-west-2", "eu-central-1"],
               "GCP": ["us-central1", "europe-west1", "asia-southeast1"]}
    instances = {"AWS": [("m5.large", "m5.xlarge"), ("c5.xlarge", "c5.large"), ("r5.xlarge", "r5.large")],
                 "GCP": [("n2-standard-4", "e2-standard-2"), ("n2-standard-8", "n2-standard-4"), ("e2-standard-4", "e2-standard-2")]}
    for cloud in selected:
        cloud_total = aws_total if cloud == "AWS" else gcp_total
        weights = [0.48, 0.33, 0.19]
        for i, region in enumerate(regions[cloud]):
            region_rows.append({"Cloud": cloud, "Region": region,
                                "Cost": round(cloud_total * weights[i], 2)})
            typ, suggestion = instances[cloud][i]
            count = max(1, round((4 + i * 2) * multiplier) + context_rng.randint(0, 2))
            cpu = context_rng.randint(12, 42)
            instance_inventory.append({"Cloud": cloud, "Region": region,
                                       "InstanceType": typ, "Count": count,
                                       "AvgCpuPercent": cpu,
                                       "IdleHours": context_rng.randint(25, 150),
                                       "Status": "Low utilization" if cpu < 25 else "Active",
                                       "SuggestedInstanceType": suggestion if cpu < 25 else "Review"})
        resource_rows.append({"Cloud": cloud, "Category": "Compute", "Score": context_rng.randint(45, 90)})
        resource_rows.append({"Cloud": cloud, "Category": "Storage", "Score": context_rng.randint(35, 75)})
        resource_rows.append({"Cloud": cloud, "Category": "Network", "Score": context_rng.randint(30, 75)})
        idle_resources[cloud] = [
            {"Resource": "Stopped instances" if cloud == "AWS" else "Idle VM instances",
             "Region": regions[cloud][0], "Count": context_rng.randint(1, 5)},
            {"Resource": "Unattached EBS volumes" if cloud == "AWS" else "Unused disks",
             "Region": regions[cloud][1], "Count": context_rng.randint(2, 7)},
        ]

    st.markdown("---")
    st.subheader("Synthetic infrastructure insights")
    st.caption("Illustrative resources, not discovered from cloud APIs. Counts change by account and regenerated scenario; "
               "the period applies to the billing ledger, not lifetime resource inventory.")
    idle_df = pd.DataFrame([{"Cloud": cloud, **entry} for cloud, items in idle_resources.items() for entry in items])
    st.write("Idle resources")
    st.dataframe(idle_df, use_container_width=True)
    st.write("Instance rightsizing opportunities")
    st.dataframe(pd.DataFrame(instance_inventory), use_container_width=True)
    st.write("Resource intensity")
    st.dataframe(pd.DataFrame(resource_rows), use_container_width=True)

    st.markdown("---")
    st.subheader("Regional cost comparison")
    region_df = pd.DataFrame(region_rows)
    st.dataframe(region_df.sort_values("Cost", ascending=False), use_container_width=True)
    st.bar_chart(region_df.set_index("Region")["Cost"])
    if len(selected) == 2:
        st.subheader("Provider comparison")
        st.bar_chart(pd.DataFrame({"Cloud": ["AWS", "GCP"],
                                   "Spend": [aws_total, gcp_total]}).set_index("Cloud"))

    st.markdown("---")
    st.subheader("AI cost optimization analysis")
    st.caption("AI or fallback recommendations use the currently selected synthetic account, "
               "period, and provider(s). Savings figures are illustrative, not validated estimates.")
    analysis_key = (account, period, tuple(selected), st.session_state.demo_seed)
    if st.session_state.get("analysis_key") != analysis_key:
        st.session_state.analysis_key = analysis_key
        st.session_state.recommendations = []
    if st.button("Generate AI analysis", key="ai_analysis_button"):
        with st.spinner("Analyzing selected spend data..."):
            st.session_state.recommendations = get_ai_recommendations(
                aws_services, gcp_budgets, aws_total, gcp_total,
                idle_resources=idle_resources,
                utilisation={"AWS": {"EC2_cpu_percent": 30} if "AWS" in selected else {},
                             "GCP": {"Compute_cpu_percent": 32} if "GCP" in selected else {}},
                instance_inventory=instance_inventory)
    recommendations = st.session_state.get("recommendations", [])
    if recommendations:
        for idx, rec in enumerate(recommendations, 1):
            if isinstance(rec, dict):
                rec = dict(rec)
                rec.setdefault("estimated_savings", "N/A")
                rec.setdefault("calculation", "Synthetic estimate based on the current utilization and spend pattern.")
                rec.setdefault("risk", "Medium")
                rec.setdefault("risk_reason", "Risk is based on implementation effort and the chance of workload disruption.")
                rec.setdefault("priority", "Next 30 days")
                rec.setdefault("priority_reason", "Priority reflects the balance between savings size and implementation effort.")
                st.markdown(f"**{idx}. {rec.get('title', 'Recommendation')}**")
                st.write(rec.get("details", ""))
                st.caption(f"Estimated savings: {rec.get('estimated_savings', 'N/A')} | "
                           f"Calculation: {rec.get('calculation', 'N/A')} | "
                           f"Confidence: {rec.get('confidence', 'N/A')}")
                st.caption(f"Risk: {rec.get('risk', 'N/A')} — {rec.get('risk_reason', 'N/A')} | "
                           f"Priority: {rec.get('priority', 'N/A')} — {rec.get('priority_reason', 'N/A')}")
            else:
                st.write(f"{idx}. {rec}")
        report = pd.DataFrame(recommendations)
        st.download_button("Download AI analysis report", report.to_csv(index=False),
                           file_name=f"ai_analysis_{account.lower()}_{days}d.csv", mime="text/csv")
    else:
        st.info("Click 'Generate AI analysis' to analyze the current selection.")

    render_what_if_simulator(account, selected, ledger, instance_inventory,
                             st.session_state.demo_seed, recommendations)

    render_ai_usage_monitor()
    render_ai_email_alerts()

    st.download_button("Download selected billing data", current.to_csv(index=False),
                       file_name=f"synthetic_billing_{account.lower()}_{days}d.csv", mime="text/csv")


if __name__ == "__main__":
    main()
