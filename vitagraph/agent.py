import os
import logging
from typing import List, Dict, Optional
from .core.ingest_rxiv import fetch_rss_feed, download_pdf, extract_text_from_pdf
from .core.extract import extract_relationships
from .core.graph import get_neo4j_driver, insert_extraction_result
from .core.hypothesis import find_missing_links, evaluate_hypothesis, generate_markdown_report
from .config import config_manager

logger = logging.getLogger(__name__)

class ResearchOracle:
    """
    Autonomous agent that orchestrates the research pipeline for a specific topic.
    """
    def __init__(self, console=None):
        self.console = console
        self.config = config_manager.config
        self.driver = None

    def _log(self, message: str, style: str = "white"):
        if self.console:
            self.console.print(f"[{style}]{message}[/{style}]")
        else:
            logger.info(message)

    def run_topic_research(self, topic: str, limit: int = 3):
        """
        Executes the full research loop: Search -> Ingest -> Extract -> Graph -> Hypothesize.
        """
        self._log(f"🚀 Starting autonomous research on: [bold cyan]{topic}[/bold cyan]", "bold green")
        
        # 1. Search & Filter
        # For now, we use the aging feed and filter for the topic
        feed_url = "http://connect.biorxiv.org/biorxiv_xml.php?subject=aging"
        self._log(f"🔍 Searching preprints...")
        entries = fetch_rss_feed(feed_url)
        
        # Filter entries by topic keywords
        relevant_entries = [
            e for e in entries 
            if topic.lower() in e["title"].lower() or topic.lower() in e["summary"].lower()
        ]
        
        if not relevant_entries:
            self._log(f"⚠️ No direct matches found for '{topic}' in the latest aging feed. Using top results instead.", "yellow")
            relevant_entries = entries[:limit]
        else:
            self._log(f"✅ Found {len(relevant_entries)} relevant papers.")
            relevant_entries = relevant_entries[:limit]

        # 2. Ingest & Extract
        for entry in relevant_entries:
            title = entry["title"]
            doi = entry["doi"]
            link = entry["link"]
            
            self._log(f"\n📖 Processing: [italic]{title}[/italic]")
            
            clean_link = link.split('?')[0]
            pdf_url = clean_link + ".full.pdf" if not clean_link.endswith(".pdf") else clean_link
            safe_doi = doi.replace("/", "_") if doi else clean_link.split("/")[-1]
            save_path = os.path.join(self.config.output_dir, f"{safe_doi}.pdf")
            
            # Download
            if download_pdf(pdf_url, save_path):
                # Extract Text
                text = extract_text_from_pdf(save_path, title, allow_mock_fallback=True)
                if text:
                    # Extract Knowledge
                    self._log(f"🧠 Extracting biological relationships...")
                    result = extract_relationships(text)
                    self._log(f"✨ Found {len(result.relationships)} relationships.")
                    
                    # Update Graph
                    self._log(f"🧬 Updating Knowledge Graph...")
                    if not self.driver:
                        self.driver = get_neo4j_driver()
                    
                    if self.driver:
                        insert_extraction_result(self.driver, result)
                    else:
                        self._log("❌ Failed to connect to Neo4j. Skipping graph update.", "red")
            else:
                self._log(f"❌ Failed to download paper: {title}", "red")

        # 3. Hypothesize
        self._log("\n🧪 Searching for novel hypotheses based on new knowledge...", "bold magenta")
        if not self.driver:
            self.driver = get_neo4j_driver()
            
        if self.driver:
            links = find_missing_links(self.driver)
            if links:
                self._log(f"💡 Found {len(links)} potential discovery paths.")
                for i, link in enumerate(links[:3]): # Show top 3
                    self._log(f"\nEvaluating: {link['source']} ➔ {link['intermediate']} ➔ {link['target']}")
                    eval_result = evaluate_hypothesis(link)
                    if eval_result.is_plausible:
                        self._log(f"🔥 [bold green]PLAUSIBLE HYPOTHESIS FOUND![/bold green] (Novelty: {eval_result.novelty_score}/10)")
                        report_path = os.path.join("output/hypotheses", f"agent_{i+1}_{topic.replace(' ', '_')}.md")
                        generate_markdown_report(link, eval_result, report_path)
                        self._log(f"📝 Report saved: {report_path}", "dim")
            else:
                self._log("📭 No new transitive relationships found yet. Try more papers!", "yellow")
            
            self.driver.close()
            self.driver = None
        
        self._log("\n🏁 Research loop complete.", "bold green")
