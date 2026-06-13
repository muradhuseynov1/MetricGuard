from __future__ import annotations

import json
import os
import re
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from metricguard.hashing import write_manifest


@dataclass(frozen=True)
class CitationAuditOutcome:
    verdict: str
    reason: str
    artifacts: list[Path]


@dataclass(frozen=True)
class LiveCitationConfig:
    enabled: bool = False
    enforce: bool = False
    timeout_seconds: int = 8

    @classmethod
    def from_env(cls) -> "LiveCitationConfig":
        enabled = _truthy(os.environ.get("METRICGUARD_LIVE_CITATION_CHECKS"))
        return cls(
            enabled=enabled,
            enforce=_truthy(os.environ.get("METRICGUARD_ENFORCE_LIVE_CITATION_CHECKS")),
            timeout_seconds=int(os.environ.get("METRICGUARD_CITATION_TIMEOUT_SECONDS", "8")),
        )


SOURCE_REGISTRY = {
    "MG-LOCAL-2026": {
        "title": "MetricGuard Local Citation Audit Fixture",
        "authors": ["MetricGuard Demo Team"],
        "year": "2026",
        "journal": "Local Evidence Fixture",
        "doi": "10.0000/metricguard.local.2026",
        "url": "metricguard://sources/local-citation-audit",
        "text": (
            "MetricGuard audits generated answers by extracting citations, checking "
            "whether cited sources exist, verifying quoted text, comparing citation "
            "metadata, and rejecting claims when the cited evidence is missing or "
            "overclaimed. The local demo records both rejected and repaired citation "
            "answers as evidence graph nodes."
        ),
        "supports": [
            "MetricGuard audits generated answers by extracting citations",
            "records both rejected and repaired citation answers as evidence graph nodes",
        ],
    }
}

BAD_ANSWER = """# Generated Answer

MetricGuard-style citation auditing reduces hallucinated references by 91% in
agentic research workflows [1]. Nguyen et al. write that "deterministic citation
gates eliminate fabricated evidence in agentic workflows" [1].

[1] Nguyen, A., Patel, R., and Smith, L. "MetricGuard: Deterministic Citation
Gates for AI Research." Nature Machine Intelligence, 2025.
DOI: 10.1038/s42256-025-99999-9
URL: https://example.invalid/metricguard-citation-gates
"""

REPAIRED_ANSWER = """# Repaired Answer

MetricGuard can audit generated answers by extracting citations, checking that
the cited source exists, verifying quoted text, comparing metadata, and rejecting
claims when evidence is missing or overclaimed [1]. The local demo records both
rejected and repaired citation answers as evidence graph nodes [1].

[1] MetricGuard Demo Team. "MetricGuard Local Citation Audit Fixture." Local
Evidence Fixture, 2026. DOI: 10.0000/metricguard.local.2026
URL: metricguard://sources/local-citation-audit
"""


def run_fake_citation_audit(
    artifacts_dir: Path,
    live_config: LiveCitationConfig | None = None,
) -> tuple[CitationAuditOutcome, CitationAuditOutcome]:
    citation_dir = artifacts_dir / "citations"
    if citation_dir.exists():
        shutil.rmtree(citation_dir)
    citation_dir.mkdir(parents=True, exist_ok=True)

    sources_dir = citation_dir / "sources"
    sources_dir.mkdir()
    (sources_dir / "source_registry.json").write_text(
        json.dumps(SOURCE_REGISTRY, indent=2) + "\n",
        encoding="utf-8",
    )

    bad_answer_path = citation_dir / "bad_answer.md"
    bad_answer_path.write_text(BAD_ANSWER, encoding="utf-8")
    repaired_answer_path = citation_dir / "repaired_answer.md"
    repaired_answer_path.write_text(REPAIRED_ANSWER, encoding="utf-8")

    rejected = audit_citation_answer(
        answer_path=bad_answer_path,
        run_id="fake_citations_rejected",
        citation_dir=citation_dir,
        live_config=live_config,
    )
    accepted = audit_citation_answer(
        answer_path=repaired_answer_path,
        run_id="fake_citations_repaired",
        citation_dir=citation_dir,
        live_config=live_config,
    )
    return rejected, accepted


def audit_citation_answer(
    answer_path: Path,
    run_id: str,
    citation_dir: Path,
    live_config: LiveCitationConfig | None = None,
) -> CitationAuditOutcome:
    audit_dir = citation_dir / run_id
    audit_dir.mkdir(parents=True, exist_ok=True)
    live_config = live_config or LiveCitationConfig.from_env()

    answer_text = answer_path.read_text(encoding="utf-8")
    extracted = _extract_citations(answer_text)
    extraction_path = audit_dir / "extracted_citations.json"
    extraction_path.write_text(json.dumps({"citations": extracted}, indent=2) + "\n", encoding="utf-8")

    deterministic_checks = _deterministic_checks(extracted, answer_text)
    deterministic_path = audit_dir / "deterministic_verification.json"
    deterministic_path.write_text(json.dumps(deterministic_checks, indent=2) + "\n", encoding="utf-8")

    live_resolution = _live_resolution_checks(extracted, live_config)
    live_resolution_path = audit_dir / "live_citation_resolution.json"
    live_resolution_path.write_text(json.dumps(live_resolution, indent=2) + "\n", encoding="utf-8")

    judge_report = _judge_support(answer_text, extracted)
    judge_path = audit_dir / "judge_report.md"
    judge_path.write_text(_format_judge_report(judge_report), encoding="utf-8")

    failed = [check["name"] for check in deterministic_checks["checks"] if not check["passed"]]
    if live_resolution["enforced"]:
        failed.extend(check["name"] for check in live_resolution["checks"] if not check["passed"])
    if not judge_report["supported"]:
        failed.append("llm_judge_support")

    verdict = "accepted" if not failed else "rejected"
    if verdict == "accepted":
        reason = "all citations resolved, metadata matched, and claims were supported by source text"
    else:
        reason = "failed checks: " + ", ".join(failed)

    verdict_path = audit_dir / "verdict.json"
    verdict_path.write_text(
        json.dumps({"verdict": verdict, "reason": reason, "accepted": verdict == "accepted"}, indent=2) + "\n",
        encoding="utf-8",
    )

    report_path = audit_dir / "audit_report.md"
    report_path.write_text(
        _format_audit_report(
            answer_path=answer_path,
            deterministic_checks=deterministic_checks,
            live_resolution=live_resolution,
            judge_report=judge_report,
            verdict=verdict,
            reason=reason,
        ),
        encoding="utf-8",
    )

    artifact_files = [
        answer_path,
        extraction_path,
        deterministic_path,
        live_resolution_path,
        judge_path,
        verdict_path,
        report_path,
    ]
    manifest_path = write_manifest(audit_dir, artifact_files)
    artifact_files.append(manifest_path)
    return CitationAuditOutcome(verdict=verdict, reason=reason, artifacts=artifact_files)


def _extract_citations(answer_text: str) -> list[dict[str, object]]:
    citations: list[dict[str, object]] = []
    footnote_pattern = re.compile(
        r"^\[(?P<label>\d+)\]\s+(?P<body>.*?)(?=^\[\d+\]\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    for match in footnote_pattern.finditer(answer_text):
        body = " ".join(match.group("body").split())
        citations.append(
            {
                "label": match.group("label"),
                "raw": body,
                "title": _first_quoted(body),
                "doi": _first_match(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b", body),
                "url": _first_match(r"\b(?:https?://|metricguard://)\S+", body),
                "year": _first_match(r"\b(20\d{2}|19\d{2})\b", body),
                "journal": _journal_from_body(body),
                "authors": _authors_from_body(body),
                "quoted_text": _quoted_text_for_label(answer_text, match.group("label")),
            }
        )
    return citations


def _deterministic_checks(extracted: list[dict[str, object]], answer_text: str) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    checks.append(
        {
            "name": "citation_extraction",
            "passed": bool(extracted),
            "details": f"found {len(extracted)} citation(s)",
        }
    )
    for citation in extracted:
        source = _source_for(citation)
        label = citation["label"]
        checks.extend(
            [
                {
                    "name": f"source_exists_{label}",
                    "passed": source is not None,
                    "details": "source matched registry" if source else "no matching DOI or URL in registry",
                },
                {
                    "name": f"doi_or_url_valid_{label}",
                    "passed": source is not None and (citation.get("doi") == source["doi"] or citation.get("url") == source["url"]),
                    "details": f"doi={citation.get('doi')}, url={citation.get('url')}",
                },
                {
                    "name": f"metadata_match_{label}",
                    "passed": _metadata_matches(citation, source),
                    "details": _metadata_details(citation, source),
                },
                {
                    "name": f"quote_present_{label}",
                    "passed": _quote_present(citation, source),
                    "details": _quote_details(citation, source),
                },
                {
                    "name": f"claimed_entities_present_{label}",
                    "passed": _entities_present(answer_text, source),
                    "details": _entity_details(source),
                },
            ]
        )
    return {"checks": checks}


def _live_resolution_checks(
    extracted: list[dict[str, object]],
    config: LiveCitationConfig,
) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    if not config.enabled:
        return {
            "enabled": False,
            "enforced": False,
            "checks": checks,
            "note": "Set METRICGUARD_LIVE_CITATION_CHECKS=1 to resolve public DOI/URL targets.",
        }
    for citation in extracted:
        label = str(citation["label"])
        doi = citation.get("doi")
        url = citation.get("url")
        if isinstance(doi, str):
            checks.append(_resolve_doi(label, doi, config.timeout_seconds))
        if isinstance(url, str):
            checks.append(_resolve_url(label, url, config.timeout_seconds))
        if not doi and not url:
            checks.append(
                {
                    "name": f"live_citation_target_{label}",
                    "passed": False,
                    "details": "citation has neither DOI nor URL",
                }
            )
    return {
        "enabled": True,
        "enforced": config.enforce,
        "checks": checks,
        "note": (
            "Live checks are verdict-enforced."
            if config.enforce
            else "Live checks are recorded as evidence but do not control the verdict."
        ),
    }


def _resolve_doi(label: str, doi: str, timeout_seconds: int) -> dict[str, object]:
    if doi.startswith("10.0000/"):
        return {
            "name": f"live_doi_resolution_{label}",
            "passed": True,
            "details": f"local fixture DOI exempt from public resolver: {doi}",
        }
    return _http_probe(
        name=f"live_doi_resolution_{label}",
        url=f"https://doi.org/{doi}",
        timeout_seconds=timeout_seconds,
    )


def _resolve_url(label: str, url: str, timeout_seconds: int) -> dict[str, object]:
    if url.startswith("metricguard://"):
        return {
            "name": f"live_url_resolution_{label}",
            "passed": True,
            "details": f"trusted local fixture URL: {url}",
        }
    return _http_probe(
        name=f"live_url_resolution_{label}",
        url=url,
        timeout_seconds=timeout_seconds,
    )


def _http_probe(name: str, url: str, timeout_seconds: int) -> dict[str, object]:
    headers = {"User-Agent": "MetricGuard/0.1 citation-verifier"}
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                final_url = response.geturl()
                return {
                    "name": name,
                    "passed": 200 <= response.status < 400,
                    "details": f"{method} {url} -> HTTP {response.status}; final_url={final_url}",
                }
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in {405, 403}:
                continue
            return {
                "name": name,
                "passed": False,
                "details": f"{method} {url} -> HTTP {exc.code}",
            }
        except urllib.error.URLError as exc:
            if method == "HEAD":
                continue
            return {
                "name": name,
                "passed": False,
                "details": f"{method} {url} failed: {exc.reason}",
            }
        except TimeoutError:
            if method == "HEAD":
                continue
            return {
                "name": name,
                "passed": False,
                "details": f"{method} {url} timed out after {timeout_seconds}s",
            }
    return {"name": name, "passed": False, "details": f"could not resolve {url}"}


def _judge_support(answer_text: str, extracted: list[dict[str, object]]) -> dict[str, object]:
    unsupported: list[str] = []
    for citation in extracted:
        source = _source_for(citation)
        if not source:
            unsupported.append(f"[{citation['label']}] has no source, so it cannot support claims")
            continue
        unsupported.extend(_unsupported_claims(answer_text, source, str(citation["label"])))
    return {
        "supported": not unsupported,
        "unsupported_claims": unsupported,
        "note": "Deterministic stand-in for LLM-as-judge in the offline demo.",
    }


def _unsupported_claims(answer_text: str, source: dict[str, object], label: str) -> list[str]:
    claims = _sentences_for_label(answer_text, label)
    source_text = str(source["text"]).lower()
    unsupported: list[str] = []
    for claim in claims:
        normalized = claim.lower()
        if "91%" in normalized:
            unsupported.append("91% improvement claim is not present in the cited source")
        elif "eliminat" in normalized and "fabricated evidence" in normalized:
            unsupported.append("absolute elimination claim is stronger than the cited source")
        elif not any(str(fragment).lower() in source_text for fragment in source["supports"]):
            unsupported.append(f"no configured support fragment matched claim: {claim}")
    return unsupported


def _source_for(citation: dict[str, object]) -> dict[str, object] | None:
    for source in SOURCE_REGISTRY.values():
        if citation.get("doi") == source["doi"] or citation.get("url") == source["url"]:
            return source
    return None


def _metadata_matches(citation: dict[str, object], source: dict[str, object] | None) -> bool:
    if source is None:
        return False
    return (
        citation.get("title") == source["title"]
        and citation.get("year") == source["year"]
        and citation.get("journal") == source["journal"]
        and all(author in str(citation.get("authors", "")) for author in source["authors"])
    )


def _quote_present(citation: dict[str, object], source: dict[str, object] | None) -> bool:
    quote = citation.get("quoted_text")
    if not quote:
        return True
    if source is None:
        return False
    return str(quote).lower() in str(source["text"]).lower()


def _entities_present(answer_text: str, source: dict[str, object] | None) -> bool:
    if source is None:
        return False
    lowered = answer_text.lower()
    return "metricguard" in lowered and "citation" in lowered


def _metadata_details(citation: dict[str, object], source: dict[str, object] | None) -> str:
    if source is None:
        return "metadata cannot be checked without a source"
    return (
        f"title={citation.get('title')!r}, year={citation.get('year')!r}, "
        f"journal={citation.get('journal')!r}, authors={citation.get('authors')!r}"
    )


def _quote_details(citation: dict[str, object], source: dict[str, object] | None) -> str:
    quote = citation.get("quoted_text")
    if not quote:
        return "no direct quote included; nothing to verify"
    if source is None:
        return f"quote={quote!r}; no source found"
    return f"quote={quote!r}"


def _entity_details(source: dict[str, object] | None) -> str:
    if source is None:
        return "no source found"
    return "answer and source both discuss MetricGuard citation auditing"


def _format_judge_report(judge_report: dict[str, object]) -> str:
    lines = [
        "# Citation Judge Report",
        "",
        f"Supported: **{str(judge_report['supported']).upper()}**",
        "",
        str(judge_report["note"]),
        "",
        "## Unsupported Claims",
        "",
    ]
    unsupported = judge_report["unsupported_claims"]
    if unsupported:
        lines.extend(f"- {item}" for item in unsupported)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _format_audit_report(
    *,
    answer_path: Path,
    deterministic_checks: dict[str, object],
    live_resolution: dict[str, object],
    judge_report: dict[str, object],
    verdict: str,
    reason: str,
) -> str:
    lines = [
        f"# Citation Audit Report: {answer_path.stem}",
        "",
        f"Verdict: **{verdict.upper()}**",
        "",
        f"Reason: {reason}",
        "",
        "## Deterministic Checks",
        "",
    ]
    for check in deterministic_checks["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: `{check['name']}` - {check['details']}")
    lines.extend(
        [
            "",
            "## Live DOI/URL Resolution",
            "",
            f"- Enabled: `{live_resolution['enabled']}`",
            f"- Enforced: `{live_resolution['enforced']}`",
            f"- Note: {live_resolution['note']}",
        ]
    )
    for check in live_resolution["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: `{check['name']}` - {check['details']}")
    lines.extend(["", "## Judge", "", f"- Supported: `{judge_report['supported']}`"])
    for item in judge_report["unsupported_claims"]:
        lines.append(f"- Unsupported: {item}")
    lines.append("")
    return "\n".join(lines)


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    if not match:
        return None
    return match.group(0).rstrip(".,)")


def _first_quoted(text: str) -> str | None:
    match = re.search(r'"([^"]+)"', text)
    return match.group(1).rstrip(".") if match else None


def _journal_from_body(body: str) -> str | None:
    for journal in ("Nature Machine Intelligence", "Local Evidence Fixture"):
        if journal in body:
            return journal
    return None


def _authors_from_body(body: str) -> str:
    return body.split('"', 1)[0].strip().rstrip(".")


def _quoted_text_for_label(answer_text: str, label: str) -> str | None:
    marker = f"[{label}]"
    quote_pattern = re.compile(r'"([^"]+)"\s*' + re.escape(marker))
    match = quote_pattern.search(answer_text)
    return match.group(1) if match else None


def _sentences_for_label(answer_text: str, label: str) -> list[str]:
    body = answer_text.split(f"[{label}] ", 1)[0]
    sentences = re.split(r"(?<=[.!?])\s+", body)
    return [sentence.strip() for sentence in sentences if f"[{label}]" in sentence]


def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}
