---
title: SupportBench OpenEnv
emoji: "robot"
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
tags:
  - openenv
  - customer-support
  - benchmark
---

# SupportBench

SupportBench is a real-world OpenEnv-style environment for training and evaluating AI agents on customer support triage. The agent handles realistic support tickets by classifying the issue, routing it, drafting a response, and selecting the resolution.

## Motivation

Customer support triage is a real operational workflow used by SaaS teams every day. It is a useful benchmark because strong performance requires policy use, structured decisions, safe escalation, and good response planning.

## Environment API

- `reset(task_id=None) -> SupportBenchObservation`
- `step(action: SupportBenchAction) -> SupportBenchStepResult`
- `state() -> SupportBenchState`

Core implementation: `supportbench/env.py`

## Observation space

Observations include:

- ticket metadata and full customer message
- customer tier
- policy snippets
- available actions
- reply templates
- progress flags
- step count, max steps, last reward, done flag, and error state

## Action space

The typed action model supports:

- `classify`
- `assign`
- `draft_reply`
- `resolve`
- `request_clarification`

Fields cover `category`, `priority`, `queue`, `escalate`, `reply_template`, `reply_text`, `resolution`, and `clarification_question`.

## Tasks

1. `easy_duplicate_charge`
   Duplicate billing charge with a straightforward refund flow.
2. `medium_shipping_delay`
   Delayed replacement shipment requiring logistics routing and recovery.
3. `hard_account_takeover`
   Likely account compromise for a VIP customer requiring urgent security escalation.

## Reward design

Reward is shaped over the full trajectory:

- classification and priority provide partial credit
- routing and escalation provide partial credit
- reply template and required response phrases provide partial credit
- correct final resolution provides final credit
- unnecessary clarification requests apply a penalty

All graders return a deterministic score in `[0.0, 1.0]`.

## Baseline inference

The root-level `inference.py` uses the OpenAI client with:

- `HF_TOKEN` or `OPENAI_API_KEY`
- `API_BASE_URL`
- `MODEL_NAME`

It emits the required `[START]`, `[STEP]`, and `[END]` logs. If no API key is present, it falls back to a deterministic scripted policy for reproducible local scores.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 7860
```

## Docker

```bash
docker build -t supportbench .
docker run -p 7860:7860 supportbench
```

## Hugging Face Spaces

Deploy as a Docker Space and add the `openenv` tag. The app exposes `/`, `/health`, `/tasks`, `/reset`, `/state`, and `/step`.

## Expected baseline scores

The deterministic fallback policy should score `1.00` on all three tasks.
