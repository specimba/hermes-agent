"""
TokenGuard - Token Economy and Budget Enforcement

Implements token budget management with:
- Dynamic budget allocation based on trust scores
- Real-time token tracking and enforcement
- Premium model access control
- Automatic budget replenishment strategies
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from enum import Enum


class BudgetTier(Enum):
    """Token budget tiers based on agent trust and capability."""
    ECO = "eco"           # 10K tokens/hour - Basic tasks
    FAST = "fast"         # 50K tokens/hour - Standard operations  
    PREMIUM = "premium"   # 200K tokens/hour - High reasoning tasks
    UNLIMITED = "unlimited"  # No limits - System agents only


@dataclass
class TokenBudget:
    """Represents an agent's token budget state."""
    agent_id: str
    tier: BudgetTier = BudgetTier.ECO
    total_budget: int = 10000
    used_tokens: int = 0
    remaining_tokens: int = 10000
    hourly_limit: int = 10000
    window_start: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        # Set limits based on tier
        tier_limits = {
            BudgetTier.ECO: 10000,
            BudgetTier.FAST: 50000,
            BudgetTier.PREMIUM: 200000,
            BudgetTier.UNLIMITED: float('inf'),
        }
        self.hourly_limit = tier_limits.get(self.tier, 10000)
        self.total_budget = self.hourly_limit
        self.remaining_tokens = self.total_budget
    
    def consume(self, tokens: int) -> bool:
        """
        Attempt to consume tokens from budget.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if successful, False if insufficient budget
        """
        if self._is_window_expired():
            self._reset_window()
        
        if tokens > self.remaining_tokens:
            return False
        
        self.used_tokens += tokens
        self.remaining_tokens -= tokens
        self.last_updated = datetime.utcnow()
        return True
    
    def _is_window_expired(self) -> bool:
        """Check if the hourly window has expired."""
        return datetime.utcnow() - self.window_start >= timedelta(hours=1)
    
    def _reset_window(self):
        """Reset the hourly window."""
        self.window_start = datetime.utcnow()
        self.used_tokens = 0
        self.remaining_tokens = self.total_budget


@dataclass
class ModelPool:
    """Represents a pool of models with shared budget."""
    name: str
    tier: BudgetTier
    models: List[str]
    total_budget: int
    used_budget: int = 0
    rate_limit_remaining: int = 1000
    cooldown_until: Optional[datetime] = None
    
    def is_available(self) -> bool:
        """Check if model pool is available for use."""
        if self.cooldown_until and datetime.utcnow() < self.cooldown_until:
            return False
        return self.rate_limit_remaining > 0 and self.used_budget < self.total_budget


class TokenGuard:
    """
    TokenGuard - Token economy manager for NEXUS OS.
    
    Manages token budgets across:
    - Individual agents (based on trust scores)
    - Model pools (FAST, PREMIUM, ECO)
    - Cloudflare Gateway integration
    
    Features:
    - Dynamic tier assignment based on trust
    - Real-time budget enforcement
    - Rate limit synchronization across 50+ APIs
    - Automatic degradation on 429 errors
    """
    
    def __init__(self, cloudflare_client=None, zilliz_client=None):
        """
        Initialize TokenGuard.
        
        Args:
            cloudflare_client: Cloudflare KV client for distributed budget sync
            zilliz_client: Zilliz client for persistent budget storage
        """
        self.cloudflare_client = cloudflare_client
        self.zilliz_client = zilliz_client
        
        # Agent budgets
        self._agent_budgets: Dict[str, TokenBudget] = {}
        
        # Model pools
        self._model_pools: Dict[str, ModelPool] = {
            "eco": ModelPool(
                name="ECO Pool",
                tier=BudgetTier.ECO,
                models=["twave-local", "bonsai-1bit", "ollama-tiny"],
                total_budget=500000,
            ),
            "fast": ModelPool(
                name="FAST Pool",
                tier=BudgetTier.FAST,
                models=["groq-llama3", "gemini-flash-lite"],
                total_budget=1000000,
            ),
            "premium": ModelPool(
                name="PREMIUM Pool",
                tier=BudgetTier.PREMIUM,
                models=["gemini-2.5-pro", "claude-4.6"],
                total_budget=2000000,
            ),
        }
    
    def get_or_create_budget(self, agent_id: str, trust_score: float = 0.5) -> TokenBudget:
        """
        Get existing budget or create new one based on trust score.
        
        Args:
            agent_id: Agent identifier
            trust_score: Current trust score (0.0-1.0)
            
        Returns:
            TokenBudget for the agent
        """
        if agent_id in self._agent_budgets:
            budget = self._agent_budgets[agent_id]
            if budget._is_window_expired():
                budget._reset_window()
            return budget
        
        # Assign tier based on trust score
        if trust_score >= 0.8:
            tier = BudgetTier.PREMIUM
        elif trust_score >= 0.5:
            tier = BudgetTier.FAST
        else:
            tier = BudgetTier.ECO
        
        budget = TokenBudget(agent_id=agent_id, tier=tier)
        self._agent_budgets[agent_id] = budget
        return budget
    
    async def check_and_consume(
        self,
        agent_id: str,
        tokens: int,
        trust_score: float = 0.5
    ) -> tuple[bool, str]:
        """
        Check budget and consume tokens if available.
        
        Args:
            agent_id: Agent requesting tokens
            tokens: Number of tokens needed
            trust_score: Current trust score
            
        Returns:
            Tuple of (success, reason)
        """
        budget = self.get_or_create_budget(agent_id, trust_score)
        
        if not budget.consume(tokens):
            return False, f"Insufficient budget: {budget.remaining_tokens}/{tokens}"
        
        # Sync to Cloudflare KV if available
        if self.cloudflare_client:
            await self._sync_to_cloudflare(agent_id, budget)
        
        return True, f"Consumed {tokens} tokens, {budget.remaining_tokens} remaining"
    
    def select_model_pool(
        self,
        required_capability: str,
        trust_score: float
    ) -> Optional[ModelPool]:
        """
        Select appropriate model pool based on capability and trust.
        
        Args:
            required_capability: Required capability tier
            trust_score: Agent's trust score
            
        Returns:
            Selected ModelPool or None if unavailable
        """
        # Map capability to pool
        capability_map = {
            "basic": [BudgetTier.ECO],
            "intermediate": [BudgetTier.ECO, BudgetTier.FAST],
            "advanced": [BudgetTier.FAST, BudgetTier.PREMIUM],
            "premium": [BudgetTier.PREMIUM],
        }
        
        allowed_tiers = capability_map.get(required_capability, [BudgetTier.ECO])
        
        # Filter by trust score
        if trust_score < 0.8 and BudgetTier.PREMIUM in allowed_tiers:
            allowed_tiers.remove(BudgetTier.PREMIUM)
        
        # Find available pool
        for tier in allowed_tiers:
            pool_name = tier.value
            pool = self._model_pools.get(pool_name)
            if pool and pool.is_available():
                return pool
        
        # Fallback to ECO if nothing else available
        eco_pool = self._model_pools.get("eco")
        if eco_pool and eco_pool.is_available():
            return eco_pool
        
        return None
    
    async def handle_rate_limit(
        self,
        pool_name: str,
        retry_after_seconds: int = 60
    ):
        """
        Handle rate limit error from a model pool.
        
        Args:
            pool_name: Name of the rate-limited pool
            retry_after_seconds: Cooldown period
        """
        pool = self._model_pools.get(pool_name)
        if pool:
            pool.rate_limit_remaining = max(0, pool.rate_limit_remaining - 100)
            pool.cooldown_until = datetime.utcnow() + timedelta(seconds=retry_after_seconds)
            
            # Log to FAILURE_PATTERN track in production
            print(f"Rate limit hit for {pool_name}, cooling down until {pool.cooldown_until}")
    
    async def _sync_to_cloudflare(self, agent_id: str, budget: TokenBudget):
        """Sync budget state to Cloudflare KV."""
        if not self.cloudflare_client:
            return
        
        try:
            key = f"nexus:budget:{agent_id}"
            value = {
                "tier": budget.tier.value,
                "used_tokens": budget.used_tokens,
                "remaining_tokens": budget.remaining_tokens,
                "window_start": budget.window_start.isoformat(),
                "last_updated": budget.last_updated.isoformat(),
            }
            await self.cloudflare_client.put(key, value, expiration_ttl=3600)
        except Exception as e:
            print(f"Failed to sync budget to Cloudflare: {e}")
    
    def get_budget_summary(self, agent_id: str) -> Dict:
        """Get budget summary for an agent."""
        budget = self._agent_budgets.get(agent_id)
        if not budget:
            return {"error": "No budget found for agent"}
        
        return {
            "agent_id": agent_id,
            "tier": budget.tier.value,
            "total_budget": budget.total_budget,
            "used_tokens": budget.used_tokens,
            "remaining_tokens": budget.remaining_tokens,
            "usage_percentage": (budget.used_tokens / budget.total_budget * 100) if budget.total_budget > 0 else 0,
            "window_resets_in": str(timedelta(hours=1) - (datetime.utcnow() - budget.window_start)),
        }
    
    def get_all_pool_status(self) -> Dict[str, Dict]:
        """Get status of all model pools."""
        return {
            name: {
                "tier": pool.tier.value,
                "models": pool.models,
                "total_budget": pool.total_budget,
                "used_budget": pool.used_budget,
                "availability": pool.is_available(),
                "rate_limit_remaining": pool.rate_limit_remaining,
                "cooldown_until": pool.cooldown_until.isoformat() if pool.cooldown_until else None,
            }
            for name, pool in self._model_pools.items()
        }
