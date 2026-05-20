# VitaGraph AI — Standard Operating Procedure

This document covers everything needed to install, configure, and operate VitaGraph AI for biological discovery research. Follow it sequentially on first run; use it as a reference thereafter.

---

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Project developed on 3.14 |
| Neo4j | 5.x | Local via Neo4j Desktop or Neo4j Aura (cloud) |
| Google Gemini API Key | — | `gemini-2.5-flash` model access required |
| Git | any | For cloning the repo |

---

## 2. Installation

```bash
# Clone the repo
git clone https://github.com/qualitymaterial/VitaGraph-AI.git
cd VitaGraph-AI

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# Install the package in editable mode
pip install -e .
```

Verify the install:

```bash
vitagraph --help
```

---

## 3. First-Time Configuration

Run the interactive setup wizard:

```bash
vitagraph setup
```

You will be prompted for:

1. **Google Gemini API Key** — used for entity/relationship extraction from PDFs
2. **Neo4j URI** — default `bolt://localhost:7687` for local, or your Aura connection string
3. **Neo4j Username** — default `neo4j`
4. **Neo4j Password** — set during Neo4j installation

Configuration is saved to `~/.vitagraph/config.json`. Credentials are stored locally only and never committed to the repo.

**Alternatively**, set environment variables to override the config file:

```bash
export GEMINI_API_KEY="your-key"
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"
```

### Verify setup

```bash
vitagraph status
```

Expected output:
```
 Check            Result
 Gemini API Key   ✓ Configured
 Neo4j            ✓ Connected (bolt://localhost:7687)
 Output dir       ✓ ./data/pdfs
```

Do not proceed until all three checks pass.

---

## 4. Standard Research Workflow

This is the repeatable session loop. Run it whenever you want to expand the knowledge graph on a topic.

### Step 1 — Enter the Command Deck

```bash
vitagraph
```

You will see the Command Deck prompt: `vita > `

Use `↑` / `↓` arrow keys to navigate command history.

---

### Step 2 — Run a research session

```
vita > /research <topic>
```

**Examples:**
```
/research rapamycin mTOR aging
/research NAD+ metabolism longevity
/research senolytics senescent cells
/research AMPK metformin lifespan
```

**What happens automatically:**
1. **Hybrid search** — bioRxiv (last 90 days of preprints) + PubMed (historical archive) are queried in parallel
2. **Deduplication** — results are merged and deduplicated by DOI
3. **PDF ingestion** — papers are downloaded to `./data/pdfs/`
4. **Extraction** — Gemini 2.5 Flash extracts entities, relationships, and verbatim evidence from each paper
5. **Graph update** — entities and relationships are written to Neo4j with DOI provenance

A live dashboard shows progress, entities discovered, and relationships found in real time.

**Tip:** Start with 2–3 focused topics before running hypothesis discovery. The more papers in the graph, the better the hypothesis quality.

---

### Step 3 — Normalize the graph (run after every session)

```
vita > /normalize
```

This merges duplicate entity nodes created by name variants across papers. For example, `mTOR` (from one paper) and `MTOR` (from another) get collapsed into a single canonical node, with the variant stored as a synonym.

**Always run normalize after each research session.** It is safe to run multiple times — if the graph is already clean, it reports zero merges and exits.

Expected output:
```
Entity count before: 142
Scanning for duplicate entities...
✓ Merged 7 duplicate node(s).  142 → 135 entities
```

---

### Step 4 — Review your library

```
vita > /papers       # list all ingested papers (most recent first)
vita > /entities     # list all discovered entities
```

From the CLI directly:
```bash
vitagraph papers --limit 20
vitagraph entities --type Compound
vitagraph entities --type Target
```

---

### Step 5 — Run hypothesis discovery

```
vita > /hypothesis
```

The hypothesis engine scans the graph for **transitive links** — paths where:
- Fact A: `Entity X → [rel] → Entity Y` exists
- Fact B: `Entity Y → [rel] → Entity Z` exists
- But: `Entity X → Entity Z` has **no direct edge**

Each discovered path is evaluated and plausible ones are written as Markdown reports to `output/hypotheses/`.

**Tip:** Run hypothesis discovery after every 3–5 research sessions as the graph grows.

---

### Step 6 — Review hypothesis reports

Reports are saved to:
```
output/hypotheses/agent_1_<topic>.md
output/hypotheses/agent_2_<topic>.md
...
```

Each report contains:
- The proposed indirect relationship
- The two-step evidence chain with verbatim quotes from source papers
- Source DOIs for verification

---

## 5. Full CLI Reference

All commands are available both in the interactive shell and as direct CLI subcommands.

| Shell Command | CLI Equivalent | Description |
|---|---|---|
| `/research <topic>` | `vitagraph research "<topic>"` | Run full autonomous research loop |
| `/papers` | `vitagraph papers [--limit N]` | List ingested papers |
| `/entities` | `vitagraph entities [--type T] [--limit N]` | List discovered entities |
| `/hypothesis` | `vitagraph hypothesis [--topic T]` | Run transitive link discovery |
| `/normalize` | `vitagraph normalize` | Merge duplicate entity nodes |
| `/status` | `vitagraph status` | Check config and connection health |
| `/setup` | `vitagraph setup` | Interactive configuration wizard |
| `/help` or `/?` | — | Show command reference |
| `/exit` or `/q` | — | Exit the Command Deck |

**Shortcuts inside the shell:**
`/r` → `/research` · `/p` → `/papers` · `/e` → `/entities` · `/h` → `/hypothesis` · `/n` → `/normalize` · `/s` → `/setup` · `/q` → `/exit`

**Direct ingestion commands** (for scripting or manual workflows):
```bash
vitagraph ingest --topic "senolytics" --days 30 --limit 10
vitagraph extract path/to/paper.pdf
vitagraph graph path/to/paper.pdf      # extract + insert into Neo4j
```

---

## 6. Neo4j Graph Queries

Open the Neo4j Browser at `http://localhost:7474` to run these directly.

**Count everything:**
```cypher
MATCH (e:Entity) RETURN count(e) AS entities
MATCH ()-[r]->() RETURN count(r) AS relationships
MATCH (p:Paper) RETURN count(p) AS papers
```

**Find all compounds that inhibit a specific target:**
```cypher
MATCH (c:Entity {type: 'Compound'})-[:INHIBITS]->(t:Entity {name: 'MTOR'})
RETURN c.name, c.synonyms
```

**Explore everything connected to an entity:**
```cypher
MATCH (e:Entity {name: 'rapamycin'})-[r]-(other:Entity)
RETURN e.name, type(r), other.name, other.type
ORDER BY type(r)
```

**Find the most connected entities (hubs):**
```cypher
MATCH (e:Entity)-[r]-()
RETURN e.name, e.type, count(r) AS connections
ORDER BY connections DESC
LIMIT 20
```

**Trace a relationship back to its source paper:**
```cypher
MATCH (p:Paper)-[:MENTIONS]->(r)-[*0..1]-(e:Entity)
WHERE p.doi = '10.1234/example'
RETURN p.title, p.doi, type(r), e.name
```

**Check for any remaining duplicate entities (should be 0 after normalize):**
```cypher
MATCH (a:Entity), (b:Entity)
WHERE id(a) < id(b) AND toLower(trim(a.name)) = toLower(trim(b.name))
RETURN a.name, b.name
```

---

## 7. Maintenance

| Task | When | Command |
|---|---|---|
| Normalize graph | After every research session | `vitagraph normalize` |
| Check graph health | Weekly or before hypothesis runs | `vitagraph status` |
| Review entity count growth | Periodically | `vitagraph entities --limit 100` |

**Output directory structure:**
```
data/
  pdfs/           ← downloaded papers (gitignored)
output/
  hypotheses/     ← generated discovery reports
~/.vitagraph/
  config.json     ← credentials and settings (never commit)
```

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `✗ Cannot connect` on status | Neo4j not running | Start Neo4j Desktop or check Aura console |
| `✗ Missing` Gemini key | Key not configured | Run `vitagraph setup` |
| No papers found for topic | Keywords too narrow | Use broader terms; try synonyms (e.g., "aging" not "ageing") |
| PDF download failures | Paywall or dead link | Expected — the system skips and continues. PubMed papers are often paywalled. |
| `429` errors from PubMed | Rate limit hit | Wait 30–60 seconds, then retry. PubMed allows ~3 req/sec. |
| Duplicate entities after normalize | Synonym-based duplicates | Run `/normalize` again — it loops until clean |
| Gemini returns empty extraction | Paper text too short or non-English | Check the PDF opened correctly; skip non-English papers |
| `NameError` or import errors | Wrong Python environment | Ensure `venv` is activated: `source venv/bin/activate` |
