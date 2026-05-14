# VitaGraph AI

> An autonomous pipeline that reads longevity preprints, builds a Neo4j Knowledge Graph of biological relationships, and generates novel hypotheses for the DeSci ecosystem.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Why This Exists

Longevity researchers spend countless hours parsing PDFs to find overlapping biological pathways. VitaGraph AI automates this literature review at scale. By pulling unstructured preprints, extracting strict biological relationships (e.g., *Compound X inhibits Pathway Y*), and storing them in a graph database, the system can mathematically identify "missing links" in current research and use an LLM to evaluate their plausibility.

## Quick Start

The quickest way to see VitaGraph AI in action is to run the hypothesis generator with dummy data in the graph.

```bash
# 1. Export your API key
export GEMINI_API_KEY="your-api-key"

# 2. Run the hypothesis evaluation script
python hypothesis.py
```

This will query the Neo4j database for transitive relationships (A -> B -> C) without a direct link (A -> C), ask the LLM to evaluate the missing link, and output a detailed Markdown report in the `output/` directory.

## Installation

**Prerequisites**: 
- Python 3.10+
- A running instance of Neo4j (local or AuraDB)
- A Google Gemini API key

```bash
# 1. Clone the repository
git clone https://github.com/qualitymaterial/VitaGraph-AI.git
cd VitaGraph-AI

# 2. Set up a virtual environment
python -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

### Configuration

Set the following environment variables to configure your pipeline:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | `None` | Required. Your Google Gemini API Key for LLM extraction and evaluation. |
| `NEO4J_URI` | `bolt://localhost:7687` | Connection URI for your Neo4j database. |
| `NEO4J_USER` | `neo4j` | Username for Neo4j authentication. |
| `NEO4J_PASSWORD` | `password` | Password for Neo4j authentication. |

## Usage

### 1. Ingesting Papers
Fetch the latest preprints from bioRxiv or medRxiv RSS feeds, download the PDFs, and extract the text.

```bash
python ingest_rxiv.py --feed-url "http://connect.biorxiv.org/biorxiv_xml.php?subject=aging" --limit 5
```

> **Warning**: BioRxiv actively blocks automated scrapers with Cloudflare 403 errors. For local testing without an enterprise proxy, use the `--allow-mock-fallback` flag to inject sample text and continue the pipeline.

### 2. Extracting & Storing Knowledge
The LLM engine (`extract.py`) processes the text, strictly mapping findings to Pydantic schemas defined in `schemas.py`. The graph engine (`graph.py`) then uses Cypher `MERGE` statements to safely insert these into your Neo4j database without duplication.

*Note: In the current prototype, extraction and graph ingestion must be wired manually or run via test scripts.*

### 3. Generating Hypotheses
Run the hypothesis engine to discover new biological targets:

```bash
python hypothesis.py
```

## Architecture

1. **Source Monitor** (`ingest_rxiv.py`): Polls RSS feeds and extracts PDF text.
2. **Extraction Engine** (`extract.py`): Maps unstructured text to strict Enums (`EntityType`, `RelationshipType`) utilizing Gemini 2.5.
3. **Graph Integration** (`graph.py`): Stores entities and relationships as attributed edges in Neo4j (including exact textual `evidence` and `confidence` scores).
4. **Hypothesis Synthesizer** (`hypothesis.py`): Queries Neo4j for structural gaps and generates Markdown reports evaluating their biological plausibility.

## Testing

VitaGraph AI uses `pytest` for unit testing, including comprehensive mocks for network requests and LLM calls.

```bash
pytest tests/
```

## Contributing

We welcome contributions to the VitaGraph AI ecosystem. Please ensure all new features are accompanied by passing `pytest` unit tests and strictly adhere to the Pydantic schemas.

## License

MIT © VitaDAO Ecosystem
