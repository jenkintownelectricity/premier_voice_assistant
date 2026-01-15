"""
Latency Manager - Context-Aware Fillers (World Class Edition)

This is the brain of your voice AI platform. It:
1. Routes queries to the best LLM (fast vs smart)
2. Masks latency with CONTEXT-AWARE filler sounds
3. Retrieves skill-specific knowledge for narrow-role assistants
4. Integrates with your voice platform (LiveKit, Vapi, etc.)

World-Class Latency Masking Strategy:
- Acoustic (0ms): "Hmm", "Uh-huh" (Immediate reaction)
- Phatic (500ms): "I see", "Got it" (Acknowledges receipt)
- Process (2s+): "Pulling up that spec sheet..." (Justifies the delay)
"""

import asyncio
import time
import random
from typing import AsyncGenerator, Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum

# ============================================================================
# LATENCY MASKING - Context-Aware Edition (The Secret Sauce)
# ============================================================================

class LatencyMasker:
    """
    Context-Aware Latency Masker - World Class Edition

    A world-class agent doesn't just say "Hmm...". It buys time by telling
    you what it's doing. This builds trust and makes delays feel purposeful.

    Three-tier filler strategy:
    1. ACOUSTIC (<200ms): "Hmm...", "Uh-huh..." - Immediate reaction
    2. PHATIC (500ms): "I see", "Got it" - Acknowledges receipt
    3. PROCESS (2s+): "Running the estimate..." - Justifies the delay
    """

    def __init__(self, skill_type: Optional[str] = None):
        self.skill_type = skill_type
        self.last_filler_time = 0
        self.fillers_used: List[str] = []

        # 1. THE "MICRO-FILLER" (Immediate Reaction - <200ms)
        # Used when the system needs just a split second.
        self.acoustic_fillers = [
            "Hmm...",
            "Mmm...",
            "Uh-huh...",
            "Right...",
            "Okay...",
        ]

        # 2. THE "HOLDING PATTERN" (Thinking Time - >1s)
        # Context-aware phrases that justify the delay.
        self.context_fillers = {
            "general": [
                "Let me see...",
                "One moment...",
                "Let me check that for you...",
                "Bear with me a second...",
                "Thinking through that...",
            ],
            # ROOFING / CONSTRUCTION / TECHNICAL
            "technical": [
                "Checking the assembly specs...",
                "Pulling up the manufacturer data...",
                "Verifying that code requirement...",
                "Let me look at the detail drawing...",
                "Reviewing the layer buildup...",
                "Let me look that up...",
                "Checking the docs...",
            ],
            # SCHEDULING / CRM
            "scheduling": [
                "Checking the calendar...",
                "Let me see what times are open...",
                "Looking at availability...",
                "Just a moment, syncing the schedule...",
            ],
            # MATH / ESTIMATES
            "calculation": [
                "Running those numbers...",
                "Let me total that up...",
                "Calculating the estimate...",
                "Double checking the math...",
            ],
            # NEGOTIATION / SALES
            "sales": [
                "Great question!",
                "Let me find the best option...",
                "Checking what we have available...",
            ],
            # EMPATHETIC / CUSTOMER SERVICE
            "customer_service": [
                "I understand where you're coming from...",
                "That's a fair point...",
                "Let me see what we can do there...",
                "I hear you...",
                "I understand.",
                "Let me help with that...",
            ],
            # ELECTRICIAN
            "electrician": [
                "Let me check the electrical codes...",
                "Reviewing the circuit requirements...",
                "Looking up the panel specs...",
            ],
            # PLUMBER
            "plumber": [
                "Checking the pipe sizing...",
                "Let me look at the fixture requirements...",
                "Reviewing the drain calculations...",
            ],
            # SOLAR
            "solar": [
                "Calculating the panel layout...",
                "Checking your roof orientation...",
                "Running the energy production estimate...",
            ],
            # LEGAL
            "lawyer": [
                "Let me review that provision...",
                "Checking the relevant statute...",
                "Looking at the case details...",
            ],
        }

    def get_instant_filler(self) -> str:
        """Get a quick acoustic filler for immediate response (<200ms)"""
        return random.choice(self.acoustic_fillers)

    def get_context_filler(self, context: str = "general") -> str:
        """Get a context-aware filler phrase for longer waits"""
        # Use skill_type if set, otherwise use provided context
        effective_context = self.skill_type or context

        # Get the appropriate filler category
        category = self.context_fillers.get(
            effective_context,
            self.context_fillers["general"]
        )

        # Avoid repeating the same phrase
        available = [p for p in category if p not in self.fillers_used[-3:]]
        if not available:
            available = category

        phrase = random.choice(available)
        self.fillers_used.append(phrase)
        return phrase

    def get_thinking_phrase(self) -> str:
        """Alias for get_context_filler for backwards compatibility"""
        return self.get_context_filler()

    async def mask_latency(
        self,
        response_generator: AsyncGenerator[str, None],
        context: str = "general",
    ) -> AsyncGenerator[str, None]:
        """
        Yields a context-aware filler immediately, then the real response.

        World-class latency masking strategy:
        - 30% chance: Short acoustic filler ("Hmm...")
        - 70% chance: Context-specific phrase ("Running those numbers...")

        Usage:
            async for chunk in masker.mask_latency(llm.generate(prompt), context="calculation"):
                send_to_tts(chunk)
        """
        # A. DECISION LOGIC: Short vs Long Delay?
        # Mix them for natural variation.

        # 30% chance of a short acoustic filler ("Hmm...")
        if random.random() < 0.3:
            filler = random.choice(self.acoustic_fillers)
        else:
            # 70% chance of a context-specific phrase
            filler = self.get_context_filler(context)

        # B. YIELD FILLER (The "Buying Time" Step)
        yield filler + " "

        # C. YIELD REAL INTELLIGENCE
        first_token_received = False
        async for chunk in response_generator:
            if not first_token_received:
                first_token_received = True
                # Natural transition from filler to response
                yield "\n"
            yield chunk

        # D. FALLBACK if no response received
        if not first_token_received:
            yield "I'm having trouble with that. Could you try again?"


# ============================================================================
# LLM PROVIDERS - Unified Interface
# ============================================================================

class LLMProvider(Enum):
    BITNET = "bitnet"      # Your local 1-bit model (free, slower)
    GROQ = "groq"          # Groq API (fast, free tier)
    OPENAI = "openai"      # OpenAI (smart, paid)
    ANTHROPIC = "anthropic"  # Claude (smart, paid)
    CEREBRAS = "cerebras"  # Cerebras (fast, free tier)
    TOGETHER = "together"  # Together.ai (various models)


@dataclass
class LLMConfig:
    """Configuration for an LLM provider"""
    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 256
    temperature: float = 0.7

    # Performance characteristics
    avg_first_token_ms: int = 500  # Average time to first token
    avg_tokens_per_sec: int = 50   # Average generation speed
    cost_per_1k_tokens: float = 0.0  # Cost in dollars


@dataclass
class QueryAnalysis:
    """Analysis of a user query for routing decisions"""
    complexity: str  # "simple", "medium", "complex"
    intent: str  # "greeting", "question", "command", "conversation"
    skill_match: Optional[str] = None  # Matched skill if any
    requires_reasoning: bool = False
    requires_current_info: bool = False
    confidence: float = 0.9


# ============================================================================
# SMART ROUTER - Decides which LLM to use
# ============================================================================

class SmartRouter:
    """
    Routes queries to the optimal LLM based on:
    - Query complexity
    - Required response quality
    - Latency requirements
    - Cost optimization
    - Skill matching
    """

    # Simple patterns that don't need smart LLMs
    SIMPLE_PATTERNS = [
        "hello", "hi", "hey", "good morning", "good afternoon",
        "how are you", "what's up", "thanks", "thank you", "bye",
        "goodbye", "yes", "no", "okay", "ok", "sure",
    ]

    def __init__(self, llm_configs: Dict[LLMProvider, LLMConfig]):
        self.llm_configs = llm_configs
        self.query_history = []

    def analyze_query(self, query: str, context: Optional[Dict] = None) -> QueryAnalysis:
        """Analyze a query to determine routing"""
        query_lower = query.lower().strip()

        # Check for simple patterns
        for pattern in self.SIMPLE_PATTERNS:
            if query_lower.startswith(pattern) or query_lower == pattern:
                return QueryAnalysis(
                    complexity="simple",
                    intent="greeting" if pattern in ["hello", "hi", "hey"] else "acknowledgment",
                    confidence=0.95
                )

        # Check query length and complexity indicators
        word_count = len(query.split())
        has_question_words = any(w in query_lower for w in ["why", "how", "explain", "what if", "compare"])
        has_reasoning_words = any(w in query_lower for w in ["because", "therefore", "analyze", "think"])

        if word_count <= 5 and not has_question_words:
            complexity = "simple"
        elif has_reasoning_words or word_count > 30:
            complexity = "complex"
        else:
            complexity = "medium"

        return QueryAnalysis(
            complexity=complexity,
            intent="question" if "?" in query else "statement",
            requires_reasoning=has_reasoning_words,
            confidence=0.8
        )

    def select_llm(self, analysis: QueryAnalysis, latency_critical: bool = True) -> LLMProvider:
        """Select the best LLM for this query"""

        # Simple queries -> fastest option
        if analysis.complexity == "simple":
            # Prefer Groq for speed, fallback to BitNet
            if LLMProvider.GROQ in self.llm_configs:
                return LLMProvider.GROQ
            return LLMProvider.BITNET

        # Complex queries -> smartest option
        if analysis.complexity == "complex" or analysis.requires_reasoning:
            # Prefer Claude/GPT-4 for reasoning
            if LLMProvider.ANTHROPIC in self.llm_configs:
                return LLMProvider.ANTHROPIC
            if LLMProvider.OPENAI in self.llm_configs:
                return LLMProvider.OPENAI

        # Medium complexity -> balance speed and quality
        if latency_critical:
            return LLMProvider.GROQ if LLMProvider.GROQ in self.llm_configs else LLMProvider.BITNET
        else:
            return LLMProvider.OPENAI if LLMProvider.OPENAI in self.llm_configs else LLMProvider.GROQ


# ============================================================================
# SKILL RETRIEVER - Knowledge for narrow-role assistants
# ============================================================================

@dataclass
class Skill:
    """A skill represents specialized knowledge/behavior for a narrow role"""
    name: str
    description: str
    system_prompt: str
    knowledge_base: list = field(default_factory=list)  # RAG documents
    example_responses: Dict[str, str] = field(default_factory=dict)  # Pattern -> Response
    filler_type: str = "default"
    preferred_llm: Optional[LLMProvider] = None


class SkillRetriever:
    """Retrieves and applies skills for narrow-role voice assistants"""

    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self.active_skill: Optional[Skill] = None

    def register_skill(self, skill: Skill):
        """Register a new skill"""
        self.skills[skill.name] = skill

    def match_skill(self, query: str, context: Optional[Dict] = None) -> Optional[Skill]:
        """Find the best matching skill for a query"""
        # Simple keyword matching for now - could use embeddings
        query_lower = query.lower()

        for skill in self.skills.values():
            # Check if query matches any example patterns
            for pattern in skill.example_responses.keys():
                if pattern.lower() in query_lower:
                    return skill

        return self.active_skill  # Return current skill if no match

    def get_cached_response(self, skill: Skill, query: str) -> Optional[str]:
        """Check if we have a cached response for this query"""
        query_lower = query.lower()
        for pattern, response in skill.example_responses.items():
            if pattern.lower() in query_lower:
                return response
        return None


# ============================================================================
# COMMAND CENTER - Main orchestrator
# ============================================================================

class SkillCommandCenter:
    """
    The main orchestrator that combines:
    - LLM routing
    - Latency masking
    - Skill retrieval
    - Voice platform integration
    """

    def __init__(self):
        self.router = SmartRouter({})
        self.skill_retriever = SkillRetriever()
        self.latency_masker = LatencyMasker()
        self.llm_clients: Dict[LLMProvider, Any] = {}

        # Stats tracking
        self.stats = {
            "total_queries": 0,
            "by_provider": {},
            "avg_latency_ms": 0,
            "cache_hits": 0,
        }

    def register_llm(self, config: LLMConfig, client: Any):
        """Register an LLM provider with its client"""
        self.router.llm_configs[config.provider] = config
        self.llm_clients[config.provider] = client

    def register_skill(self, skill: Skill):
        """Register a skill for narrow-role assistants"""
        self.skill_retriever.register_skill(skill)

    async def process_query(
        self,
        query: str,
        context: Optional[Dict] = None,
        use_latency_masking: bool = True,
        force_provider: Optional[LLMProvider] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Process a query through the command center.

        This is the main entry point for voice AI integration.
        Returns an async generator that yields response chunks.
        """
        start_time = time.time()
        self.stats["total_queries"] += 1

        # 1. Check for skill match and cached response
        skill = self.skill_retriever.match_skill(query, context)
        if skill:
            cached = self.skill_retriever.get_cached_response(skill, query)
            if cached:
                self.stats["cache_hits"] += 1
                yield cached
                return

            # Update latency masker for skill-specific fillers
            self.latency_masker.skill_type = skill.filler_type

        # 2. Analyze query and select LLM
        analysis = self.router.analyze_query(query, context)

        if force_provider:
            provider = force_provider
        elif skill and skill.preferred_llm:
            provider = skill.preferred_llm
        else:
            provider = self.router.select_llm(analysis)

        # Track stats
        provider_name = provider.value
        self.stats["by_provider"][provider_name] = self.stats["by_provider"].get(provider_name, 0) + 1

        # 3. Generate response with latency masking
        async def generate():
            # This would call the actual LLM client
            # For now, placeholder that simulates response
            client = self.llm_clients.get(provider)
            if client:
                # Actual LLM call would go here
                async for chunk in client.generate(query, skill):
                    yield chunk
            else:
                yield f"[No client configured for {provider.value}]"

        if use_latency_masking:
            async for chunk in self.latency_masker.mask_latency(generate()):
                yield chunk
        else:
            async for chunk in generate():
                yield chunk

        # Update latency stats
        elapsed = (time.time() - start_time) * 1000
        self.stats["avg_latency_ms"] = (
            self.stats["avg_latency_ms"] * 0.9 + elapsed * 0.1
        )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def demo():
    """Demo the command center"""

    # Initialize
    center = SkillCommandCenter()

    # Register a sample skill
    receptionist = Skill(
        name="receptionist",
        description="Front desk receptionist for a dental office",
        system_prompt="You are a friendly receptionist at a dental office...",
        example_responses={
            "hours": "We're open Monday through Friday, 9 AM to 5 PM.",
            "appointment": "I'd be happy to help you schedule an appointment!",
            "location": "We're located at 123 Main Street.",
        },
        filler_type="customer_service",
    )
    center.register_skill(receptionist)

    # Process a query
    print("Processing: 'What are your hours?'")
    async for chunk in center.process_query("What are your hours?"):
        print(chunk, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(demo())
