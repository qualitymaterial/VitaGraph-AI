# ◈ VitaGraph AI

**The Autonomous Biological Discovery Engine.**

VitaGraph AI is a high-fidelity research agent designed to transform raw scientific literature into a structured, navigable Knowledge Graph. Built for longevity researchers and biological engineers, it uses a hybrid discovery pipeline to find, read, and cross-reference research across the entire history of science.

![VitaGraph Dashboard Preview](https://via.placeholder.com/800x400/2a2a2a/magenta?text=VITAGRAPH+AI+ORACLE+DASHBOARD)

## ⚡ Key Capabilities

- **Hybrid Discovery Pipeline**: Scans the latest preprints via **bioRxiv** and deep-dives into millions of historical papers via **PubMed**.
- **Claude-Grade CLI**: A premium, split-view terminal dashboard with real-time analytics, knowledge streams, and autonomous reasoning logs.
- **Interactive Command Deck**: A high-speed shell environment with slash-commands (`/r`, `/p`, `/h`) and autocomplete menus.
- **Neo4j Provenance Graph**: Every extracted relationship is permanently linked to its source **Paper node** and **DOI**, creating a verifiable audit trail of biological knowledge.
- **Autonomous Hypothesizer**: Automatically identifies "missing links" (transitive relationships) in your graph to propose novel research directions.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -e .

# 2. Configure your Oracle (Gemini + Neo4j)
vitagraph setup

# 3. Enter the Command Deck
vitagraph shell
```

## 📟 Slash Commands (The Command Deck)

Inside the `vitagraph shell`, use these high-speed shortcuts:

| Command | Shortcut | Action |
| :--- | :--- | :--- |
| `/research <topic>` | `/r` | Start an autonomous deep-research loop |
| `/papers` | `/p` | View your ingested research library |
| `/entities` | `/e` | List discovered biological actors (genes, proteins, etc.) |
| `/hypothesis` | `/h` | Trigger the discovery of novel biological links |
| `/help` | `/?` | Open the command menu |

## 🧪 Documentation

For detailed guides on performing advanced research and managing your graph, see the **[Research Guide](RESEARCH_GUIDE.md)**.

---
*Created by the Advanced Agentic Coding team at Google Deepmind.*
