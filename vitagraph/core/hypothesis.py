import logging
from typing import List, Dict, Tuple
from datetime import datetime
from google import genai
from google.genai import types
from .schemas import HypothesisEvaluation, NoveltyLevel
from ..config import config_manager

logger = logging.getLogger(__name__)

EVAL_PROMPT = """
You are an expert longevity biologist with deep knowledge of signaling pathways,
compounds, genes, and their interactions in the context of aging and lifespan.

You are evaluating a proposed indirect biological relationship derived from graph
traversal of scientific literature. The relationship was NOT found directly in any
paper — it is a hypothesis inferred from two separate established facts.

Proposed indirect relationship:
  {source}  →  (via {intermediate})  →  {target}

Evidence chain:
  Step 1: "{evidence1}"
  Step 2: "{evidence2}"

Evaluate this hypothesis carefully:

- is_plausible: Is the proposed indirect relationship biologically coherent?
  Consider whether the mechanism of Step 1 and Step 2 can physically connect.
  Return false if the entities are unrelated domains, the logic is circular,
  or the intermediate step breaks the causal chain.

- confidence: Score 0.0–1.0 based on evidence quality and mechanistic logic.
  0.9+ = strong mechanistic basis, high-quality evidence sentences
  0.7–0.9 = plausible with reasonable evidence
  0.5–0.7 = speculative but not impossible
  <0.5 = weak or contradictory — set is_plausible to false

- novelty: Is this relationship already well-established in the longevity field?
  "known" = this is textbook biology, already in major reviews
  "likely_known" = probably in the literature but not definitively proven
  "novel" = genuinely unexpected or not yet directly tested

- reasoning: 2–3 sentences. Cite the specific biological mechanism that makes
  this plausible or implausible. Be concrete — name pathways, receptors, or
  downstream effects where relevant.
"""


def find_missing_links(driver) -> List[Dict]:
    """
    Finds transitive relationships in the graph that are not directly connected.
    e.g., A -> B and B -> C exists, but A -> C does not.
    """
    with driver.session() as session:
        query = """
        MATCH (a:Entity)-[r1]->(b:Entity)-[r2]->(c:Entity)
        WHERE a <> c AND NOT (a)-[]->(c)
        RETURN
            a.name AS source,
            type(r1) AS rel1,
            r1.evidence AS evidence1,
            b.name AS intermediate,
            type(r2) AS rel2,
            r2.evidence AS evidence2,
            c.name AS target
        LIMIT 10
        """
        result = session.run(query)
        return [dict(record) for record in result]


def evaluate_hypothesis(hypothesis: Dict) -> HypothesisEvaluation:
    """
    Evaluates a transitive hypothesis using Gemini. Asks the model to reason
    about biological plausibility, confidence, and novelty of the proposed link.
    Falls back to a conservative implausible result if the API call fails.
    """
    config = config_manager.config
    api_key = config.gemini_api_key

    if not api_key:
        logger.error("GEMINI_API_KEY not found. Hypothesis evaluation skipped.")
        return HypothesisEvaluation(
            is_plausible=False,
            confidence=0.0,
            novelty=NoveltyLevel.KNOWN,
            reasoning="Evaluation skipped — Gemini API key not configured.",
        )

    prompt = EVAL_PROMPT.format(
        source=hypothesis.get("source", ""),
        intermediate=hypothesis.get("intermediate", ""),
        target=hypothesis.get("target", ""),
        evidence1=hypothesis.get("evidence1", ""),
        evidence2=hypothesis.get("evidence2", ""),
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=HypothesisEvaluation,
                temperature=0.1,
            ),
        )
        return HypothesisEvaluation.model_validate_json(response.text)

    except Exception as e:
        logger.error(f"Hypothesis evaluation failed: {e}")
        return HypothesisEvaluation(
            is_plausible=False,
            confidence=0.0,
            novelty=NoveltyLevel.KNOWN,
            reasoning=f"Evaluation failed due to an error: {e}",
        )


def generate_markdown_report(topic: str, evaluated: List[Tuple[Dict, HypothesisEvaluation]]) -> str:
    """
    Generates a research report from evaluated hypotheses.
    Only includes plausible findings, sorted by confidence descending.
    Formatted for Obsidian with YAML frontmatter and WikiLinks.
    """
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Sort by confidence descending
    evaluated = sorted(evaluated, key=lambda x: x[1].confidence, reverse=True)

    novelty_emoji = {
        NoveltyLevel.NOVEL:        "🔥 Novel",
        NoveltyLevel.LIKELY_KNOWN: "🔬 Likely Known",
        NoveltyLevel.KNOWN:        "📚 Established",
    }

    report = f"""---
title: "Discovery Report: {topic}"
date: {date_str}
topic: "{topic}"
type: research_report
agent: VitaGraph Oracle v0.1.0
hypotheses_found: {len(evaluated)}
---

# ◈ Research Discovery: {topic}
**Generated by VitaGraph AI** | *{date_str}*

## 🧬 Executive Summary
The following biological relationships were identified through transitive link analysis
and evaluated by Gemini for plausibility. Only relationships scored as biologically
coherent are included. Findings are ranked by confidence.

---

"""

    if not evaluated:
        report += "No plausible novel links were identified in this session. Try ingesting more varied literature to expand the discovery horizon.\n"
        return report

    for i, (h, ev) in enumerate(evaluated, 1):
        source       = f"[[{h['source']}]]"
        intermediate = f"[[{h['intermediate']}]]"
        target       = f"[[{h['target']}]]"
        novelty_tag  = novelty_emoji.get(ev.novelty, str(ev.novelty))

        report += f"### Discovery {i}: {h['source']} → {h['target']}\n"
        report += f"**Novelty**: {novelty_tag} | **Confidence**: {ev.confidence:.0%}\n\n"
        report += f"**Proposed Relationship**: {source} --[Indirect]--> {target}\n\n"

        report += "#### 🧩 Evidence Chain\n"
        report += f"1. {source} → **{h.get('rel1', 'interacts with')}** → {intermediate}\n"
        report += f"   - *\"{h.get('evidence1', '')}\"*\n"
        report += f"2. {intermediate} → **{h.get('rel2', 'interacts with')}** → {target}\n"
        report += f"   - *\"{h.get('evidence2', '')}\"*\n\n"

        report += "#### 🤖 AI Evaluation\n"
        report += f"{ev.reasoning}\n\n"
        report += "---\n\n"

    return report
