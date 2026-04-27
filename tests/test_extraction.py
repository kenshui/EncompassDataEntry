from encompass_ai_agent.extraction import RegexFallbackExtractor


def test_regex_extractor_finds_requested_fee_fields() -> None:
    text = """
    Processing Fee: $995.00
    Transfer Tax City - 125.50
    Prepaid Interest Rate: 6.875%
    Loan Amount $375,000.00
    """

    fields = RegexFallbackExtractor().extract(text)

    assert fields["processing_fee"] == "995.00"
    assert fields["transfer_tax_city"] == "125.50"
    assert fields["prepaid_interest_rate"] == "6.875%"
    assert fields["loan_amount"] == "375000.00"
