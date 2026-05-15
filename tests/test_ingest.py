import pytest
from unittest.mock import patch, MagicMock
import os
from vitagraph.core.ingest_rxiv import fetch_rss_feed, download_pdf, extract_text_from_pdf

# Mock data for feedparser
class MockFeed:
    def __init__(self, entries, bozo=0, bozo_exception=None):
        self.entries = entries
        self.bozo = bozo
        self.bozo_exception = bozo_exception

@patch('vitagraph.core.ingest_rxiv.feedparser.parse')
def test_fetch_rss_feed_success(mock_parse):
    # Setup mock
    mock_entry = {
        "title": "Test Paper",
        "link": "http://example.com/paper1",
        "summary": "Abstract here",
        "published": "2023-01-01",
        "prism_doi": "10.1234/5678"
    }
    mock_parse.return_value = MockFeed([mock_entry])
    
    entries = fetch_rss_feed("http://fake-url.com")
    
    assert len(entries) == 1
    assert entries[0]["title"] == "Test Paper"
    assert entries[0]["doi"] == "10.1234/5678"

@patch('vitagraph.core.ingest_rxiv.feedparser.parse')
def test_fetch_rss_feed_bozo_error(mock_parse):
    mock_parse.return_value = MockFeed([], bozo=1, bozo_exception=Exception("Bad feed"))
    
    entries = fetch_rss_feed("http://fake-url.com")
    
    assert len(entries) == 0

@patch('vitagraph.core.ingest_rxiv.cloudscraper.create_scraper')
def test_download_pdf_success(mock_create_scraper, tmp_path):
    # Setup mock response
    mock_scraper = MagicMock()
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [b"pdf content chunks"]
    mock_response.raise_for_status.return_value = None
    mock_scraper.get.return_value = mock_response
    mock_create_scraper.return_value = mock_scraper
    
    save_path = tmp_path / "test.pdf"
    
    result = download_pdf("http://example.com/test.pdf", str(save_path))
    
    assert result is True
    assert os.path.exists(save_path)
    with open(save_path, "rb") as f:
        assert f.read() == b"pdf content chunks"

@patch('vitagraph.core.ingest_rxiv.cloudscraper.create_scraper')
def test_download_pdf_failure(mock_create_scraper, tmp_path):
    mock_scraper = MagicMock()
    mock_response = MagicMock()
    from requests.exceptions import RequestException
    mock_response.raise_for_status.side_effect = RequestException("Not found")
    mock_scraper.get.return_value = mock_response
    mock_create_scraper.return_value = mock_scraper
    
    save_path = tmp_path / "test.pdf"
    
    result = download_pdf("http://example.com/test.pdf", str(save_path))
    
    assert result is False
    assert not os.path.exists(save_path)

@patch('vitagraph.core.ingest_rxiv.fitz.open')
def test_extract_text_from_pdf_success(mock_fitz_open, tmp_path):
    # Create a dummy file so os.path.exists passes
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.write_text("dummy")
    
    # Setup PyMuPDF mock
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Extracted text content."
    # Make the doc act like an iterable of pages
    mock_doc.__iter__.return_value = [mock_page]
    # Handle context manager
    mock_doc.__enter__.return_value = mock_doc
    mock_fitz_open.return_value = mock_doc
    
    text = extract_text_from_pdf(str(pdf_path))
    
    assert text == "Extracted text content."

def test_extract_text_from_pdf_not_found(tmp_path):
    pdf_path = tmp_path / "non_existent.pdf"
    
    # Pass allow_mock_fallback=True to trigger the mock text return
    text = extract_text_from_pdf(str(pdf_path), allow_mock_fallback=True)
    
    assert text is not None
    assert "Mock text" in text
