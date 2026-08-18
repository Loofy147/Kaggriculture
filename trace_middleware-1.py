from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple
import copy
import logging

Action = Dict[str, Any]
Observation = Dict[str, Any]


class ProposalKind(str, Enum):
    MODIFY = "modify"
    REPLACE = "replace"
    DELAY = "delay"
    CANCEL = "cancel"
    HOLD = "hold"
    RECOVER = "recover"


@dataclass
class ExecutionFeedback:
    accepted: bool = True
    executed: bool = True
    partial: bool = False
    error: Optional[str] = None
    status: Optional[str] = None
    remainder: Optional[Action] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMemory:
    step: int = 0
    pending_actions: List[Action] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    estimates: Dict[str, Any] = field(default_factory=dict)
    custom_data: Dict[str, Any] = field(default_factory=dict)
    last_feedback: Optional[ExecutionFeedback] = None


@dataclass(frozen=True)
class Intent:
    action: Action
    source: str = "trace"
    step: int = 0


class BasePolicy(ABC):
    @abstractmethod
    def propose(self, obs: Observation, memory: AgentMemory) -> Intent:
        raise NotImplementedError


class TracePolicy(BasePolicy):
    def __init__(self, trace: Sequence[Action], fallback=None):
        self.trace = list(trace)
        self.fallback = fallback

    def propose(self, obs: Observation, memory: AgentMemory) -> Intent:
        step = memory.step
        if 0 <= step < len(self.trace):
            return Intent(copy.deepcopy(self.trace[step]), "trace", step)
        if self.fallback is not None:
            return Intent(copy.deepcopy(self.fallback(obs, memory)), "fallback", step)
        return Intent({"action": "PASS"}, "safe_fallback", step)


@dataclass
class OverlayProposal:
    overlay: str
    kind: ProposalKind
    action: Optional[Action] = None
    hard_constraint: bool = False
    priority: int = 0
    confidence: float = 1.0
    rationale: str = ""
    ttl: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseOverlay(ABC):
    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority

    @abstractmethod
    def propose(
        self,
        obs: Observation,
        intent: Intent,
        memory: AgentMemory,
    ) -> Optional[OverlayProposal]:
        raise NotImplementedError


@dataclass
class DecisionContext:
    obs: Observation
    intent: Intent
    proposals: Tuple[OverlayProposal, ...]
    memory: AgentMemory


@dataclass
class ArbitrationResult:
    action: Action
    winning_source: str
    applied_proposals: List[str] = field(default_factory=list)
    rejected_proposals: List[str] = field(default_factory=list)
    rationale: str = ""


class Arbiter(ABC):
    @abstractmethod
    def resolve(self, context: DecisionContext) -> ArbitrationResult:
        raise NotImplementedError


class PriorityArbiter(Arbiter):
    """Deterministic baseline arbiter.

    Hard constraints > priority > confidence.
    Ties preserve registration/proposal order because Python sorting is stable.
    """

    def resolve(self, context: DecisionContext) -> ArbitrationResult:
        proposals = list(context.proposals)
        if not proposals:
            return ArbitrationResult(
                action=copy.deepcopy(context.intent.action),
                winning_source=context.intent.source,
                rationale="No overlay intervened; baseline intent preserved.",
            )

        def score(p: OverlayProposal):
            return (int(p.hard_constraint), p.priority, p.confidence)

        ranked = sorted(proposals, key=score, reverse=True)
        winner = ranked[0]

        if winner.action is None:
            return ArbitrationResult(
                action=copy.deepcopy(context.intent.action),
                winning_source=context.intent.source,
                rejected_proposals=[p.overlay for p in ranked],
                rationale=f"Top proposal '{winner.overlay}' had no executable action.",
            )

        return ArbitrationResult(
            action=copy.deepcopy(winner.action),
            winning_source=winner.overlay,
            applied_proposals=[winner.overlay],
            rejected_proposals=[p.overlay for p in ranked[1:]],
            rationale=winner.rationale,
        )


class ExecutionRecovery(ABC):
    @abstractmethod
    def recover(self, feedback: ExecutionFeedback, memory: AgentMemory) -> None:
        raise NotImplementedError


class DefaultExecutionRecovery(ExecutionRecovery):
    def recover(self, feedback: ExecutionFeedback, memory: AgentMemory) -> None:
        if feedback.remainder is not None:
            memory.pending_actions.append(copy.deepcopy(feedback.remainder))


class CollisionRepairOverlay(BaseOverlay):
    def __init__(self):
        super().__init__("CollisionRepair", 1000)

    def propose(self, obs, intent, memory):
        if not obs.get("blocked", False):
            return None
        return OverlayProposal(
            overlay=self.name,
            kind=ProposalKind.HOLD,
            action={"action": "HOLD"},
            hard_constraint=True,
            priority=self.priority,
            confidence=1.0,
            rationale="Baseline action conflicts with a hard environment constraint.",
            metadata={"reason": "blocked", "original_action": copy.deepcopy(intent.action)},
        )


class AnticipatoryResourceOverlay(BaseOverlay):
    def __init__(self, trace: Sequence[Action], lookahead: int = 1):
        super().__init__("AnticipatoryResource", 200)
        self.trace = list(trace)
        self.lookahead = max(1, lookahead)

    def propose(self, obs, intent, memory):
        step = memory.step
        future_actions = self.trace[step + 1: step + 1 + self.lookahead]
        if not future_actions or not obs.get("future_resource_pressure", False):
            return None
        return OverlayProposal(
            overlay=self.name,
            kind=ProposalKind.MODIFY,
            action=copy.deepcopy(future_actions[0]),
            priority=self.priority,
            confidence=max(0.0, min(1.0, float(obs.get("resource_prediction_confidence", 0.5)))),
            rationale="Predicted resource contention warrants pre-positioning.",
            metadata={"lookahead": self.lookahead},
        )


class AdversarialPressureOverlay(BaseOverlay):
    def __init__(self):
        super().__init__("AdversarialPressure", 300)

    def propose(self, obs, intent, memory):
        vulnerability = float(obs.get("opponent_vulnerability", 0.0))
        pressure_action = obs.get("pressure_action")
        if vulnerability <= 0 or pressure_action is None:
            return None
        return OverlayProposal(
            overlay=self.name,
            kind=ProposalKind.MODIFY,
            action=copy.deepcopy(pressure_action),
            priority=self.priority,
            confidence=max(0.0, min(1.0, vulnerability)),
            rationale="Observable opponent vulnerability creates a pressure opportunity.",
            metadata={"vulnerability": vulnerability},
        )


class ReactivePipeline:
    def __init__(
        self,
        base_policy: BasePolicy,
        arbiter: Arbiter,
        recovery: Optional[ExecutionRecovery] = None,
        logger: Optional[logging.Logger] = None,
        history_limit: int = 1000,
    ):
        if history_limit < 1:
            raise ValueError("history_limit must be >= 1")
        self.base_policy = base_policy
        self.arbiter = arbiter
        self.recovery = recovery or DefaultExecutionRecovery()
        self.overlays: List[BaseOverlay] = []
        self.memory = AgentMemory()
        self.history_limit = history_limit
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def add_overlay(self, overlay: BaseOverlay) -> None:
        self.overlays.append(overlay)
        self.overlays.sort(key=lambda o: o.priority)

    def update_state(self, obs: Observation, feedback: Optional[ExecutionFeedback]) -> None:
        if "step" in obs:
            self.memory.step = int(obs["step"])
        else:
            self.memory.step += 1

        if feedback is not None:
            self.memory.last_feedback = copy.deepcopy(feedback)
            self.recovery.recover(feedback, self.memory)

        self.memory.history.append({
            "step": self.memory.step,
            "observation": copy.deepcopy(obs),
            "feedback": copy.deepcopy(feedback),
        })
        if len(self.memory.history) > self.history_limit:
            del self.memory.history[:-self.history_limit]

    def decide(self, obs: Observation, feedback: Optional[ExecutionFeedback] = None) -> ArbitrationResult:
        self.update_state(obs, feedback)
        intent = self.base_policy.propose(obs, self.memory)
        proposals: List[OverlayProposal] = []
        for overlay in self.overlays:
            try:
                # Overlay isolation: an overlay receives its own deep-copied
                # intent so even accidental in-place mutation cannot corrupt
                # the canonical baseline intent or another overlay's view.
                isolated_intent = Intent(
                    action=copy.deepcopy(intent.action),
                    source=intent.source,
                    step=intent.step,
                )
                proposal = overlay.propose(obs, isolated_intent, self.memory)
                if proposal is not None:
                    proposals.append(copy.deepcopy(proposal))
            except Exception as exc:
                self.logger.exception("Overlay '%s' failed at step %s: %s", overlay.name, self.memory.step, exc)
        context = DecisionContext(obs=obs, intent=intent, proposals=tuple(proposals), memory=self.memory)
        return self.arbiter.resolve(context)

    def act(self, obs: Observation, feedback: Optional[ExecutionFeedback] = None) -> Action:
        return copy.deepcopy(self.decide(obs, feedback).action)


def create_agent(trace_data: Sequence[Action]) -> ReactivePipeline:
    engine = ReactivePipeline(
        base_policy=TracePolicy(trace_data),
        arbiter=PriorityArbiter(),
        recovery=DefaultExecutionRecovery(),
    )
    engine.add_overlay(AnticipatoryResourceOverlay(trace_data, lookahead=2))
    engine.add_overlay(AdversarialPressureOverlay())
    engine.add_overlay(CollisionRepairOverlay())
    return engine
