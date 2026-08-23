"""SEC EDGAR filings collector (sources.yaml: macro.sec_edgar)."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from dateutil import parser as dateparser

from collectors.base import RawItem, RunStats, get_json, logger

COLLECTOR = "sec-edgar"
MAX_FILINGS_PER_COMPANY = 10
REQUEST_SLEEP = 0.2


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = dateparser.isoparse(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def filing_url(cik: str, accession_number: str, primary_document: str) -> str:
    cik_int = int(cik)
    accession = accession_number.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{primary_document}"


def parse_submissions(data: dict, company: dict, forms: list[str]) -> list[RawItem]:
    recent = data.get("filings", {}).get("recent", {})
    form_list = recent.get("form", [])
    accession_list = recent.get("accessionNumber", [])
    date_list = recent.get("filingDate", [])
    doc_list = recent.get("primaryDocument", [])
    name = company.get("name", "")
    cik = company.get("cik", "")

    items: list[RawItem] = []
    for i, form in enumerate(form_list):
        if form not in forms:
            continue
        accession = accession_list[i] if i < len(accession_list) else ""
        if not accession:
            continue
        primary_doc = doc_list[i] if i < len(doc_list) else ""
        filing_date = date_list[i] if i < len(date_list) else ""
        items.append(
            RawItem(
                source_id="sec-edgar",
                external_id=accession,
                kind="filing",
                title=f"{name} {form} filing",
                url=filing_url(cik, accession, primary_doc),
                published_at=_parse_dt(filing_date),
                country="US",
                category="earnings",
                payload={
                    "form": form,
                    "filing_date": filing_date,
                    "primary_document": primary_doc,
                    "cik": cik,
                    "ticker": company.get("ticker", ""),
                    "company": name,
                },
            )
        )
        if len(items) >= MAX_FILINGS_PER_COMPANY:
            break
    return items


def collect(config: dict) -> tuple[list[RawItem], RunStats]:
    stats = RunStats(collector=COLLECTOR)
    user_agent = os.environ.get("SEC_EDGAR_USER_AGENT")
    if not user_agent:
        stats.error = "skipped: no SEC_EDGAR_USER_AGENT"
        return [], stats.finish("success")

    forms = config.get("forms", [])
    items: list[RawItem] = []
    for company in config.get("companies", []):
        cik = company.get("cik", "")
        try:
            data = get_json(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers={"User-Agent": user_agent},
            )
        except Exception as exc:
            stats.failed += 1
            logger.warning("sec-edgar: CIK %s failed: %s", cik, exc)
            time.sleep(REQUEST_SLEEP)
            continue
        company_items = parse_submissions(data, company, forms)
        items.extend(company_items)
        stats.fetched += len(company_items)
        time.sleep(REQUEST_SLEEP)
    return items, stats.finish()
