"""Weekly meeting report generation and AWS Lambda adapters."""

from app.reports.weekly import build_weekly_report

__all__ = ["build_weekly_report"]
