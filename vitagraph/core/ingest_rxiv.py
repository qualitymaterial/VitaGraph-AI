import feedparser
import requests
import fitz  # PyMuPDF
import os
import argparse
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_biorxiv_api(topic: str = "", days: int = 7) -> List[Dict]:
    """
    Fetches papers from the official bioRxiv API for the given number of days.
    """
    import datetime
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=days)
    
    url = f"https://api.biorxiv.org/details/biorxiv/{start_date}/{today}/0"
    logger.info(f"Fetching papers from bioRxiv API: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        collection = data.get("collection", [])
    except Exception as e:
        logger.error(f"Failed to fetch from bioRxiv API: {e}")
        return []

    entries = []
    for paper in collection:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        
        # Simple keyword filtering if a topic is provided
        if topic and (topic.lower() not in title.lower() and topic.lower() not in abstract.lower()):
            continue
            
        doi = paper.get("doi", "")
        # Construct link from DOI
        link = f"https://www.biorxiv.org/content/{doi}"
        
        entries.append({
            "title": title,
            "link": link,
            "summary": abstract,
            "doi": doi
        })
        
    logger.info(f"Successfully retrieved {len(entries)} papers from API.")
    return entries

import cloudscraper

def download_pdf(url: str, save_path: str) -> bool:
    """
    Downloads a PDF from a given URL and saves it to the specified path.
    Returns True if successful, False otherwise.
    """
    logger.info(f"Downloading PDF from: {url} to {save_path}")
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Successfully downloaded PDF to {save_path}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download PDF from {url}: {e}")
        return False
    except IOError as e:
        logger.error(f"Failed to save PDF to {save_path}: {e}")
        return False

def extract_text_from_pdf(pdf_path: str, fallback_title: str = "", allow_mock_fallback: bool = False) -> Optional[str]:
    """
    Extracts text from a given PDF file using PyMuPDF.
    If the file is not found and allow_mock_fallback is True, returns fallback mock text for testing.
    Otherwise, raises a FileNotFoundError or logs a critical error.
    """
    logger.info(f"Extracting text from: {pdf_path}")
    if not os.path.exists(pdf_path):
        if allow_mock_fallback:
            logger.warning(f"File not found: {pdf_path}. Returning mock text for pipeline testing.")
            return f"Mock text for {fallback_title}. This is placeholder text because the PDF could not be downloaded due to Cloudflare restrictions on bioRxiv."
        else:
            logger.error(f"File not found: {pdf_path}. Pipeline blocked. Use --allow-mock-fallback for testing.")
            return None
        
    try:
        text = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
        logger.info(f"Successfully extracted {len(text)} characters from {pdf_path}")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from {pdf_path}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Ingest preprints from bioRxiv/medRxiv RSS feeds.")
    parser.add_argument("--feed-url", type=str, default="http://connect.biorxiv.org/biorxiv_xml.php?subject=aging", help="The RSS feed URL to fetch.")
    parser.add_argument("--output-dir", type=str, default="./data/pdfs", help="Directory to save downloaded PDFs.")
    parser.add_argument("--limit", type=int, default=5, help="Limit the number of papers to process.")
    parser.add_argument("--allow-mock-fallback", action="store_true", help="Allow using mock text if PDF download fails.")
    
    args = parser.parse_args()
    
    entries = fetch_rss_feed(args.feed_url)
    
    if not entries:
        logger.warning("No entries found or failed to fetch feed.")
        return

    processed = 0
    for entry in entries[:args.limit]:
        title = entry["title"]
        doi = entry["doi"]
        link = entry["link"]
        logger.info(f"Processing: {title} (DOI: {doi})")
        
        # BioRxiv specific logic: constructing PDF link from article link
        # biorxiv link format: https://www.biorxiv.org/content/10.1101/2023.12.31.573771v1
        # PDF format: https://www.biorxiv.org/content/10.1101/2023.12.31.573771v1.full.pdf
        clean_link = link.split('?')[0]
        pdf_url = clean_link + ".full.pdf" if not clean_link.endswith(".pdf") else clean_link
        
        # Generate a safe filename
        safe_doi = doi.replace("/", "_") if doi else clean_link.split("/")[-1]
        filename = f"{safe_doi}.pdf"
        save_path = os.path.join(args.output_dir, filename)
        
        if download_pdf(pdf_url, save_path):
            text = extract_text_from_pdf(save_path, title, allow_mock_fallback=args.allow_mock_fallback)
        else:
            text = extract_text_from_pdf(save_path, title, allow_mock_fallback=args.allow_mock_fallback)
            
        if text:
            logger.info(f"First 100 characters of text: {text[:100]}...")
            # Note: In Phase 2, this text will be passed to the LLM extraction engine.
        
        processed += 1
        print("-" * 40)
        
    logger.info(f"Finished processing {processed} papers.")

if __name__ == "__main__":
    main()
