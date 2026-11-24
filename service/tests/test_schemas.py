import pytest
from pydantic import ValidationError

from docflow.extraction import api_schema, load_schema
from docflow.config import REPO
from docflow.schemas import Fields, business_checks


@pytest.mark.parametrize("raw,expected", [("1 234,56", 1234.56), ("1,234.56", 1234.56), ("15,5", 15.5),
                                          (2015.931, 2015.93), (None, None)])
def test_amount_normalisation(raw, expected):
    assert Fields(doc_type="receipt", total_amount=raw).total_amount == expected


def test_text_and_number_cleanup():
    f = Fields(doc_type="invoice", counterparty="  Gamma   Telekom ", document_number="№ FV/2025/03/1", currency="pln")
    assert f.counterparty == "Gamma Telekom" and f.document_number == "FV/2025/03/1" and f.currency == "PLN"


def test_bad_currency_and_date_rejected():
    with pytest.raises(ValidationError):
        Fields(doc_type="invoice", currency="zł")
    with pytest.raises(ValidationError):
        Fields(doc_type="invoice", issue_date="2025-02-30")


def test_business_checks():
    ok = Fields(doc_type="invoice", issue_date="2025-01-10", due_date="2025-01-24", currency="EUR", total_amount=10)
    assert business_checks(ok) == []
    bad = Fields(doc_type="receipt", issue_date="2025-01-10", due_date="2025-01-01", total_amount=None)
    issues = business_checks(bad)
    assert "due_date set on a receipt" in issues and "due_date is before issue_date" in issues
    assert "receipt without total_amount" in issues


def test_api_schema_is_strict_compatible():
    s = api_schema(load_schema(REPO / "schema.json"))
    text = str(s)
    assert "pattern" not in text and "minimum" not in text and "maximum" not in text
    assert s["properties"]["issue_date"]["anyOf"][0] == {"type": "string", "format": "date"}
    assert s["additionalProperties"] is False
