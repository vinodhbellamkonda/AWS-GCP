import os
import json
from typing import Dict, List

import httpx
from langchain_openai import ChatOpenAI


def get_llm():
    api_key = os.getenv("GENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("GENAI_BASE_URL", "https://genailab.tcs.in")
    model = os.getenv("GENAI_MODEL", "azure/genailab-maas-gpt-35-turbo")

    if not api_key:
        raise ValueError("Missing API key. Set GENAI_API_KEY or OPENAI_API_KEY before running this script.")

    return ChatOpenAI(
        base_url=base_url,
        model=model,
        api_key=api_key,
        http_client=httpx.Client(verify=False),
        temperature=0.2,
    )


def build_dashboard_summary() -> Dict:
    """Return dashboard data in a structured form for AI analysis."""
    return {
        "report_name": "Multi-Cloud Billing Dashboard",
        "period": "Last 6 months",
        "clouds": {
            "AWS": {
                "total_spend": 37000,
                "services": [
                    {"service": "Amazon EC2", "spend": 2600},
                    {"service": "Amazon S3", "spend": 920},
                    {"service": "Amazon RDS", "spend": 1180},
                    {"service": "AWS Lambda", "spend": 460},
                    {"service": "Amazon CloudFront", "spend": 360},
                ],
            },
            "GCP": {
                "total_spend": 23500,
                "services": [
                    {"service": "Compute Engine", "spend": 1750},
                    {"service": "Cloud Storage", "spend": 760},
                    {"service": "BigQuery", "spend": 980},
                    {"service": "Cloud Run", "spend": 365},
                    {"service": "Networking", "spend": 470},
                ],
            },
        },
        "monthly_trend": {"Jan": 6800, "Feb": 8000, "Mar": 7900, "Apr": 9400, "May": 10600, "Jun": 11900},
        "observations": [
            "Spend is increasing month-over-month by over 14%.",
            "Compute services represent the largest cost concentration.",
            "Cloud storage and analytics are secondary cost drivers.",
        ],
    }


def build_ai_prompt(report: Dict) -> str:
    return f"""
You are a senior cloud cost optimization analyst. Analyze the following dashboard report and provide a concise but actionable business summary.

Requirements:
1. Start with a 3-bullet executive summary.
2. Identify the biggest cost drivers and why they are expensive.
3. Recommend 5 practical cost-reduction actions with estimated savings percentages.
4. Suggest an implementation timeline for the next 30 days.
5. Highlight risks to watch for and how to mitigate them.
6. Keep the answer concise, executive-friendly, and based on the numbers provided.

Dashboard report:
{json.dumps(report, indent=2)}
"""


def analyze_dashboard_report() -> str:
    llm = get_llm()
    report = build_dashboard_summary()
    prompt = build_ai_prompt(report)
    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


if __name__ == "__main__":
    summary = analyze_dashboard_report()
    print(summary)
