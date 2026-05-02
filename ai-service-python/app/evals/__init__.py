"""Eval harness for the RAG pipeline.

Two layers of measurement are exposed:

* `runner.evaluate_retrieval` — feeds a goldset of (query, relevant chunk
  ids) pairs through the hybrid retriever and computes ranx metrics
  (recall@k, MRR, nDCG). Useful for tuning chunking, BM25, fusion.

* `judge.score_faithfulness` / `score_answer_relevance` — LLM-as-judge
  scoring of generated answers vs the source set and the original query.
  Run on a small subset to bound LLM cost.

Goldset format: JSON Lines, one entry per line, schema in `goldset.GoldEntry`.
"""

from app.evals.goldset import GoldEntry, load_goldset
from app.evals.runner import evaluate_retrieval

__all__ = ["GoldEntry", "load_goldset", "evaluate_retrieval"]
