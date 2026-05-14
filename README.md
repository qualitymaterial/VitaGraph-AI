# VitaDAO Hypothesis Generator

A pipeline for automating the discovery of novel biological relationships in longevity research. It ingests preprints, extracts entities and relationships using LLMs, builds a Neo4j Knowledge Graph, and surfaces "missing links" as novel hypotheses.

## Features
- **Ingestion**: Fetches PDFs from bioRxiv/medRxiv RSS feeds.
- **Extraction**: Uses Gemini 2.5 to extract structured biological relationships mapped strictly to Pydantic models.
- **Knowledge Graph**: Stores verified entity relationships in a Neo4j graph database.
- **Hypothesis Generation**: Queries graph for transitive relationships (A->B, B->C) lacking direct connections (A->C) and prompts the LLM to evaluate plausibility.

## Setup
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Set your environment variables:
   ```bash
   export GEMINI_API_KEY="your-api-key"
   export NEO4J_URI="bolt://localhost:7687"
   export NEO4J_USER="neo4j"
   export NEO4J_PASSWORD="password"
   ```

## Usage
Run the pipeline to test the hypothesis generation on dummy data:
```bash
python hypothesis.py
```

Run tests:
```bash
pytest tests/
```

## Disclaimer
The bioRxiv ingestion pipeline is actively blocked by Cloudflare in automated environments. To test the pipeline locally, use `--allow-mock-fallback`. For production, a specialized scraping service is required.
