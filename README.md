# 🤖 Vera — Merchant Growth Assistant

> **magicpin AI Challenge — Backend Submission**

Vera is a **deterministic-first, LLM-assisted merchant growth assistant** built with FastAPI.

It evaluates merchant and customer context, prioritizes business triggers, generates grounded WhatsApp messages, prevents duplicate outreach, and manages conversation state safely.

The core design principle is simple:

> **Deterministic when it matters. Generative when it helps.**

---

## ✨ Features

- 🎯 **Deterministic trigger prioritization**
- 🧠 **Context-grounded message composition**
- 🤖 **Optional LLM-assisted wording**
- 🛡️ **Strict validation of LLM output**
- 🚫 **Atomic duplicate-message suppression**
- 👤 **Customer-aware messaging**
- 💬 **Positive / unclear / negative intent detection**
- 📵 **WhatsApp auto-reply detection**
- 🔒 **Conversation termination and reactivation protection**
- ⚡ **FastAPI backend**
- 🧪 **API and adversarial regression tests**

---

# 🏗️ Architecture

```text
                 ┌─────────────────────────┐
                 │     Merchant Context    │
                 └────────────┬────────────┘
                              │
                 ┌────────────▼────────────┐
                 │     Customer Context    │
                 └────────────┬────────────┘
                              │
                 ┌────────────▼────────────┐
                 │      Trigger Context    │
                 └────────────┬────────────┘
                              │
                              ▼
              ┌──────────────────────────────┐
              │ Deterministic Trigger Scoring│
              │        & Prioritization      │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │     Grounded Context Packet  │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  Deterministic Composition   │
              │        Safe Baseline         │
              └──────────────┬───────────────┘
                             │
                             ▼
                 ┌────────────────────────┐
                 │    Optional LLM Layer  │
                 └────────────┬───────────┘
                              │
                              ▼
              ┌──────────────────────────────┐
              │      Strict Validation       │
              │ CTA / send_as / suppression  │
              │       / taboo vocabulary     │
              └──────────────┬───────────────┘
                             │
                   ┌─────────┴─────────┐
                   │                   │
                 Valid               Invalid
                   │                   │
                   ▼                   ▼
              Use LLM output      Deterministic
                                      fallback
                   │                   │
                   └─────────┬─────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │     Atomic Suppression       │
              │      & Conversation State    │
              └──────────────┬───────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Final Action   │
                    └─────────────────┘
