"""Embedding-based tool auto-routing for Mona.

Routes user messages to the most relevant tool suite using sentence-transformer
embeddings and cosine similarity. Supports manual override via tool_id parameter
or slash commands (e.g., /real-estate, /student).
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

TOOL_ROUTING_CONFIG_PATH = Path("/opt/openclaw/state/tool-routing-config.json")
SKILLS_LOCAL_PATH = Path("/opt/openclaw/skills/local")
EMBEDDING_MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

SLASH_COMMAND_RE = re.compile(r"^/([a-z0-9-]+)\s*", re.IGNORECASE)


@dataclass
class ToolSuiteInfo:
    id: str
    name: str
    tools: list[str]
    description: str
    embedding: Optional[np.ndarray] = field(default=None, repr=False)


@dataclass
class ToolMatch:
    tool_id: str
    tool_name: str
    confidence: float
    system_context: str
    tools: list[str]


class ToolRouter:
    def __init__(self):
        self._suites: list[ToolSuiteInfo] = []
        self._model = None
        self._confidence_threshold = 0.5
        self._initialized = False
        self._load_config()

    def _load_config(self):
        config = {}
        if TOOL_ROUTING_CONFIG_PATH.exists():
            try:
                config = json.loads(TOOL_ROUTING_CONFIG_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        self._confidence_threshold = config.get("confidence_threshold", 0.5)

        suites_data = config.get("suites", [])
        if not suites_data:
            suites_data = self._load_from_manifests()

        self._suites = []
        for s in suites_data:
            self._suites.append(ToolSuiteInfo(
                id=s["id"],
                name=s["name"],
                tools=s.get("tools", []),
                description=s.get("description", s["name"]),
            ))

        logger.info("Loaded %d tool suites for routing", len(self._suites))

    def _load_from_manifests(self) -> list[dict]:
        suites = []
        if not SKILLS_LOCAL_PATH.exists():
            return suites
        for manifest_path in sorted(SKILLS_LOCAL_PATH.glob("*/manifest.json")):
            try:
                data = json.loads(manifest_path.read_text())
                suites.append({
                    "id": data.get("slug", manifest_path.parent.name),
                    "name": data.get("name", manifest_path.parent.name),
                    "tools": data.get("tools", []),
                    "description": f"{data.get('name', '')}: {', '.join(data.get('tools', []))}",
                })
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read manifest %s: %s", manifest_path, e)
        return suites

    def _ensure_embeddings(self):
        if self._initialized:
            return
        self._initialized = True

        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(EMBEDDING_MODEL_ID)
            logger.info("Loaded embedding model: %s", EMBEDDING_MODEL_ID)
        except ImportError:
            logger.warning("sentence-transformers not installed; falling back to keyword matching")
            return
        except Exception as e:
            logger.warning("Failed to load embedding model: %s", e)
            return

        texts = [s.description for s in self._suites]
        if texts:
            embeddings = self._model.encode(texts, normalize_embeddings=True)
            for suite, emb in zip(self._suites, embeddings):
                suite.embedding = emb

    def _embed_query(self, text: str) -> Optional[np.ndarray]:
        if self._model is None:
            return None
        return self._model.encode(text, normalize_embeddings=True)

    def _keyword_match(self, message: str) -> Optional[ToolSuiteInfo]:
        """Fallback keyword matching when embedding model is unavailable."""
        msg_lower = message.lower()
        best_score = 0
        best_suite = None

        for suite in self._suites:
            score = 0
            for tool_name in suite.tools:
                if tool_name.lower() in msg_lower:
                    score += 3
            name_words = suite.name.lower().split()
            for word in name_words:
                if len(word) > 3 and word in msg_lower:
                    score += 1
            if score > best_score:
                best_score = score
                best_suite = suite

        if best_score >= 1 and best_suite:
            return best_suite
        return None

    def route(self, user_message: str, tool_id: Optional[str] = None) -> Optional[ToolMatch]:
        """Route a user message to the best-matching tool suite.

        Priority: manual tool_id > slash command > embedding similarity > keyword fallback.
        Returns None if confidence is below threshold (general assistant mode).
        """
        if tool_id:
            suite = self._find_suite(tool_id)
            if suite:
                return self._make_match(suite, 1.0)
            return None

        slash_match = SLASH_COMMAND_RE.match(user_message)
        if slash_match:
            command = slash_match.group(1)
            suite = self._find_suite(command)
            if suite:
                return self._make_match(suite, 1.0)

        self._ensure_embeddings()

        clean_message = user_message
        if slash_match:
            clean_message = user_message[slash_match.end():]

        query_emb = self._embed_query(clean_message)
        if query_emb is not None:
            best_score = -1.0
            best_suite = None
            for suite in self._suites:
                if suite.embedding is None:
                    continue
                score = float(np.dot(query_emb, suite.embedding))
                if score > best_score:
                    best_score = score
                    best_suite = suite

            if best_suite and best_score >= self._confidence_threshold:
                return self._make_match(best_suite, best_score)
        else:
            kw_suite = self._keyword_match(clean_message)
            if kw_suite:
                return self._make_match(kw_suite, 0.7)

        return None

    def strip_slash_command(self, message: str) -> str:
        """Remove a leading slash command from a message, returning the payload."""
        match = SLASH_COMMAND_RE.match(message)
        if match:
            return message[match.end():].strip()
        return message

    def get_all_tools(self) -> list[dict]:
        """Return all tool suites for the UI dropdown."""
        return [
            {
                "id": s.id,
                "name": s.name,
                "tools": s.tools,
                "description": s.description,
            }
            for s in self._suites
        ]

    def _find_suite(self, suite_id: str) -> Optional[ToolSuiteInfo]:
        for s in self._suites:
            if s.id == suite_id:
                return s
        return None

    def _make_match(self, suite: ToolSuiteInfo, confidence: float) -> ToolMatch:
        system_context = (
            f"The user's request has been routed to the {suite.name} tool suite. "
            f"Available tools: {', '.join(suite.tools)}. "
            f"Respond with expertise in this domain and reference these tools when relevant."
        )
        return ToolMatch(
            tool_id=suite.id,
            tool_name=suite.name,
            confidence=confidence,
            system_context=system_context,
            tools=suite.tools,
        )


tool_router = ToolRouter()
