from __future__ import annotations

from apps.contract_intelligence.domain.enums import DocumentType


REQUIRED_BID_REVIEW_DOCUMENTS: tuple[DocumentType, ...] = (
    DocumentType.PRIME_CONTRACT,
    DocumentType.GENERAL_CONDITIONS,
    DocumentType.INSURANCE_REQUIREMENTS,
)


KEYWORD_HINTS: tuple[tuple[DocumentType, tuple[str, ...]], ...] = (
    (DocumentType.INSURANCE_REQUIREMENTS, ("insurance", "coverage", "endorsement")),
    (DocumentType.GENERAL_CONDITIONS, ("general conditions", "aia a201", "gc")),
    (DocumentType.SPECIAL_PROVISIONS, ("special provisions", "supplementary conditions")),
    (DocumentType.ADDENDUM, ("addendum", "addenda")),
    (DocumentType.FUNDING_DOCUMENT, ("funding", "grant", "federal aid", "state aid")),
    (DocumentType.PROCUREMENT_DOCUMENT, ("rfp", "ifb", "bid package", "procurement")),
    (DocumentType.PRIME_CONTRACT, ("prime contract", "agreement", "owner contract", "contract")),
)


def classify_document(filename: str) -> DocumentType:
    normalized = filename.lower().replace("_", " ").replace("-", " ").strip()
    for document_type, keywords in KEYWORD_HINTS:
        if any(keyword in normalized for keyword in keywords):
            return document_type
    return DocumentType.OTHER


def missing_required_documents(document_types: list[DocumentType | str]) -> list[DocumentType]:
    seen = {DocumentType(item) if isinstance(item, str) else item for item in document_types}
    return [item for item in REQUIRED_BID_REVIEW_DOCUMENTS if item not in seen]
