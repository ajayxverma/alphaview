from alphaview_crawler.deep_read import reference_document


def test_undated_pricing_reference_preserves_text_beyond_old_limit():
    text = "Background information about an invoice workflow. " * 160 + "Invoice pricing is $19 per month."
    body = f"<html><head><title>Invoice pricing</title></head><body><article><h1>Pricing</h1><p>{text}</p></article></body></html>".encode()
    document = reference_document(body, "https://example.com/pricing", {"language": "en"})
    assert document and document["document_type"] == "pricing"
    assert document["published_at"] is None
    assert len(document["text"]) > 4000 and "$19" in document["text"]


def test_login_and_captcha_pages_are_not_evidence():
    for title in ("Sign in", "Verify you are human", "CAPTCHA"):
        body = f"<html><title>{title}</title><body><p>{'Please verify your identity. ' * 20}</p></body></html>".encode()
        assert reference_document(body, "https://example.com/private", {}) is None