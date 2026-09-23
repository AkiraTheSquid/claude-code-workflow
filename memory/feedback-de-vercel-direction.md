---
name: feedback-de-vercel-direction
description: Seth wants to reduce Vercel dependence (vendor lock-in concern); prefer Fly/portable containers for new services
metadata: 
  node_type: memory
  type: feedback
---

2026-07-12, during co-working spec for [[delta-note]]: Seth said he wants "to get away from Vercel as much as possible" (vendor lock-in) and floated AWS. Claude recommended against AWS for a solo dev (ops tax, unpredictable egress cost — same failure mode as the Supabase 402 incident) and proposed Fly containers as the portable middle path; Seth had not yet confirmed the AWS-vs-Fly call at time of writing.

**Why:** Lock-in + cost predictability matter to him more than platform convenience (see also the no-Vercel-Workflows guardrail in CLAUDE.md).

**How to apply:** For any NEW backend/service, default to a Fly app (portable Docker) over Vercel functions/products. Existing static Vercel deploys (delta-note web, delta-drills, redline-writer) stay put until he asks to migrate — static hosting is portable by nature, no urgency. Don't propose new Vercel-specific surfaces (API routes, KV, queues, etc.) without flagging this preference.
