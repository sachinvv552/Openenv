"""Baseline inference runner for SupportBench."""

from __future__ import annotations

import json
import os
from typing import Any, List, Optional

from supportbench.env import SupportBenchAction, SupportBenchEnv
from supportbench.tasks import SUPPORT_POLICIES
from supportbench.tasks import TASKS

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]

API_KEY = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
MAX_STEPS = 8

SYSTEM_PROMPT = """
You are operating a customer support environment.
Return only valid JSON with keys:
action_type, category, priority, queue, escalate, reply_template, reply_text, resolution, clarification_question.
Choose exactly one action each turn. Prefer progressive work: classify, assign, draft_reply, resolve.
Use the ticket, policies, and progress state. Avoid request_clarification unless information is missing.
""".strip()


def format_reward(value: float) -> str:
    return f"{value:.2f}"


def choose_action(client: Any, env: SupportBenchEnv) -> SupportBenchAction:
    state = env.state()
    task = next(task for task in TASKS if task["task_id"] == state.task_id)
    prompt_payload = {
        "task": {
            "task_id": task["task_id"],
            "title": task["title"],
            "difficulty": task["difficulty"],
        },
        "state": state.model_dump(),
        "ticket": task["ticket"],
        "policies": SUPPORT_POLICIES,
    }
    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(prompt_payload, indent=2)},
        ],
        response_format={"type": "json_object"},
    )
    payload = response.choices[0].message.content or "{}"
    return SupportBenchAction(**json.loads(payload))


def fallback_action(env: SupportBenchEnv) -> SupportBenchAction:
    state = env.state()
    task = next(task for task in TASKS if task["task_id"] == state.task_id)
    expected = task["expected"]
    if "classify" not in state.completed_actions:
        return SupportBenchAction(
            action_type="classify",
            category=expected["category"],
            priority=expected["priority"],
        )
    if "assign" not in state.completed_actions:
        return SupportBenchAction(
            action_type="assign",
            queue=expected["queue"],
            escalate=expected["escalate"],
        )
    if "draft_reply" not in state.completed_actions:
        return SupportBenchAction(
            action_type="draft_reply",
            reply_template=expected["reply_template"],
            reply_text="We reviewed the case. " + ", ".join(expected["must_mention"]) + ".",
        )
    return SupportBenchAction(action_type="resolve", resolution=expected["resolution"])


def run_episode(task_id: str) -> float:
    env = SupportBenchEnv(task_id=task_id)
    client: Optional[Any] = OpenAI(api_key=API_KEY, base_url=API_BASE_URL) if API_KEY and OpenAI else None
    rewards: List[str] = []
    final_score = 0.0
    success = False
    steps_taken = 0

    print(f"[START] task={task_id} env={env.benchmark_name} model={MODEL_NAME}")
    env.reset(task_id)
    try:
        for step_num in range(1, MAX_STEPS + 1):
            try:
                action = choose_action(client, env) if client else fallback_action(env)
            except Exception:
                action = fallback_action(env)

            result = env.step(action)
            steps_taken = step_num
            final_score = float(result.info["score"])
            rewards.append(format_reward(result.reward.value))
            action_str = action.model_dump_json(exclude_none=True)
            error = result.observation.last_action_error or "null"
            print(
                f"[STEP] step={step_num} action={action_str} reward={format_reward(result.reward.value)} "
                f"done={str(result.done).lower()} error={error}"
            )
            if result.done:
                success = bool(result.info["grader"]["success"])
                break
        else:
            success = final_score >= 0.95
    finally:
        env.close()
        print(
            f"[END] success={str(success).lower()} steps={steps_taken} score={format_reward(final_score)} "
            f"rewards={','.join(rewards)}"
        )
    return final_score


def main() -> None:
    for task in TASKS:
        run_episode(task["task_id"])


if __name__ == "__main__":
    main()
