"""
Checklist templates for vendor/tool due diligence.

Grounded in the real, standard 6-domain vendor due-diligence framework
(business/financial stability, information security, privacy & compliance,
operational resilience, legal/contract risk, ethics/ESG) and the standard
security sub-categories (identity/access, vulnerability management, logging/
monitoring, encryption, incident response, architecture) -- confirmed via
research, not invented. Scoped honestly to what a research agent can actually
check from public evidence; items requiring direct vendor cooperation (a
filled-out security questionnaire, an NDA'd pen-test report) or professional
judgment (legal/contract review) are explicitly out of scope -- see each
item's `scope_note`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CheckKind(str, Enum):
    WEB_RESEARCH = "web_research"  # answered via DueDiligenceAgent.investigate()
    NVD_LOOKUP = "nvd_lookup"  # answered via nvd_lookup.search_nvd()


@dataclass(frozen=True)
class ChecklistItem:
    key: str
    label: str
    domain: str  # which of the 6 due-diligence domains this belongs to
    kind: CheckKind
    prompt_template: str  # {subject} gets substituted
    scope_note: str  # what this can and can't actually establish


@dataclass(frozen=True)
class ChecklistTemplate:
    key: str
    label: str
    description: str
    items: tuple[ChecklistItem, ...]


OPEN_SOURCE_LIBRARY = ChecklistTemplate(
    key="open_source_library",
    label="Open-Source Library / Framework",
    description="For adopting an open-source tool, library, or framework into internal systems.",
    items=(
        ChecklistItem(
            key="license",
            label="License terms",
            domain="Legal & contract risk",
            kind=CheckKind.WEB_RESEARCH,
            prompt_template="{subject} has an open-source license that permits commercial/internal enterprise use without requiring source disclosure of proprietary code that uses it.",
            scope_note="Confirms the published license text and its general terms. Not a substitute for legal review of how your specific usage pattern interacts with it.",
        ),
        ChecklistItem(
            key="known_vulnerabilities",
            label="Known vulnerabilities (CVE)",
            domain="Information security",
            kind=CheckKind.NVD_LOOKUP,
            prompt_template="{subject}",
            scope_note="Reports publicly disclosed CVEs only. Absence of results means nothing has been publicly disclosed and logged -- not that the software is vulnerability-free.",
        ),
        ChecklistItem(
            key="maintenance_health",
            label="Maintenance & release activity",
            domain="Operational resilience",
            kind=CheckKind.WEB_RESEARCH,
            prompt_template="{subject} is actively maintained, with recent commits and releases in the last 6 months, and has more than one active maintainer.",
            scope_note="A real, checkable signal of abandonment risk. Doesn't guarantee future maintenance continues.",
        ),
        ChecklistItem(
            key="community_health",
            label="Community & support health",
            domain="Operational resilience",
            kind=CheckKind.WEB_RESEARCH,
            prompt_template="{subject} has an active user community (GitHub issues/discussions, Stack Overflow presence, or similar) where problems get answered.",
            scope_note="A proxy for how stuck you'd be if something breaks. Not a guarantee of support quality.",
        ),
        ChecklistItem(
            key="data_handling",
            label="Data handling posture",
            domain="Privacy & compliance",
            kind=CheckKind.WEB_RESEARCH,
            prompt_template="{subject} does not transmit usage data, telemetry, or user data to external servers by default without explicit opt-in.",
            scope_note="Based on published documentation/source code claims. Independent verification would require actually auditing network calls.",
        ),
        ChecklistItem(
            key="architecture_docs",
            label="Architecture & integration documentation",
            domain="Information security",
            kind=CheckKind.WEB_RESEARCH,
            prompt_template="{subject} has publicly documented architecture and integration requirements (dependencies, required permissions, network access needed).",
            scope_note="Confirms documentation exists and what it claims. Not an independent architecture review of undisclosed internals.",
        ),
    ),
)

SAAS_VENDOR = ChecklistTemplate(
    key="saas_vendor",
    label="SaaS Vendor / Third-Party Service",
    description="For adopting an external hosted service or commercial vendor.",
    items=(
        ChecklistItem(
            key="compliance_certifications",
            label="Compliance certifications claimed",
            domain="Privacy & compliance",
            kind=CheckKind.WEB_RESEARCH,
            prompt_template="{subject} publicly claims SOC 2, ISO 27001, or equivalent compliance certification.",
            scope_note="Confirms what the vendor claims publicly. Does NOT independently verify the certification is current/valid -- that requires checking with the certifying body directly.",
        ),
        ChecklistItem(
            key="known_vulnerabilities",
            label="Known vulnerabilities / breach history",
            domain="Information security",
            kind=CheckKind.NVD_LOOKUP,
            prompt_template="{subject}",
            scope_note="Reports publicly disclosed CVEs for the underlying product where applicable. Vendor-specific breach history (not always CVE-tagged) should be checked via the web-research items too.",
        ),
        ChecklistItem(
            key="data_residency",
            label="Data residency & handling policy",
            domain="Privacy & compliance",
            kind=CheckKind.WEB_RESEARCH,
            prompt_template="{subject} publishes a clear data residency and data handling policy stating where customer data is stored and processed.",
            scope_note="Based on the vendor's own published policy. Confirms the policy exists and what it states, not independent verification of actual practice.",
        ),
        ChecklistItem(
            key="pricing_model",
            label="Cost / pricing model",
            domain="Business & financial stability",
            kind=CheckKind.WEB_RESEARCH,
            prompt_template="{subject} has a publicly documented, predictable pricing model without hidden usage-based costs that could spike unexpectedly.",
            scope_note="Confirms published pricing terms. Real-world cost still depends on your actual usage pattern.",
        ),
        ChecklistItem(
            key="incident_history",
            label="Incident / outage history",
            domain="Operational resilience",
            kind=CheckKind.WEB_RESEARCH,
            prompt_template="{subject} has a public status page or has a track record of transparent incident communication during outages.",
            scope_note="A proxy for operational transparency. Doesn't guarantee reliability going forward.",
        ),
        ChecklistItem(
            key="integration_requirements",
            label="Integration & access requirements",
            domain="Information security",
            kind=CheckKind.WEB_RESEARCH,
            prompt_template="{subject} documents exactly what permissions, API scopes, or network access it requires to integrate.",
            scope_note="Confirms documentation exists and what it claims to need. Not independent verification of what it actually accesses.",
        ),
    ),
)

TEMPLATES: dict[str, ChecklistTemplate] = {
    OPEN_SOURCE_LIBRARY.key: OPEN_SOURCE_LIBRARY,
    SAAS_VENDOR.key: SAAS_VENDOR,
}
