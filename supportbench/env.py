"""SupportBench environment implementation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .tasks import REPLY_TEMPLATES, SUPPORT_POLICIES, TASKS, TASK_INDEX


ActionName = Literal["classify", "assign", "draft_reply", "resolve", "request_clarification"]


class Ticket(BaseModel):
    ticket_id: str
    customer_name: str
    channel: str
    subject: str
    message: str
    metadata: Dict[str, Any]


class SupportBenchAction(BaseModel):
    action_type: ActionName
    category: Optional[str] = None
    priority: Optional[str] = None
    queue: Optional[str] = None
    escalate: Optional[bool] = None
    reply_template: Optional[str] = None
    reply_text: Optional[str] = None
    resolution: Optional[str] = None
    clarification_question: Optional[str] = None


class SupportBenchReward(BaseModel):
    value: float = Field(ge=0.0, le=1.0)
    reason: str
    score_breakdown: Dict[str, float] = Field(default_factory=dict)


class SupportBenchObservation(BaseModel):
    benchmark: str
    task_id: str
    difficulty: str
    title: str
    step_count: int
    max_steps: int
    ticket: Ticket
    customer_tier: str
    policies: List[str]
    available_actions: List[str]
    available_reply_templates: Dict[str, str]
    progress: Dict[str, bool]
    last_action_error: Optional[str] = None
    last_reward: float = 0.0
    done: bool = False


class SupportBenchState(BaseModel):
    benchmark: str = "supportbench"
    task_id: str
    step_count: int
    max_steps: int
    done: bool
    cumulative_reward: float
    fields: Dict[str, Any]
    completed_actions: List[str]
    score: float
    last_action_error: Optional[str] = None


class SupportBenchStepResult(BaseModel):
    observation: SupportBenchObservation
    reward: SupportBenchReward
    done: bool
    info: Dict[str, Any]


class SupportBenchEnv:
    benchmark_name = "supportbench"

    def __init__(self, task_id: Optional[str] = None):
        self.task_id = task_id or TASKS[0]["task_id"]
        self._task = deepcopy(TASK_INDEX[self.task_id])
        self._state: Optional[SupportBenchState] = None
        self.reset(self.task_id)

    def reset(self, task_id: Optional[str] = None) -> SupportBenchObservation:
        if task_id is not None:
            self.task_id = task_id
        self._task = deepcopy(TASK_INDEX[self.task_id])
        self._state = SupportBenchState(
            task_id=self.task_id,
            step_count=0,
            max_steps=self._task["max_steps"],
            done=False,
            cumulative_reward=0.0,
            fields={
                "category": None,
                "priority": None,
                "queue": None,
                "escalate": None,
                "reply_template": None,
                "reply_text": None,
                "resolution": None,
            },
            completed_actions=[],
            score=0.0,
            last_action_error=None,
        )
        return self._build_observation(last_reward=0.0)

    def state(self) -> SupportBenchState:
        assert self._state is not None
        return self._state.model_copy(deep=True)

    def step(self, action: SupportBenchAction) -> SupportBenchStepResult:
        assert self._state is not None

        if self._state.done:
            reward = SupportBenchReward(value=0.0, reason="Episode already finished.")
            return SupportBenchStepResult(
                observation=self._build_observation(last_reward=0.0),
                reward=reward,
                done=True,
                info={"score": self._state.score, "grader": self.grade()},
            )

        self._state.step_count += 1
        self._state.last_action_error = None
        pre_score = self.grade()["score"]

        if action.action_type == "classify":
            self._state.fields["category"] = action.category
            self._state.fields["priority"] = action.priority
        elif action.action_type == "assign":
            self._state.fields["queue"] = action.queue
            self._state.fields["escalate"] = action.escalate
        elif action.action_type == "draft_reply":
            self._state.fields["reply_template"] = action.reply_template
            self._state.fields["reply_text"] = action.reply_text
        elif action.action_type == "resolve":
            self._state.fields["resolution"] = action.resolution
        elif action.action_type == "request_clarification":
            self._state.fields["clarification_question"] = action.clarification_question
        else:
            self._state.last_action_error = f"Unsupported action_type: {action.action_type}"

        self._state.completed_actions.append(action.action_type)
        grader = self.grade()
        post_score = grader["score"]
        reward_value = max(0.0, min(1.0, post_score - pre_score))
        reward_reason = "Progress updated based on current ticket handling state."

        if action.action_type == "request_clarification":
            reward_value = 0.0
            reward_reason = "Clarification requests do not help on benchmark tasks with complete information."
        elif self._state.step_count > self._state.max_steps:
            reward_value = 0.0
            reward_reason = "Maximum steps exceeded."

        if self._state.step_count >= self._state.max_steps or (
            action.action_type == "resolve" and grader["score"] >= 0.80
        ):
            self._state.done = True

        self._state.score = grader["score"]
        self._state.cumulative_reward = round(
            min(1.0, self._state.cumulative_reward + reward_value), 4
        )
        reward = SupportBenchReward(
            value=round(reward_value, 4),
            reason=reward_reason,
            score_breakdown=grader["breakdown"],
        )
        observation = self._build_observation(last_reward=reward.value)
        return SupportBenchStepResult(
            observation=observation,
            reward=reward,
            done=self._state.done,
            info={"score": grader["score"], "grader": grader},
        )

    def grade(self) -> Dict[str, Any]:
        assert self._state is not None
        expected = self._task["expected"]
        weights = self._task["grader_weights"]
        fields = self._state.fields
        breakdown: Dict[str, float] = {}

        breakdown["classify"] = (
            weights["classify"]
            if fields["category"] == expected["category"] and fields["priority"] == expected["priority"]
            else weights["classify"] / 2
            if fields["category"] == expected["category"] or fields["priority"] == expected["priority"]
            else 0.0
        )

        breakdown["assign"] = (
            weights["assign"]
            if fields["queue"] == expected["queue"] and fields["escalate"] == expected["escalate"]
            else weights["assign"] / 2
            if fields["queue"] == expected["queue"] or fields["escalate"] == expected["escalate"]
            else 0.0
        )

        reply_match = 0.0
        if fields["reply_template"] == expected["reply_template"]:
            reply_match += weights["reply"] * 0.6
        reply_text = (fields.get("reply_text") or "").lower()
        mentions = expected["must_mention"]
        mention_ratio = sum(1 for term in mentions if term.lower() in reply_text) / len(mentions)
        reply_match += weights["reply"] * 0.4 * mention_ratio
        breakdown["reply"] = round(reply_match, 4)

        breakdown["resolve"] = (
            weights["resolve"] if fields["resolution"] == expected["resolution"] else 0.0
        )

        breakdown["penalty"] = -0.10 if "request_clarification" in self._state.completed_actions else 0.0

        raw_score = sum(breakdown.values())
        score = round(max(0.0, min(1.0, raw_score)), 4)
        success = score >= 0.95
        return {"score": score, "success": success, "breakdown": breakdown}

    def close(self) -> None:
        return None

    def _build_observation(self, last_reward: float) -> SupportBenchObservation:
        assert self._state is not None
        progress = {
            "classified": self._state.fields["category"] is not None and self._state.fields["priority"] is not None,
            "assigned": self._state.fields["queue"] is not None and self._state.fields["escalate"] is not None,
            "replied": self._state.fields["reply_template"] is not None,
            "resolved": self._state.fields["resolution"] is not None,
        }
        return SupportBenchObservation(
            benchmark=self.benchmark_name,
            task_id=self.task_id,
            difficulty=self._task["difficulty"],
            title=self._task["title"],
            step_count=self._state.step_count,
            max_steps=self._state.max_steps,
            ticket=Ticket(**self._task["ticket"]),
            customer_tier=self._task["customer_tier"],
            policies=deepcopy(SUPPORT_POLICIES),
            available_actions=["classify", "assign", "draft_reply", "resolve", "request_clarification"],
            available_reply_templates=deepcopy(REPLY_TEMPLATES),
            progress=progress,
            last_action_error=self._state.last_action_error,
            last_reward=last_reward,
            done=self._state.done,
        )
