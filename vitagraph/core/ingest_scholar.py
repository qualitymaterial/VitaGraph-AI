import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def search_deep_archive(topic: str, limit: int = 5) -> List[Dict]:
    """
    Searches PubMed for historical papers matching the topic using NIH Entrez API.
    """
    # 1. Search for IDs
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": topic,
        "retmax": limit,
        "retmode": "json"
    }
    
    logger.info(f"Deep Searching PubMed for: {topic}")
    
    try:
        search_res = requests.get(search_url, params=search_params, timeout=30)
        search_res.raise_for_status()
        id_list = search_res.json().get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            return []
            
        # 2. Fetch details for these IDs
        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        summary_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "json"
        }
        
        summary_res = requests.get(summary_url, params=summary_params, timeout=30)
        summary_res.raise_for_status()
        summaries = summary_res.json().get("result", {})
        
        entries = []
        for uid in id_list:
            paper = summaries.get(uid, {})
            title = paper.get("title", "Unknown Title")
            
            # Find DOI
            doi = ""
            for article_id in paper.get("articleids", []):
                if article_id.get("idtype") == "doi":
                    doi = article_id.get("value")
                    break
            
            link = f"https://pubmed.ncbi.nlm.nih.gov/{uid}/"
            
            entries.append({
                "title": title,
                "link": link,
                "summary": paper.get("source", ""), # PubMed summary is often short, but the link provides full text
                "doi": doi,
                "uid": uid
            })
            
        logger.info(f"Successfully found {len(entries)} papers on PubMed.")
        return entries
        
    except Exception as e:
        logger.error(f"Failed to search PubMed: {e}")
        return []
