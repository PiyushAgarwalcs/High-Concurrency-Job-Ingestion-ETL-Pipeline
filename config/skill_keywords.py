"""
AI relevance detection and skill keyword matrices for the Job Filtering Engine.
Categorized into Core AI, LLM & Agentic AI, AI Application & Deployment, and DSA / SWE keywords.
"""

from typing import List

# ─── A. Core AI Keywords ──────────────────────────────────────────────────────
CORE_AI_KEYWORDS: List[str] = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "neural networks",
    "neural network",
    "generative ai",
    "genai",
    "gen ai",
    "large language models",
    "large language model",
    "llm",
    "llms",
    "nlp",
    "natural language processing",
    "computer vision",
    "reinforcement learning",
    "predictive modeling",
]

# ─── B. LLM and Agentic AI Keywords ───────────────────────────────────────────
LLM_AGENTIC_KEYWORDS: List[str] = [
    "rag",
    "retrieval augmented generation",
    "retrieval-augmented generation",
    "langchain",
    "langgraph",
    "llamaindex",
    "llama index",
    "ai agents",
    "ai agent",
    "agentic ai",
    "multi-agent systems",
    "multi agent systems",
    "multiagent systems",
    "multi-agent",
    "tool calling",
    "function calling",
    "mcp",
    "prompt engineering",
    "vector databases",
    "vector database",
    "vector db",
    "embeddings",
    "semantic search",
    "llm evaluation",
    "fine tuning",
    "fine-tuning",
    "model serving",
]

# ─── C. AI Application and Deployment Keywords ─────────────────────────────────
AI_APPLICATION_DEPLOYMENT_KEYWORDS: List[str] = [
    "ai integration",
    "ai deployment",
    "model deployment",
    "inference",
    "model serving",
    "ai applications",
    "ai application",
    "ai automation",
    "ai workflows",
    "ai workflow",
    "ai pipelines",
    "ai pipeline",
    "production ai",
    "ml pipelines",
    "ml pipeline",
    "mlops",
    "llmops",
    "ai infrastructure",
]

# ─── D. DSA Keywords (Validates SDE / SWE roles without AI keywords) ──────────
DSA_KEYWORDS: List[str] = [
    "data structures",
    "algorithms",
    "dsa",
    "competitive programming",
    "problem solving",
]

# ─── Supporting Technical Keywords (Helpful for ranking, insufficient alone) ──
# Python alone, SQL alone, or basic API development must NOT qualify SDE roles
SUPPORTING_SWE_KEYWORDS: List[str] = [
    "c++",
    "python",
    "backend development",
    "distributed systems",
    "api development",
    "system design",
    "rest api",
    "sql",
]

# Combined AI Relevance Validation Keywords (Category A + B + C)
AI_RELEVANCE_KEYWORDS: List[str] = (
    CORE_AI_KEYWORDS
    + LLM_AGENTIC_KEYWORDS
    + AI_APPLICATION_DEPLOYMENT_KEYWORDS
)

# SDE Validation Keywords: Either AI Relevance or DSA qualifies an SDE role
SDE_VALIDATION_KEYWORDS: List[str] = AI_RELEVANCE_KEYWORDS + DSA_KEYWORDS

