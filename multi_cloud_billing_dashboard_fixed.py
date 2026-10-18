import io
import json
import os
import random
import re
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
    .main {
        background: linear-gradient(180deg, #0b1220 0%, #111827 100%);
    }
    .stApp {
        color: #e5e7eb;
    }
    h1, h2, h3, h4, h5, h6,
    .stSubheader,
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
    .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
        color: #111111 !important;
        font-weight: 800;
        letter-spacing: 0.01em;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
    }
    div[data-testid="stMetricLabel"] {
        color: #9ca3af;
    }
    .block-container {
        padding-top: 1.5rem;
    }
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }
    .stButton > button {
        background: #000000;
        color: #ffffff;
        border: 2px solid rgba(255,255,255,0.95);
        border-radius: 10px;
        font-weight: 800;
        padding: 0.7rem 1.3rem;
        box-shadow: 0 8px 18px rgba(0,0,0,0.35);
        min-height: 44px;
    }
    .stButton > button:hover {
        background: #111111;
        border-color: rgba(255,255,255,1);
        color: #ffffff;
    }
    .stButton > button:focus:not(:active) {
        box-shadow: 0 0 0 0.25rem rgba(255,255,255,0.35);
    }
    div[data-testid="stDownloadButton"] > button {
        background: #000000;
        color: #ffffff;
        border: 2px solid rgba(255,255,255,0.95);
        border-radius: 10px;
        font-weight: 800;
        padding: 0.7rem 1.3rem;
        box-shadow: 0 8px 18px rgba(0,0,0,0.35);
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background: #111111;
        color: #ffffff;
    }
    .ai-highlight {
        background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(229,231,235,0.9));
        border: 1px solid rgba(15,23,42,0.75);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        color: #111827;
        box-shadow: 0 0 0 1px rgba(15,23,42,0.15), 0 10px 20px rgba(15, 23, 42, 0.2);
        line-height: 1.6;
    }
    .ai-highlight strong {
        color: #111111;
        font-size: 1.05rem;
        font-weight: 800;
        letter-spacing: 0.01em;
    }
    .ai-highlight span,
    .ai-highlight small {
        color: #111827;
    }
    .ai-highlight small {
        opacity: 1;
        font-weight: 700;
    }
    .ai-header {
        color: #111111;
        font-size: 1.15rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
        display: block;
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
        "GENAI_API_KEY=...\nOPENAI_API_KEY=...\nGENAI_BASE_URL=https://genailab.tcs.in\nGENAI_MODEL=azure/genailab-maas-gpt-35-turbo"
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

    recs = []

    if stale_instances:
        top_entry = max(stale_instances, key=lambda x: x.get("IdleHours", 0))
        recs.append({
            "title": "Downsize idle instances in active regions",
            "details": f"{top_entry.get('Cloud')} has {sum(item.get('Count', 0) for item in stale_instances)} low-utilization instances in {top_entry.get('Region')} running {top_entry.get('InstanceType')} for {top_entry.get('IdleHours')} idle hours; change to {top_entry.get('SuggestedInstanceType')} to lower cost.",
            "estimated_savings": "$2,100/month",
            "confidence": "High",
            "risk": "Low",
            "priority": "Immediate",
        })

    if aws_cpu < 35 or aws_stopped > 0:
        recs.append({
            "title": "Right-size EC2 instances",
            "details": f"AWS EC2 utilization is around {aws_cpu}% and {aws_stopped} stopped instances were observed in {aws_stop_region}, indicating oversized compute capacity.",
            "estimated_savings": "$1,800/month",
            "confidence": "High",
            "risk": "Low",
            "priority": "Immediate",
        })

    if gcp_cpu < 40 or gcp_idle > 0:
        recs.append({
            "title": "Reduce idle GCP compute",
            "details": f"GCP compute is at about {gcp_cpu}% utilization and {gcp_idle} idle VMs are present in {gcp_idle_region}; reduce machine size or shut down non-production workloads.",
            "estimated_savings": "$1,400/month",
            "confidence": "High",
            "risk": "Low",
            "priority": "Immediate",
        })

    if aws_ebs > 0 or gcp_disks > 0:
        recs.append({
            "title": "Clean up orphaned storage",
            "details": f"There are {aws_ebs} unattached AWS EBS volumes and {gcp_disks} unused GCP disks, which are common sources of recurring waste across the active regions.",
            "estimated_savings": "$900/month",
            "confidence": "High",
            "risk": "Low",
            "priority": "Immediate",
        })

    if utilisation.get("AWS", {}).get("Lambda_idle_hours", 0) > 10 or utilisation.get("GCP", {}).get("CloudRun_scale_to_zero", False):
        recs.append({
            "title": "Improve autoscaling and scale-to-zero",
            "details": "Lambda and Cloud Run workloads show idle time; align instance count with traffic patterns and pause non-critical workloads during off-hours.",
            "estimated_savings": "$1,200/month",
            "confidence": "Medium",
            "risk": "Low",
            "priority": "Next 30 days",
        })

    recs.append({
        "title": "Move non-critical workloads to cheaper regions",
        "details": "Regional cost analysis shows a large gap between the current primary region and lower-cost regions; shift batch and non-latency-sensitive workloads to reduce spend.",
        "estimated_savings": "$1,500/month",
        "confidence": "Medium",
        "risk": "Medium",
        "priority": "Next 30 days",
    })

    recs.append({
        "title": "Review storage tiering and analytics cost",
        "details": "The demo data shows a high share of storage and analytics spend; archive old objects and optimize query windows to reduce monthly cost.",
        "estimated_savings": "$750/month",
        "confidence": "Medium",
        "risk": "Medium",
        "priority": "Next 30 days",
    })

    while len(recs) < 5:
        recs.append({
            "title": "General optimization review",
            "details": "Continue reviewing service utilization and cost trends to remove waste in the next planning cycle.",
            "estimated_savings": "$500/month",
            "confidence": "Medium",
            "risk": "Low",
            "priority": "Next quarter",
        })

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


def get_ai_recommendations(aws_services, gcp_budgets, aws_total, gcp_total, idle_resources=None, utilisation=None, instance_inventory=None):
    """Return actionable cost reduction recommendations with details. Prefers the configured LangChain/OpenAI-compatible endpoint."""
    aws_top = aws_services.sort_values('Spend', ascending=False).to_dict('records')
    gcp_top = gcp_budgets.sort_values('Spend', ascending=False).to_dict('records')
    default_recommendations = _build_demo_recommendations(aws_services, gcp_budgets, idle_resources, utilisation, instance_inventory)

    api_key = os.getenv('GENAI_API_KEY') or os.getenv('OPENAI_API_KEY')
    base_url = os.getenv('GENAI_BASE_URL', '******')
    model = os.getenv('GENAI_MODEL', 'azure/genailab-maas-gpt-35-turbo')
    idle_payload = json.dumps(idle_resources or {}, default=str)
    util_payload = json.dumps(utilisation or {}, default=str)
    instance_payload = json.dumps(instance_inventory or [], default=str)

    if api_key and ChatOpenAI is not None and httpx is not None:
        prompt = f'''
        Analyze this cloud spend summary and provide a JSON array of 5 cost-saving recommendations.
        Each item must include these exact keys: title, details, estimated_savings, confidence, risk, priority.
        Keep the values concise but useful for a dashboard presentation.
  
        AWS spend summary:
        {json.dumps(aws_top, default=str)}
  
        GCP spend summary:
        {json.dumps(gcp_top, default=str)}
  
        Total AWS spend: ${aws_total:,.2f}
        Total GCP spend: ${gcp_total:,.2f}
 
        Idle resource summary:
        {idle_payload}

        Instance inventory and rightsizing opportunities:
        {instance_payload}
 
        Utilization summary:
        {util_payload}
        '''
        try:
            client = httpx.Client(verify=False)
            llm = ChatOpenAI(
                base_url=base_url,
                model=model,
                api_key=api_key,
                http_client=client,
                temperature=0.2,
            )
            response = llm.invoke(prompt)
            text = response.content if hasattr(response, 'content') else str(response)
            parsed = _parse_ai_analysis_payload(text)
            if parsed:
                return parsed
        except Exception:
            pass

    if api_key and OpenAI is not None:
        prompt = f'''
        Analyze this cloud spend summary and provide a JSON array of 5 cost-saving recommendations.
        Each item must include these exact keys: title, details, estimated_savings, confidence, risk, priority.
        Keep the values concise but useful for a dashboard presentation.
  
        AWS spend summary:
        {json.dumps(aws_top, default=str)}
  
        GCP spend summary:
        {json.dumps(gcp_top, default=str)}
  
        Total AWS spend: ${aws_total:,.2f}
        Total GCP spend: ${gcp_total:,.2f}
 
        Idle resource summary:
        {idle_payload}

        Instance inventory and rightsizing opportunities:
        {instance_payload}
 
        Utilization summary:
        {util_payload}
        '''
        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {'role': 'system', 'content': 'You are a cloud cost optimization expert.'},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.2,
                max_tokens=600,
            )
            text = response.choices[0].message.content.strip()
            parsed = _parse_ai_analysis_payload(text)
            if parsed:
                return parsed
        except Exception:
            pass

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
    """Create a deterministic 180-day synthetic *daily* billing ledger per account.

    All selectable periods are subsets of this same ledger, not fresh random
    generations for each selection. Daily services aggregate to dashboard totals.
    """
    profile = DEMO_ACCOUNTS[account]
    rng = random.Random(profile["seed"] + seed * 1009)
    days = pd.date_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=180)
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

    def service_summary(cloud, name):
        subset = current.loc[current["Cloud"] == cloud]
        totals = subset.groupby("Service", as_index=False)["Cost"].sum()
        totals = totals.rename(columns={"Service": name, "Cost": "Spend"})
        totals["Forecast"] = (totals["Spend"] * 1.08).round(2)
        return totals.round(2)

    aws_services = service_summary("AWS", "Service")
    gcp_budgets = service_summary("GCP", "Budget")
    aws_total = float(aws_services["Spend"].sum())
    gcp_total = float(gcp_budgets["Spend"].sum())
    total_spend = aws_total + gcp_total
    total_forecast = total_spend * 1.08  # illustrative forecast, not an actual cloud forecast
    prev_spend = float(previous["Cost"].sum())
    growth = (total_spend / prev_spend - 1) * 100 if prev_spend else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Selected-period spend", f"${total_spend:,.2f}")
    c2.metric("Illustrative forecast (+8%)", f"${total_forecast:,.2f}")
    c3.metric("Spend / forecast", f"{total_spend / total_forecast:.1%}" if total_forecast else "N/A")
    c4.metric("Change vs prior equal period", f"{growth:+.1f}%" if growth is not None else "N/A")

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
            st.subheader("AWS service spend")
            st.dataframe(aws_services.sort_values("Spend", ascending=False), use_container_width=True)
            st.bar_chart(aws_services.set_index("Service")["Spend"])
    if "GCP" in selected:
        with right:
            st.subheader("GCP service spend")
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
                st.markdown(f"**{idx}. {rec.get('title', 'Recommendation')}**")
                st.write(rec.get("details", ""))
                st.caption(f"Estimated savings: {rec.get('estimated_savings', 'N/A')} | "
                           f"Confidence: {rec.get('confidence', 'N/A')} | "
                           f"Risk: {rec.get('risk', 'N/A')} | Priority: {rec.get('priority', 'N/A')}")
            else:
                st.write(f"{idx}. {rec}")
        report = pd.DataFrame(recommendations)
        st.download_button("Download AI analysis report", report.to_csv(index=False),
                           file_name=f"ai_analysis_{account.lower()}_{days}d.csv", mime="text/csv")
    else:
        st.info("Click 'Generate AI analysis' to analyze the current selection.")

    st.download_button("Download selected billing data", current.to_csv(index=False),
                       file_name=f"synthetic_billing_{account.lower()}_{days}d.csv", mime="text/csv")


if __name__ == "__main__":
    main()
