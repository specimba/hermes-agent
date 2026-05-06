"""
KAIJU Governance Pipeline Automation

Automated pipeline for processing governance decisions into code improvements.
Handles docstring fixes, code quality improvements, and automatic PR generation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum
import hashlib
import json

from .kaiju import KAIJUGovernor, AgentProposal, GateDecision, TrustScore, ViolationType
from .vap import VAPChain, VAPEntry


class PipelineTrigger(Enum):
    """Types of triggers that initiate the governance pipeline."""
    DOCSTRING_GAP = "docstring_gap"
    CODE_QUALITY_ISSUE = "code_quality_issue"
    GOVERNANCE_PROPOSAL = "governance_proposal"
    TRUST_SCORE_IMPROVEMENT = "trust_improvement"
    COMPLIANCE_VIOLATION = "compliance_violation"


class ApprovalThreshold(Enum):
    """Approval threshold levels for automated actions."""
    AUTO_APPROVE = "auto_approve"           # No human review needed
    REQUIRE_REVIEW = "require_review"       # Human review required
    HARD_STOP = "hard_stop"                # Cannot proceed


@dataclass
class PipelineConfig:
    """Configuration for governance pipeline behavior."""
    # Trust score thresholds for auto-approval
    auto_approve_trust_threshold: float = 0.8
    require_review_trust_threshold: float = 0.5

    # Budget thresholds
    max_auto_budget: int = 10000
    max_review_budget: int = 50000

    # Code quality thresholds
    min_docstring_coverage: float = 0.8
    max_complexity_score: int = 10

    # PR generation settings
    auto_create_pr: bool = True
    pr_approval_required: bool = True
    pr_title_prefix: str = "[KAIJU-AUTO]"

    # VAP audit settings
    enable_audit_logging: bool = True
    audit_all_actions: bool = True


@dataclass
class PipelineRequest:
    """A request to the governance pipeline."""
    request_id: str
    trigger_type: PipelineTrigger
    agent_id: str
    target_files: List[str]
    proposed_changes: Dict[str, Any]
    justification: str
    estimated_tokens: int = 0
    priority: int = 5  # 1-10, lower is higher priority
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.request_id:
            content = f"{self.agent_id}:{self.trigger_type.value}:{json.dumps(self.target_files)}:{self.timestamp.isoformat()}"
            self.request_id = hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class PipelineResult:
    """Result of pipeline processing."""
    request_id: str
    approval_decision: ApprovalThreshold
    pr_url: Optional[str] = None
    changes_applied: bool = False
    vap_entry_id: Optional[str] = None
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class GovernancePipeline:
    """
    Automated governance pipeline for KAIJU-driven code improvements.

    Processes governance decisions and automatically:
    1. Fixes docstring gaps
    2. Improves code quality
    3. Generates PRs for approved changes
    4. Logs all actions to VAP audit chain
    """

    def __init__(
        self,
        kaiju_governor: KAIJUGovernor,
        vap_chain: VAPChain,
        config: Optional[PipelineConfig] = None
    ):
        self.governor = kaiju_governor
        self.vap_chain = vap_chain
        self.config = config or PipelineConfig()
        self._request_history: List[PipelineRequest] = []
        self._result_history: List[PipelineResult] = []

    async def process_request(self, request: PipelineRequest) -> PipelineResult:
        """
        Process a governance pipeline request.

        Args:
            request: The pipeline request to process

        Returns:
            PipelineResult with outcome
        """
        self._request_history.append(request)

        # Step 1: Evaluate via KAIJU governor
        proposal = AgentProposal(
            agent_id=request.agent_id,
            action_type="code_improvement",
            action_params={
                "trigger": request.trigger_type.value,
                "files": request.target_files,
                "changes": request.proposed_changes,
            },
            requested_capability=self._determine_required_capability(request),
            estimated_token_cost=request.estimated_tokens,
            target_resource=",".join(request.target_files),
            justification=request.justification,
        )

        gate_result = await self.governor.evaluate_proposal(
            proposal=proposal,
            available_budget=self.config.max_auto_budget,
        )

        # Step 2: Determine approval threshold
        approval = self._determine_approval_threshold(
            gate_result, request
        )

        # Step 3: Execute based on approval
        result = PipelineResult(
            request_id=request.request_id,
            approval_decision=approval,
        )

        if approval == ApprovalThreshold.HARD_STOP:
            result.error_message = f"Pipeline hard stop: {gate_result.reason}"
            await self._log_pipeline_action(request, result, gate_result)
            return result

        # Step 4: Apply changes if approved
        if approval in (ApprovalThreshold.AUTO_APPROVE, ApprovalThreshold.REQUIRE_REVIEW):
            result.changes_applied = await self._apply_changes(request, result)

            # Step 5: Generate PR if needed
            if result.changes_applied and self.config.auto_create_pr:
                result.pr_url = await self._generate_pr(request, result)

        # Step 6: Log to VAP
        vap_entry = await self._log_pipeline_action(request, result, gate_result)
        if vap_entry:
            result.vap_entry_id = vap_entry.entry_id

        self._result_history.append(result)
        return result

    def _determine_required_capability(self, request: PipelineRequest) -> str:
        """Determine required capability based on request type."""
        capability_map = {
            PipelineTrigger.DOCSTRING_GAP: "basic",
            PipelineTrigger.CODE_QUALITY_ISSUE: "intermediate",
            PipelineTrigger.GOVERNANCE_PROPOSAL: "advanced",
            PipelineTrigger.TRUST_SCORE_IMPROVEMENT: "intermediate",
            PipelineTrigger.COMPLIANCE_VIOLATION: "premium",
        }
        return capability_map.get(request.trigger_type, "basic")

    def _determine_approval_threshold(
        self,
        gate_result: Any,
        request: PipelineRequest
    ) -> ApprovalThreshold:
        """Determine approval threshold based on gate result and request."""
        # Hard stop from KAIJU
        if gate_result.decision == GateDecision.HARD_STOP:
            return ApprovalThreshold.HARD_STOP

        # Deny from KAIJU
        if gate_result.decision == GateDecision.DENY:
            if gate_result.trust_score and gate_result.trust_score.overall < 0.3:
                return ApprovalThreshold.HARD_STOP
            return ApprovalThreshold.REQUIRE_REVIEW

        # Check trust score for auto-approval
        if gate_result.trust_score:
            trust = gate_result.trust_score.overall
            if trust >= self.config.auto_approve_trust_threshold:
                return ApprovalThreshold.AUTO_APPROVE
            elif trust >= self.config.require_review_trust_threshold:
                return ApprovalThreshold.REQUIRE_REVIEW

        # Default to require review
        return ApprovalThreshold.REQUIRE_REVIEW

    async def _apply_changes(
        self,
        request: PipelineRequest,
        result: PipelineResult
    ) -> bool:
        """Apply the proposed changes to target files."""
        try:
            for filepath in request.target_files:
                # In production, this would apply actual code changes
                # For now, we log the intended changes
                pass

            # Log action to VAP
            if self.config.enable_audit_logging:
                await self.vap_chain.log_agent_action(
                    agent_id=request.agent_id,
                    action_type="apply_changes",
                    action_params={
                        "files": request.target_files,
                        "trigger": request.trigger_type.value,
                    },
                    result_hash=result.request_id,
                    metadata={
                        "changes": request.proposed_changes,
                        "pipeline_request": request.request_id,
                    },
                )
            return True
        except Exception as e:
            result.error_message = f"Failed to apply changes: {str(e)}"
            return False

    async def _generate_pr(
        self,
        request: PipelineRequest,
        result: PipelineResult
    ) -> Optional[str]:
        """Generate a GitHub PR for the applied changes."""
        try:
            pr_title = f"{self.config.pr_title_prefix} {request.trigger_type.value}: {request.justification[:50]}"
            pr_body = self._generate_pr_body(request, result)

            # In production, this would use GitHub API
            # For now, return a placeholder
            pr_url = f"https://github.com/nexus-os/auto-pr/{result.request_id}"

            # Log PR creation to VAP
            if self.config.enable_audit_logging:
                await self.vap_chain.log_agent_action(
                    agent_id=request.agent_id,
                    action_type="create_pr",
                    action_params={
                        "title": pr_title,
                        "files": request.target_files,
                    },
                    result_hash=hashlib.sha256(pr_url.encode()).hexdigest()[:16],
                    metadata={
                        "pr_url": pr_url,
                        "pipeline_request": request.request_id,
                    },
                )
            return pr_url
        except Exception as e:
            result.error_message = f"Failed to generate PR: {str(e)}"
            return None

    def _generate_pr_body(
        self,
        request: PipelineRequest,
        result: PipelineResult
    ) -> str:
        """Generate PR description body."""
        return f"""
# KAIJU Automated Governance Change

## Trigger
{request.trigger_type.value}

## Justification
{request.justification}

## Target Files
{chr(10).join(f"- {f}" for f in request.target_files)}

## Proposed Changes
```json
{json.dumps(request.proposed_changes, indent=2)}
```

## Approval Decision
{result.approval_decision.value}

## Pipeline Request ID
{request.request_id}

## VAP Audit
Entry ID: {result.vap_entry_id or "N/A"}

---
*This PR was auto-generated by KAIJU Governance Pipeline*
"""

    async def _log_pipeline_action(
        self,
        request: PipelineRequest,
        result: PipelineResult,
        gate_result: Any
    ) -> Optional[VAPEntry]:
        """Log pipeline action to VAP chain."""
        if not self.config.enable_audit_logging:
            return None

        metadata = {
            "pipeline_request": request.request_id,
            "trigger_type": request.trigger_type.value,
            "approval_decision": result.approval_decision.value,
            "changes_applied": result.changes_applied,
            "pr_url": result.pr_url,
            "gate_decision": gate_result.decision.value if gate_result else "unknown",
            "agent_id": request.agent_id,
        }

        return await self.vap_chain._log_event(
            event_type="governance_pipeline",
            agent_id=request.agent_id,
            action_hash=result.request_id,
            metadata=metadata,
        )

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        total_requests = len(self._request_history)
        total_results = len(self._result_history)

        auto_approved = sum(
            1 for r in self._result_history
            if r.approval_decision == ApprovalThreshold.AUTO_APPROVE
        )
        review_required = sum(
            1 for r in self._result_history
            if r.approval_decision == ApprovalThreshold.REQUIRE_REVIEW
        )
        hard_stopped = sum(
            1 for r in self._result_history
            if r.approval_decision == ApprovalThreshold.HARD_STOP
        )

        return {
            "total_requests": total_requests,
            "total_results": total_results,
            "auto_approved": auto_approved,
            "review_required": review_required,
            "hard_stopped": hard_stopped,
            "prs_generated": sum(1 for r in self._result_history if r.pr_url),
            "changes_applied": sum(1 for r in self._result_history if r.changes_applied),
        }
