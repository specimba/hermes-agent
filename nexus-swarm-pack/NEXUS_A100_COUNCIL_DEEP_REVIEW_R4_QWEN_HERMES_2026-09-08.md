# NEXUS A100 / SLM COUNCIL — DEEP REVIEW R4
## Evaluation-Truth Repair + Qwen/Hermes Sandboxed Execution Fabric

**Date:** 2026-09-08  
**Review ID:** `NEXUS-A100-COUNCIL-DEEP-REVIEW-R4-QHERMES-20260908`  
**Class:** Clock-B research / evaluation / model-engineering / execution-fabric advisory  
**Authority:** advisory only  
**Training authority:** none  
**Serving-swap authority:** none  
**Clock-A authority:** none  
**Custody authority:** none  

---

# 0. Executive verdict

The A100 lane should **not** be treated as stalled, and it should **not** be left in a permanently read-only research posture.

The correct phase is:

```text
A100
= GPU / model forge

CURRENT BOTTLENECK
= evaluation truth + model identity + independent verification

QWEN/HERMES
= sandboxed engineering / orchestration / receiver / verification candidate

HF
= mutable exchange + compute/control-plane candidate

NEXUS / AEEG
= authority / mission / consequence adjudication

DSH / Plan B
= observer / independent evidence where admitted
```

The council consensus that another unconstrained training cycle should pause is correct, but the pause must be **bounded by clear exit criteria**. It is not a permanent model-development freeze.

The revised sequence is:

```text
A100-EVAL-REPAIR-00-R4
        ↓
exact serving identity + exact A/B/C/D B1 identities
        ↓
A100-B1-CAUSAL-ABLAT-01
        ↓
A100-L2-EXTERNAL-01
        ↓
A100-HF0-002 (Qwen/Hermes independent receiver)
        ↓
provider council conflict adjudication
        ↓
bounded next training / promotion / quantization decision
```

The Qwen/Hermes lane is worth keeping, but **the current exported workspace is not production-admissible**. It contains stale/false capability claims, success-shaped MCP/A2A stubs, an outdated HF Jobs adapter, obsolete ZeroGPU assumptions, and credential-bearing documentation. The right move is to preserve it as evidence, then rebuild/admit the execution surface around a pinned official Hermes Agent runtime or equivalent hardened harness.

The strongest new architectural recommendation is:

> **Use Qwen/Hermes to prepare and independently verify A100 work without giving it A100 host authority.**

For example:

```text
Qwen/Hermes sandbox
→ receives sanitized eval-harness snapshot
→ patches Wilson/statistics/provenance code
→ emits patch + tests + hashes
→ A100/Cline applies under a separate grant
→ A100 runs heavyweight eval
→ Qwen/Hermes independently receives result artifact from HF
→ verifies byte identity + lightweight statistics
→ independent reviewer/adjudicator accepts or rejects
```

That is useful autonomy without authority laundering.

---

# 1. Evidence set inspected

## 1.1 Google Drive A100/Qwen corpus

The operator-provided Drive folder was enumerated directly.

Key current artifacts include:

```text
NEXUS_A100_PROVIDER_COUNCIL_2026-09-08.zip
NEXUS_SESSION_COMPLETE_20260906.zip
NEXUS_QWEN_HF_SANDBOX_ADVISORY_2026-09-08.zip
qwencoderworkspace1.tar
HFbucketsandOTHERfunctionsSTORAGEa100plan2.txt
B1_DPO_V2_ADVISORY_RECEIPT.json
A100_CLOUDGPU_ASTRA_HANDOFF_REPORT.md
NEXUS_SLM_A100_COUNCIL_ADVISORY_20260908_R2.pdf
```

Observed local hashes after connector download:

```text
NEXUS_A100_PROVIDER_COUNCIL_2026-09-08.zip
SHA-256
a2dc815dcd03c27350673cc6651720eef0e8932c2a16107473c24e7b79356266

NEXUS_QWEN_HF_SANDBOX_ADVISORY_2026-09-08.zip
SHA-256
41fc0221bba5e200b0404c0c8d3377d342410b37a10ec3a7b96a8803f6b4aa12

qwencoderworkspace1.tar
SHA-256
4b2ec671ab4e2ae3dac18c080dff708fe62bc3b7b1cd19a762e5a1a1ffe6278b
```

Both advisory ZIPs passed their internal `SHA256SUMS.txt` checks.

## 1.2 Council reports supplied by operator

Reviewed:

```text
NEXUS_A100_PROVIDER_COUNCIL_DEEP_REVIEW_R3_2026-09-08.md
SHA-256
391fba6c11688a3bc948f1db989cee664a2c8628717e4d774078fc3ab345cb73

NEXUS_OSv2_COUNCIL_E_GROK_A100_2026-09-08.docx
SHA-256
de909e5e9e73793b9456bdf65b03ed26a95e429b07a3f7f1409e5a31b2e795be

NEXUS_A100_PROVIDER_COUNCIL_DEEPDIVE_GLM_ZAI_2026-09-08.md
SHA-256
0e3a4ba865917c65436dfb8dcd8c8eac6b83f6808a63157c5c1d58057bfd2ac6
```

Qwen3.8 MAX council seat was unavailable for this review.

That absence should **not** be filled by pretending the already-informed Qwen sandbox is a blind Round-1 council reviewer. It can instead serve as an engineering/verification worker.

---

# 2. Council synthesis — where the evidence now converges

The V1/V2 reviews, R3, Grok and GLM substantially agree on five high-value points.

## 2.1 Wilson confidence-interval defect

The defect is real.

The affected B1 evaluation code passes integer success counts into a helper that expects a probability/rate. Values above one are clamped, causing mediocre rates to receive intervals corresponding to 100% success.

Independent recomputation:

```text
65/100
= 0.650
Wilson95 ≈ [0.5525, 0.7364]

166/200
= 0.830
Wilson95 ≈ [0.7718, 0.8757]

76/100
= 0.760
Wilson95 ≈ [0.6677, 0.8331]

52/100
= 0.520
Wilson95 ≈ [0.4232, 0.6154]

11/40
= 0.275
Wilson95 ≈ [0.1611, 0.4284]

40/40
= 1.000
Wilson95 ≈ [0.9124, 1.0000]
```

Required API:

```python
wilson_from_counts(k, n)
```

Historical point estimates may remain valid where computed separately.

Historical affected CI fields must be marked:

```text
SUPERSEDED_METRIC_FIELD
```

not deleted.

## 2.2 The `0.65 / 0.83` B1 F7 result is a composite result

The treatment evaluated by `b1_f7_holdout_01.py` is:

```text
b1_merged_v2_dpo
+
b1_lora_v1_rebalanced
+
merge_and_unload
```

Therefore:

```text
JBB benign over-refusal = 0.65
OR-Bench over-refusal   = 0.83
```

belongs to the composite.

It is not a clean measurement of:

```text
b1_merged_v2_dpo alone
```

and not a clean measurement of:

```text
b1_lora_v1_rebalanced alone
```

## 2.3 Current B1 serving identity is not sufficiently receipted

Later continuity reports:

```text
8767 = b1_lora_v1_rebalanced
```

Earlier handoff material reports:

```text
8767 = b1_merged_v0
```

One newer council text uses wording that can be read as “v0 still on 8767.”

This is not a model-performance problem.

It is an identity/provenance problem.

Before any serving mutation:

```text
A100-LIVE-IDENTITY-00
```

must record:

```text
process start time
health result
base artifact identity
adapter identity
load/merge mode
dtype
tokenizer/chat-template identity
generation config
artifact hashes
```

No restart or swap should occur before this receipt.

## 2.4 A100-HF0-001 remains PARTIAL

A100 successfully demonstrated part of the HF transport path, but the intended binary/Xet round trip was not independently closed from the A100 environment.

The correct closure experiment is cross-environment:

```text
A100 writer
→ synthetic binary
→ SHA256_A
→ HF bucket

Qwen/Hermes receiver
→ separate environment
→ separate read credential
→ exact object read
→ SHA256_B

require:
SHA256_A == SHA256_B
```

If PASS:

```text
CROSS-ENVIRONMENT TRANSPORT / CONTENT PARITY
= VERIFIED
```

Still not:

```text
CUSTODY
IMMUTABILITY
SCIENTIFIC ACCEPTANCE
```

## 2.5 Another unconstrained training cycle is premature

This is not because A100 is incapable.

It is because the current oracle has:

```text
known CI defects
model-identity ambiguity
contaminated utility probes
judge weakness
benchmark reuse / contamination risk
serving-state drift
```

A new training epoch before repairing those defects would create more artifacts without proportionally increasing knowledge.

---

# 3. R4 council adjudication — use four B1 arms, not another ambiguous “v0 vs v2”

The prior reports differ slightly on the next B1 comparison.

One formulation proposes a bounded v0-vs-v2 F7 holdout.

That is useful as a diagnostic, but it does not solve the current causal ambiguity.

R4 therefore adopts the four-object design:

```text
A = b1_merged_v0

B = frozen factory
    + b1_lora_v1_rebalanced

C = b1_merged_v2_dpo

D = b1_merged_v2_dpo
    + b1_lora_v1_rebalanced
```

The core question is not:

```text
is "v2" better?
```

It is:

```text
what changed behavior:
rebalanced SFT/LoRA?
DPO-v2?
their interaction?
```

Run all four subjects through the same harness.

Required continuity/diagnostic slices:

```text
JBB benign
JBB harmful
OR-Bench diagnostic slice
ISM diagnostic set
```

Required fresh slices:

```text
fresh substantive utility
blind_test_next
```

The final hidden set must not be inspected by the training or harness-patching worker before claim freeze.

Paired prompts require paired statistics.

Report:

```text
absolute rate
Wilson interval from counts
absolute delta
discordant-pair ledger
exact McNemar result for predeclared comparisons
all disagreement examples
semantic/manual adjudication status
```

The lexical refusal marker can remain a deterministic feature.

It must not remain the sole final oracle.

---

# 4. L2 adjudication

The strongest external L2 result remains materially weaker than the same-generation/self-play results.

Current evidence supports:

```text
L2-v4 external:
recall ≈ 0.64
FPR    ≈ 0.36
BAcc   ≈ 0.64
```

Later L2-v6 evidence indicates:

```text
recall ≈ 0.62
FPR    ≈ 0.29
BAcc   ≈ 0.665
```

This is an operating-point tradeoff.

It is not proof that v6 is universally better.

L2-v5 does not yet have the equivalent frozen external result in the current ledger.

Therefore:

```text
A100-L2-EXTERNAL-01
```

should compare:

```text
v4
v5
v6
```

on the same frozen external set.

Required metrics:

```text
recall
FPR
specificity
precision
balanced accuracy
AUROC
AUPRC
Brier score
reliability / calibration
latency
memory
```

Threshold calibration data and final test data must be separate.

---

# 5. Qwen/Hermes lane — independent audit of the actual exported workspace

The Qwen lane is more useful than a generic council seat because it can become a second execution environment.

But its current workspace is **pre-admission**.

## 5.1 Useful proven properties

The Qwen advisory reports:

```text
sandbox package installation
= PASS

pip / venv / curl / git
= PASS

HF authenticated read
= PASS

HF bucket discovery
= PASS

owned bucket upload
= PASS

owned dataset repository creation
= PASS

split ML runtime / HF admin environment
= PASS
```

This is enough to justify further experimentation.

It is not enough to call the bridge production-ready.

## 5.2 Credential hygiene defect

The exported tar contains:

```text
.env
```

as an untracked file.

More importantly, a value-suppressing scan found credential-shaped literals in multiple tracked Markdown/status files.

No credential values are reproduced in this report.

Disposition:

```text
QWEN_WORKSPACE_ARCHIVE
= SECRET-BEARING UNTIL SCRUBBED

PUBLICATION / REUSE
= HOLD

ANY STILL-ACTIVE EXPOSED CREDENTIAL
= ROTATE / REVOKE BEFORE PRODUCTION-LIKE USE
```

The archived artifact should remain available as forensic evidence.

Create a separate scrubbed derivative for continuing engineering.

## 5.3 Current bridge contains success-shaped stubs

The inspected `hf_nexus_bridge.py` contains:

```text
_log_to_mcp()
→ prints "[MCP LOG]"
→ does not perform a real MCP effect

delegate_to_agent()
→ creates local task payload
→ returns status="published"
→ no remote publish / retrieval / ACK proved

run_remote_job()
→ uses an unvalidated/outdated command construction

self.cli_path
→ hard-coded "hf"
```

This contradicts the lane's own split-environment invariant requiring a dedicated HF admin CLI.

Therefore:

```text
CURRENT_CUSTOM_BRIDGE
= SCAFFOLD

MCP_AUDIT_EFFECT
= NOT IMPLEMENTED

A2A_PUBLICATION
= NOT IMPLEMENTED

HF_JOB_ADAPTER
= NOT VALIDATED

PRODUCTION_BRIDGE
= REJECT
```

## 5.4 Current docs contain stale capability claims

The workspace contains statements such as:

```text
HF Pro required for owned bucket writes
production-ready
zero-a10g / zero-a100
```

The newer Qwen advisory already supersedes much of this.

These old files should not be deleted; mark them historical/stale.

## 5.5 Dangerous evidence-retention behavior

`checkpoint_backup()` implements rolling deletion of older bucket objects.

That may be acceptable for explicitly designated scratch checkpoints.

It is unacceptable as a default for:

```text
evidence
receipts
evaluation outputs
sealed artifacts
```

HF Buckets are mutable and non-versioned.

Therefore:

```text
ROLLING_DELETE
= SCRATCH CLASS ONLY

EVIDENCE CLASS
= NO AUTOMATIC DELETE
```

---

# 6. Official Hermes Agent changes the recommendation

The current Qwen workspace contains a custom “Hermes” scaffold.

There is now a much stronger option: use the current official Nous Research Hermes Agent as the execution harness, or make the custom bridge conform to its stronger primitives.

Current official Hermes Agent supports:

```text
multiple model providers
custom OpenAI-compatible endpoints
Qwen OAuth
Hugging Face provider
MCP servers
per-server MCP tool filtering
toolsets
subagent delegation
Docker / remote / cloud terminal backends
memory and skill write gates
provider fallback
```

This makes it a credible *harness candidate*.

It does not make Hermes a NEXUS authority.

Most importantly, Hermes' own security documentation states that the real security boundary for adversarial model actions is **OS-level isolation**, not an in-process approval heuristic.

That maps well to NEXUS doctrine:

```text
Hermes approvals / scanners
= defense-in-depth

OS/container/cloud sandbox
= effect boundary

NEXUS MissionGrant / CapabilityTicket
= authority

effect receipt
= evidence

independent acceptance
= acceptance
```

---

# 7. Recommended Qwen/Hermes execution topology

Do not make Qwen/Hermes one giant all-powerful agent.

Use role-separated sessions/environments.

```text
                    NEXUS / AEEG
                       │
                TaskEnvelope / Grant
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
     HERMES-Q-BUILD       HERMES-Q-HF-RX
     sandboxed code        receiver/witness
     worker                lane
             │                   │
             ▼                   ▼
       patch/tests          HF object read
       no A100 host         exact hash
             │                   │
             └─────────┬─────────┘
                       ▼
                    A100
                  GPU FORGE
          train / heavy eval / serve
                       │
                       ▼
                  HF A1 staging
                       │
                       ▼
                independent review
                       │
                       ▼
                NEXUS accept/reject
```

## `HERMES-Q-BUILD`

Purpose:

```text
eval-harness repair
provenance tooling
lightweight code
test generation
reproduction
```

Capabilities:

```text
sandbox workspace write
no A100 filesystem
no production NEXUS filesystem
no broad HF write credential
network deny by default
```

Input should be a sanitized source snapshot.

Output:

```text
patch
tests
manifest
hashes
run receipt
```

## `HERMES-Q-HF-RX`

Purpose:

```text
A100-HF0 independent receiver
artifact hash witness
metadata census
```

Capabilities:

```text
HF read-only/fine-grained credential
ephemeral download workspace
no HF write
no delete
no A100 access
no arbitrary model/dataset execution
```

This role must not be the same process that wrote the object.

## `HERMES-Q-RESEARCH`

Purpose:

```text
provider docs
HF capability research
tool/API drift checks
```

Capabilities:

```text
web
no consequential HF writes
no A100 mutation
```

## Why separate sessions rather than only subagents?

Hermes subagents can inherit parent capabilities.

For high-confidence experiments, the parent session itself should be minimally provisioned.

Do not give a coordinator:

```text
web + terminal + HF write + NEXUS write + secrets
```

and assume children will create meaningful independence.

---

# 8. Hermes reproducibility profile for NEXUS

Hermes is deliberately self-improving.

That is useful for general productivity.

It is dangerous for controlled experiments if the harness changes itself between runs.

For NEXUS scientific/evidence runs:

```text
Hermes version
= PINNED

model/provider
= PINNED

fallback provider
= DISABLED unless explicitly part of experiment

toolsets
= PINNED

MCP include/exclude list
= PINNED

memory writes
= DISABLED
  or approval-gated

skill writes
= approval-gated / disabled

background self-improvement
= must not silently alter experiment state

container image
= PINNED

config hash
= RECEIPTED
```

This creates:

```text
HERMES-EXPERIMENT-PROFILE
```

distinct from:

```text
HERMES-GENERAL-PRODUCTIVITY-PROFILE
```

---

# 9. Qwen3.8 execution options

Current Qwen3.8-27B is suitable for this engineering role.

The official open-weight model reports:

```text
27B dense
Apache-2.0
262K native context
extendable to ~1M with YaRN
coding / agentic focus
```

The currently available Groq-hosted route reports approximately:

```text
131K hosted context
tool use
JSON / schema modes
reasoning control
high throughput
```

Do not conflate:

```text
official model capability
```

with:

```text
provider-hosted runtime limits
```

Each receipt must record both:

```text
MODEL_ID
PROVIDER
CONTEXT_LIMIT_EFFECTIVE
TOOL_USE_MODE
REASONING_MODE
```

The unavailable Qwen3.8 MAX council surface is therefore **not a blocker** for the engineering lane.

For scientific council independence, however, the already-informed sandbox should not be retroactively called a blind Round-1 Qwen seat.

---

# 10. Hugging Face: keep the advantages, tighten the threat model

HF remains highly useful:

```text
Buckets
= high-throughput mutable object exchange

Repositories
= versioned model/dataset/code publication

Jobs
= managed compute when billing/credit state permits

Sandboxes
= interactive isolated compute candidate

ZeroGPU
= dynamic Gradio GPU allocation
```

But these planes must not be conflated.

## 10.1 Storage Buckets

Current HF documentation describes Buckets as:

```text
S3-like
Xet-backed
mutable
non-versioned
```

Therefore:

```text
HF BUCKET
= A1 WORKING / EXCHANGE PLANE

!= R0 CUSTODY
```

## 10.2 Jobs and Sandboxes

Current HF Jobs require an authenticated account with a positive credit balance.

Current HF Sandboxes are built on Jobs and are explicitly experimental.

HF warns that shared sandboxes are for the same trust boundary and do not guarantee protection from every cross-sandbox attack.

Therefore:

```text
HF SANDBOX
= promising HERMES-Q substrate
= NOT admitted by documentation alone

dedicated sandbox
> shared sandbox
```

If billing blocks Jobs/Sandboxes, continue the existing browser/container sandbox lane instead of attempting a bypass.

## 10.3 ZeroGPU

Current ZeroGPU uses dynamic Blackwell-class allocations with:

```text
large  = 48 GB
xlarge = 96 GB
```

and is Gradio-oriented.

Do not model it as:

```text
zero-a10g
zero-a100
general-purpose shell worker
```

Use it for bounded inference/demos, not as the Hermes orchestration kernel.

---

# 11. New R4 security finding — HF data/model content must be treated as hostile input

The July 2026 Hugging Face security disclosure materially strengthens the case for strict data-plane isolation.

HF reported an autonomous-agent-driven intrusion that began through malicious dataset-processing paths, including local-file disclosure and template-driven code execution, followed by credential theft and lateral movement.

For NEXUS, the lesson is not:

```text
do not use HF
```

It is:

```text
HF CONTENT
!= TRUSTED JUST BECAUSE IT IS ON HF
```

Create:

```text
HF-CONTENT-QUARANTINE-00
```

Rules:

1. pin source owner/repo/revision;
2. record hashes before execution/loading;
3. prefer data-only formats:
   - JSON/JSONL
   - Parquet
   - safetensors;
4. do not load unknown pickle checkpoints in privileged environments;
5. do not enable arbitrary remote code for unknown model/dataset repos;
6. process unknown datasets in a credential-poor dedicated sandbox;
7. never expose broad HF/A100/NEXUS credentials to an untrusted dataset-processing worker;
8. treat README/model-card/dataset text as untrusted data, not executable instructions;
9. do not let the same worker both ingest unknown content and hold evidence/custody authority.

This is especially important for a self-directed Hermes/Qwen worker because autonomous tooling increases the speed at which one poisoned artifact can influence subsequent actions.

---

# 12. Credential architecture

Current HF guidance recommends:

```text
one token per app/use
fine-grained tokens for production-like usage
```

Adopt:

```text
A100-HF-WRITE
= writer credential
= only required bucket/repo scope

QWEN-HF-RECEIVER-READ
= read-only/fine-grained
= exact receiving objects only where possible

HERMES-Q-RESEARCH
= no HF write token

HERMES-Q-BUILD
= no HF production token
```

Never share:

```text
A100 writer token
```

with:

```text
Qwen receiver
```

or the independent-receiver claim becomes much weaker.

Avoid forwarding credentials into Hermes containers unless the task strictly requires them.

Hermes' own documentation warns that forwarded environment variables become readable by commands inside the container.

---

# 13. `A100-EVAL-REPAIR-00-R4`

This should be the next A100 mutation mission.

```text
CLASS
CLOCK-B
EVAL HARNESS / IDENTITY / PROVENANCE REPAIR

NO MODEL TRAINING
NO SERVING SWAP
NO QUANTIZATION
NO ROUTER CHANGE
NO CLOCK-A EFFECT
```

Required:

```text
1. wilson_from_counts(k,n)
2. unit tests:
   0/100
   65/100
   76/100
   100/100
   11/40
   40/40
   166/200

3. mark old broken CI fields SUPERSEDED

4. correct shipgate result-path provenance

5. correct OR-Bench sample-size documentation:
   actual current slice = 200 where code uses [:200]

6. exact A/B/C/D model identity receipts

7. live 8767 identity receipt BEFORE any restart/swap

8. prompt contamination ledger:
   training
   SFT
   DPO
   distillation
   prior eval
   current diagnostic
   blind/final

9. evaluator version/identity receipt

10. no training
```

Recommended implementation split:

```text
Qwen/Hermes sandbox
→ independently prepare patch + tests

A100/Cline
→ review/apply patch to canonical Clock-B eval tree

A100
→ run repaired tests

Qwen/Hermes
→ independently recompute known statistical fixtures

V3/council
→ adjudicate receipt
```

This avoids having the same worker write, execute and accept every repair.

---

# 14. `A100-B1-CAUSAL-ABLAT-01`

Preconditions:

```text
EVAL_REPAIR_R4
= PASS

A/B/C/D identities
= PASS

SERVING_IDENTITY
= PASS

CONTAMINATION_LEDGER
= PASS
```

Subjects:

```text
A = b1_merged_v0
B = rebalanced LoRA effective model
C = b1_merged_v2_dpo
D = C + rebalanced LoRA composite
```

Run identical generation settings.

Evaluation layers:

```text
L1 deterministic lexical signal
L2 structured semantic adjudicator
L3 manual review
```

Mandatory manual review:

```text
all A/B/C/D disagreements
all lexical-vs-semantic disagreements
all ambiguous semantic cases
random agreement sample
```

Do not use the subject model as its own final semantic judge.

No automatic promotion.

---

# 15. `A100-HF0-002-QH`

Purpose:

```text
close the current transport/readback gap
using a genuinely separate execution environment
```

Writer:

```text
A100
generate synthetic random binary
record size
record SHA256_A
upload exact object
record remote object path
STOP
```

Receiver:

```text
HERMES-Q-HF-RX
separate environment
separate read-only token
download exact object as bytes
do not execute / parse as model
record size
record SHA256_B
STOP
```

Adjudicator:

```text
A == B
size_A == size_B
path identity exact
```

Optional reverse-direction control is useful, but should not be required to close the specific A100-upload/Qwen-readback hypothesis.

Claim ceiling:

```text
REMOTE ACCEPTANCE
+
SECOND-ENVIRONMENT READBACK
+
BYTE/HASH PARITY
```

not custody.

---

# 16. Council protocol refinement

Retain the provider council's blind Round-1 principle.

Do not give Round-1 reviewers the synthesis report as their primary evidence.

Round 1:

```text
raw frozen evidence
neutral manifest
common questions
role-specific remit
```

Round 2:

```text
sealed Round-1 reports
prior advisories
conflict matrix
```

The current Qwen sandbox is already informed by the advisory program.

Therefore:

```text
QWEN SANDBOX
= useful engineering worker now

QWEN SANDBOX
!= blind Council-D seat for this already-started round
```

When a fresh Qwen reviewer becomes available, give it the raw neutral pack only.

---

# 17. ACCEPT / HOLD / REJECT

| Item | R4 disposition | Reason |
|---|---|---|
| Evaluation-repair-first order | **ACCEPT** | Known oracle defects |
| Wilson repair | **ACCEPT / P0** | Independently confirmed |
| Live 8767 identity probe | **ACCEPT / P0** | Serving state disputed |
| Four-arm A/B/C/D B1 ablation | **ACCEPT** | Resolves causal identity |
| Generic “v0 vs v2” as final causal test | **HOLD** | Too ambiguous alone |
| L2 v4/v5/v6 same-set external eval | **ACCEPT** | Missing comparable evidence |
| A100-HF0-002 via Qwen | **ACCEPT** | Strong second-environment receiver |
| Qwen/Hermes as A100 host writer | **REJECT** | Collapses boundary |
| Qwen/Hermes as sandbox patch worker | **ACCEPT** | Functional and bounded |
| Current custom Hermes bridge as production | **REJECT** | Fake MCP/A2A + stale adapters |
| Official Hermes Agent as experimental harness | **ACCEPT FOR ADMISSION** | Mature tool/provider/isolation primitives |
| Hermes smart approvals as NEXUS authority | **REJECT** | In-process heuristic |
| Hermes Docker/dedicated sandbox as effect boundary | **ACCEPT CANDIDATE** | OS-level isolation model |
| Automatic provider fallback in eval runs | **REJECT** | Breaks runtime identity |
| Hermes memory/skill auto-mutation in eval runs | **REJECT** | Breaks reproducibility |
| HF Bucket as custody | **REJECT** | Mutable/non-versioned |
| HF Sandbox as guaranteed isolation | **REJECT** | Experimental; documented caveats |
| ZeroGPU as general orchestration host | **REJECT** | Dynamic Gradio GPU plane |
| New B1/L2 training now | **HOLD** | Until R4 repair + discriminative eval |
| Training forever | **REJECT** | Functionality requires bounded iteration |
| Quantization now | **HOLD** | Downstream of model selection/parity |
| Qwen as council authority | **REJECT** | Worker/reviewer only |
| Qwen as second-infra hash witness | **ACCEPT WITH CLAIM CEILING** | Useful but not custody |

---

# 18. Immediate sequence

```text
P0-A
QWEN-HERMES-HYGIENE-00
= preserve original archive
= scrub derivative
= rotate/revoke still-active exposed creds
= remove stale success claims from active front page

P0-B
HERMES-Q-ADMISSION-00
= pinned official Hermes runtime
= dedicated container/sandbox
= memory/skill mutation disabled/gated
= fallback disabled
= minimal toolset
= no broad credential forwarding

P0-C
A100-EVAL-REPAIR-00-R4
= patch + identity + provenance

P0-D
A100-LIVE-IDENTITY-00
= identify 8767 before mutation

P1
A100-B1-CAUSAL-ABLAT-01

P1 parallel
A100-L2-EXTERNAL-01

P1 parallel
A100-HF0-002-QH

P2
provider conflict matrix
+ operator adjudication

P3
bounded next training/promotion/quantization grant
```

No new architecture epoch is required.

This is a repair-and-execution epoch.

---

# 19. Claim ceiling after R4

```text
A100 is a functioning research/model-forge lane
= SUPPORTED

A100 evaluation oracle is currently trustworthy end-to-end
= NO

Wilson CI bug exists
= SUPPORTED / independently recomputed

rebalanced B1 improves tested harmful-refusal behavior
= SUPPORTED on existing harness

rebalanced B1 is strictly better overall
= REJECTED

composite B1 shows promising F7 movement
= SUPPORTED AS DIAGNOSTIC POINT ESTIMATES

DPO-v2 alone caused F7 movement
= NOT ESTABLISHED

current 8767 object
= LATEST REPORTED, NOT YET FRESHLY SEALED IN R4

A100-HF0-001 complete
= NO

Qwen sandbox can read/write owned HF resources
= SUPPORTED by lane receipts

current custom Qwen/Hermes bridge is production-ready
= NO

Qwen/Hermes can become a useful sandboxed implementation/verification worker
= STRONGLY RECOMMENDED EXPERIMENT

Qwen/Hermes can be NEXUS authority
= NO

HF Bucket is evidence custody
= NO

HF Sandboxes are useful isolation candidates
= YES, EXPERIMENTAL

new model training should never resume
= NO

new model training should wait until evaluation repair
= YES
```

---

# 20. Deep-search source register

High-quality current sources checked for R4:

1. **Nous Research — Hermes Agent documentation**
   - https://hermes-agent.nousresearch.com/docs/
   - current architecture, providers, MCP, subagents, toolsets, memory/skills, security

2. **Nous Research — Hermes security**
   - https://hermes-agent.nousresearch.com/docs/user-guide/security
   - OS/container boundary; approvals; credential forwarding; isolation

3. **Nous Research — Hermes SECURITY.md**
   - https://github.com/NousResearch/hermes-agent/blob/main/SECURITY.md
   - explicit statement that OS-level isolation is the security boundary against an adversarial LLM

4. **Nous Research — MCP**
   - https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
   - per-server filtering and environment isolation

5. **Nous Research — providers**
   - https://hermes-agent.nousresearch.com/docs/integrations/providers/
   - Qwen/HF/custom providers and routing

6. **Nous Research — subagent delegation**
   - https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation
   - isolated child contexts / terminal sessions; capability inheritance

7. **Nous Research — memory and skills**
   - https://hermes-agent.nousresearch.com/docs/user-guide/features/memory/
   - https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/
   - self-improvement and write-approval gates

8. **Qwen3.8 official repository**
   - https://github.com/QwenLM/Qwen3.8
   - Qwen3.8-27B release, open weights

9. **Qwen3.8-27B model repository**
   - https://github.com/AlibabaCloud-Official/Qwen3.8-27B
   - 27B dense, Apache-2.0, 262K native context, YaRN extension

10. **Groq Qwen3.8-27B**
    - https://console.groq.com/docs/model/qwen/qwen3.8-27b
    - hosted context/runtime/tool capabilities

11. **Hugging Face Storage Buckets**
    - https://huggingface.co/docs/hub/storage-buckets
    - mutable, non-versioned, Xet-backed

12. **Hugging Face Jobs**
    - https://huggingface.co/docs/huggingface_hub/guides/jobs
    - managed Jobs and positive-credit requirement

13. **Hugging Face Sandboxes**
    - https://huggingface.co/docs/huggingface_hub/guides/sandbox
    - experimental isolation, dedicated-sandbox guidance

14. **Hugging Face ZeroGPU**
    - https://huggingface.co/docs/hub/spaces-zerogpu
    - Blackwell-backed large/xlarge dynamic allocation

15. **Hugging Face token guidance**
    - https://huggingface.co/docs/hub/security-tokens
    - token-per-app and fine-grained token recommendations

16. **Hugging Face July 2026 security disclosure**
    - https://huggingface.co/blog/security-incident-july-2026
    - autonomous-agent intrusion through dataset-processing surface

17. **Hugging Face technical incident timeline**
    - https://huggingface.co/blog/agent-intrusion-technical-timeline
    - dataset config local-file disclosure and template-code-execution vectors

18. **Hugging Face safetensors / model loading**
    - https://huggingface.co/docs/transformers/models
    - safer weight-loading preference

19. **NIST AITE**
    - https://www.nist.gov/news-events/news/2026/07/announcing-nists-artificial-intelligence-technology-evaluation-aite
    - blind/sequestered evaluation rationale

---

# 21. Final freeze

```text
NEXUS_A100_R4
= REVIEW_COMPLETE

A100 PHASE
= EVALUATION-TRUTH REPAIR
+ BOUNDED EXECUTION-FABRIC EXPANSION

NEW TRAINING
= HOLD UNTIL REPAIR + DISCRIMINATIVE EVAL

QWEN/HERMES
= ACCEPT AS EXPERIMENTAL SANDBOXED WORKER FABRIC

CURRENT CUSTOM HERMES BRIDGE
= NOT PRODUCTION-ADMITTED

OFFICIAL HERMES
= ADMISSION CANDIDATE

QWEN MAX COUNCIL ABSENCE
= NOT A BLOCKER

QWEN3.8-27B ENGINEERING ROLE
= AVAILABLE THROUGH OTHER CURRENT ROUTES

A100-HF0
= PARTIAL
= QWEN/HERMES RECEIVER RECOMMENDED

HF BUCKET
= MUTABLE A1
= NOT CUSTODY

HF CONTENT
= UNTRUSTED INPUT UNTIL ADMITTED

NEXT
= QWEN-HERMES-HYGIENE-00
+ HERMES-Q-ADMISSION-00
+ A100-EVAL-REPAIR-00-R4
```

The strategic conclusion is:

> **Do not choose between “safe research” and “useful implementation.” Use role-separated execution surfaces. A100 should remain the GPU forge; Qwen/Hermes should become a sandboxed implementation/verification fabric; HF should remain a mutable exchange/compute plane; NEXUS/AEEG should remain the authority. This preserves functionality while increasing, rather than weakening, evidentiary independence.**
