import os
import logging
from typing import List, Dict, Optional
from .core.ingest_rxiv import fetch_biorxiv_api, download_pdf, extract_text_from_pdf
from .core.ingest_scholar import search_deep_archive
from .core.extract import extract_relationships
from .core.graph import get_neo4j_driver, insert_extraction_result
from .core.hypothesis import find_missing_links, evaluate_hypothesis, generate_markdown_report
from .config import config_manager
from .reports import ResearchDashboard
from rich.live import Live

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
        Executes the full research loop with a live dashboard.
        """
        dashboard = ResearchDashboard()
        
        with Live(dashboard.render(topic, "Initializing"), refresh_per_second=4) as live:
            dashboard.logs.append(f"🚀 Starting autonomous research on: {topic}")
            
            # Fetch initial stats
            if not self.driver:
                self.driver = get_neo4j_driver()
            if self.driver:
                with self.driver.session() as session:
                    res = session.run("MATCH (n:Entity) RETURN count(n) as c")
                    dashboard.stats["entities"] = res.single()["c"]
                    res = session.run("MATCH ()-[r]->() RETURN count(r) as c")
                    dashboard.stats["relations"] = res.single()["c"]
                    res = session.run("MATCH (p:Paper) RETURN count(p) as c")
                    dashboard.stats["papers"] = res.single()["c"]

            live.update(dashboard.render(topic, "Searching"))
            
            # 1. Search & Filter
            dashboard.logs.append("🔍 Checking recent preprints (bioRxiv)...")
            recent_entries = fetch_biorxiv_api(topic=topic, days=90)
            
            dashboard.logs.append("🌐 Deep Searching archive (PubMed)...")
            historical_entries = search_deep_archive(topic=topic, limit=limit)
            
            # Combine and deduplicate by DOI
            all_entries = {e["doi"]: e for e in (recent_entries + historical_entries) if e.get("doi")}.values()
            relevant_entries = list(all_entries)[:limit]
            
            if not relevant_entries:
                dashboard.logs.append(f"⚠️ No papers found for '{topic}' anywhere.")
                live.update(dashboard.render(topic, "Completed"))
                return
                
            dashboard.logs.append(f"✅ Found {len(relevant_entries)} relevant papers.")
            relevant_entries = relevant_entries[:limit]

            # 2. Ingest & Extract
            for i, entry in enumerate(relevant_entries):
                title = entry["title"]
                dashboard.current_paper = title
                dashboard.progress_value = int((i / len(relevant_entries)) * 100)
                live.update(dashboard.render(topic, "Processing Papers"))
                
                doi = entry["doi"]
                link = entry["link"]
                
                dashboard.logs.append(f"📖 Reading: {title[:50]}...")
                
                clean_link = link.split('?')[0]
                pdf_url = clean_link + ".full.pdf" if not clean_link.endswith(".pdf") else clean_link
                safe_doi = doi.replace("/", "_") if doi else clean_link.split("/")[-1]
                save_path = os.path.join(self.config.output_dir, f"{safe_doi}.pdf")
                
                if download_pdf(pdf_url, save_path):
                    text = extract_text_from_pdf(save_path, title)
                    if text:
                        dashboard.logs.append("🧠 Extracting knowledge...")
                        result = extract_relationships(
                            text,
                            paper_title=title,
                            doi=doi,
                            abstract=entry.get("summary", ""),
                            source_url=entry.get("link", ""),
                        )
                        
                        # Show Entities in the Feed immediately
                        if result.entities:
                            for ent in result.entities[:2]: # Show a couple of entities
                                dashboard.discoveries.append({"name": ent.name, "type": ent.entity_type})
                        
                        if result.relationships:
                            dashboard.logs.append(f"✨ Found {len(result.relationships)} facts.")
                            for rel in result.relationships[:2]:
                                dashboard.discoveries.append({"name": f"{rel.source_entity} → {rel.target_entity}", "type": rel.relationship_type})
                            
                            # Update Graph
                            dashboard.logs.append("🧬 Updating Knowledge Graph...")
                            if not self.driver:
                                self.driver = get_neo4j_driver()
                            
                            if self.driver:
                                insert_extraction_result(self.driver, result)
                                # Update stats after insertion
                                with self.driver.session() as session:
                                    res = session.run("MATCH (n:Entity) RETURN count(n) as c")
                                    dashboard.stats["entities"] = res.single()["c"]
                                    res = session.run("MATCH ()-[r]->() RETURN count(r) as c")
                                    dashboard.stats["relations"] = res.single()["c"]
                                    res = session.run("MATCH (p:Paper) RETURN count(p) as c")
                                    dashboard.stats["papers"] = res.single()["c"]
                        else:
                            dashboard.logs.append("📭 No clear relationships found.")
                    else:
                        dashboard.logs.append(f"📭 No text found in {title[:30]}")
                else:
                    dashboard.logs.append(f"❌ Failed to download: {title[:30]}")
                
                live.update(dashboard.render(topic, "Processing Papers"))

            # 3. Hypothesize
            dashboard.progress_value = 100
            dashboard.current_paper = "Discovery Phase"
            live.update(dashboard.render(topic, "Synthesizing Hypotheses"))
            dashboard.logs.append("🧪 Searching for novel hypotheses...")
            
            if not self.driver:
                self.driver = get_neo4j_driver()
                
            if self.driver:
                links = find_missing_links(self.driver)
                if links:
                    dashboard.logs.append(f"💡 Found {len(links)} discovery paths!")
                    for i, link in enumerate(links[:3]):
                        dashboard.logs.append(f"Evaluating: {link['source']} ➔ {link['target']}")
                        eval_result = evaluate_hypothesis(link)
                        if eval_result.is_plausible:
                            dashboard.logs.append("🔥 PLAUSIBLE HYPOTHESIS FOUND!")
                            dashboard.discoveries.append({"name": f"NEW: {link['source']} ➔ {link['target']}", "type": "Hypothesis"})
                            hyp_topic = f"{link['source']} to {link['target']}"
                            report_content = generate_markdown_report(hyp_topic, [link])
                            hyp_dir = os.path.join(self.config.output_dir, "hypotheses")
                            os.makedirs(hyp_dir, exist_ok=True)
                            report_path = os.path.join(hyp_dir, f"agent_{i+1}_{topic.replace(' ', '_')}.md")
                            with open(report_path, "w") as f:
                                f.write(report_content)
                else:
                    dashboard.logs.append("📭 No new transitive links found yet.")
                
                self.driver.close()
                self.driver = None
            
            live.update(dashboard.render(topic, "Complete"))
            dashboard.logs.append("🏁 Research loop complete.")
