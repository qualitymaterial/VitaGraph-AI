# ◈ VitaGraph AI: Research Guide

Welcome to the definitive guide for performing biological discovery with VitaGraph AI. This tool is designed to move at the speed of thought, bridging the gap between raw data and scientific insight.

---

## 🛠️ The Command Deck

The **Command Deck** (`vitagraph shell`) is your central hub for interaction. 

### **The Slash Menu**
Type `/` inside the shell at any time to see a popup menu of available actions.

### **Shortcuts**
- `/r "topic"` — Fast-track to research.
- `/p` — Browse your library.
- `/q` — Exit safely.

---

## 🧬 Performing Deep Research

When you run a research loop, the **Oracle** performs a three-stage operation:

1.  **Scanning (Hybrid Search)**: 
    - It checks **bioRxiv** for preprints from the last 90 days.
    - It deep-searches the **PubMed** archive for historical peer-reviewed literature.
2.  **Ingestion & Extraction**: 
    - Papers are downloaded, converted to text, and fed into the Gemini-2.5-Flash reasoning model.
    - Entities (Proteins, Compounds, Diseases) and standardized Relationships (Upregulates, Inhibits) are extracted.
3.  **Graph Synthesis**: 
    - Data is committed to your Neo4j instance.
    - Facts are attributed to their source DOI and Paper Title.

---

## 🔬 Discovery & Hypotheses

Once you have a baseline of knowledge, you can use the **Hypothesis Engine**:

```bash
vitagraph hypothesis
```

The agent will scan your *entire* database looking for "Transitive Links":
- **Fact A**: Compound X → Inhibits → Protein Y
- **Fact B**: Protein Y → Activates → Pathway Z
- **Hypothesis**: Compound X → *potentially* → Inhibits → Pathway Z

These findings are exported to your local `data/reports` directory as formatted Markdown files.

---

## 📚 Managing Your Library

As your graph grows, you can manage it using specialized lookup commands:

### **List Ingested Papers**
See everything you've read so far:
```bash
vitagraph papers
```

### **Explore Discovered Entities**
Search your knowledge base for specific types of actors:
```bash
vitagraph entities --type "Target"
```

---

## ⚠️ Troubleshooting

- **No Papers Found?**: Try broadening your topic. Instead of "Magnesium," try "Magnesium Ion Channel Aging."
- **Rate Limits**: If you see "429" errors, slow down your research loops. PubMed has fair-use limits.
- **Neo4j Connection**: Ensure your database is active in the Neo4j Aura console.

---
*Happy Discovering.*
