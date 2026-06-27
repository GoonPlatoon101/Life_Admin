# CLAUDE.md

This file is the shared working agreement for **everyone contributing to LifeAdmin** — human teammates and Claude Code (claude.ai/code) alike. It captures the product intent, architecture, and conventions so anyone (or any agent) can pick up work without re-deriving context. Where it says "you," it means whoever is making the change.

## Repository State

This repo is **greenfield**. The only tracked files are `README.md`, a Python-oriented `.gitignore`, and this `CLAUDE.md`. There is no source code, no dependency manifest, and no test suite yet — so there are no build/lint/test commands to run until the first code lands.

**The stack is not yet decided.** Two signals conflict and must be reconciled before scaffolding:
- The `.gitignore` is Python-flavored (Django/Flask/Streamlit/pytest/Ruff/uv/poetry).
- The "Recommended Folder Structure" below sketches a TypeScript/Next.js app (`app/`, `prisma/`, `lib/agent/*.ts`).

Do not assume either stack. Agree on the language/framework choice as a team before generating scaffolding, then update this file and align `.gitignore` and the folder structure to the chosen stack.

This is a **nested git repository** inside the Obsidian "Second Brain" vault (`Second Brain/Projects/Life_Admin/`). Run git commands from this directory; vault-level commits do not include changes here. The project is not yet listed in the vault's project tables in the parent `CLAUDE.md` files.

## Purpose


This file gives every contributor the product, architecture, implementation, and coding context for the **LifeAdmin** app.

LifeAdmin is an AI-powered admin dashboard that helps users reduce manual life/work admin by turning scattered email and calendar information into clear, structured, reviewable action items.

The immediate goal is to build a safe, read-only MVP first, then gradually introduce user-approved agent actions such as drafting replies, creating reminders, adding tasks, and suggesting scheduling.

---

## Product Thesis

Users currently waste time manually checking multiple tools to understand what they need to do next.

Important responsibilities are often scattered across:

* Emails that require replies
* Calendar meetings that need preparation
* Deadlines hidden inside email threads
* Follow-up tasks from conversations
* Informative newsletters or announcements
* User preferences and priorities

LifeAdmin should answer:

> “What do I need to pay attention to today?”

The system should not replace the user’s judgment. It should reduce the effort required to find, filter, summarize, and organize admin work.

---

## Core Product Scope

The main dashboard should include:

| Section         | Purpose                                                      |
| --------------- | ------------------------------------------------------------ |
| Todo List       | Tasks extracted from emails, meetings, and user input        |
| Meetings        | Upcoming meetings, preparation notes, and follow-up items    |
| Emails to Reply | Important emails that likely require a user response         |
| News Feed       | Summaries of informative emails, newsletters, and updates    |
| Needs Review    | Items the AI is uncertain about or needs the user to confirm |

---

## High-Level Architecture

```text
User Input / Connected Accounts
        ↓
Agent Orchestrator
        ↓
Email Sync      Calendar Sync      User Preferences
        ↓              ↓                 ↓
Raw Email Data   Meeting Data       Rules / Priorities
        ↓              ↓                 ↓
        └────── Bounded Agentic Loop ──────┘
                       ↓
              Structured Outputs
                       ↓
                  Database
                       ↓
                  Dashboard
                       ↓
             User Review / Approval
                       ↓
              Tool Agent Actions
```

The key design principle is that the agent does not directly act on the user's behalf without review. It extracts, suggests, and prepares actions. The user remains in control.

---

## Bounded Agentic Loop

The central implementation pattern is a **bounded agentic loop**.

```text
Analyze Incoming Item
        ↓
Filter Tool
        ↓
Classification Tool
        ↓
Choose Extraction Path
        ↓
Relevant Extraction Tool(s)
        ↓
Validation Tool
        ↓
Save Structured Output
        ↓
Dashboard
```

If validation fails or confidence is low:

```text
Validation Tool
        ↓
Retry / Refine within max attempts
        ↓
If still uncertain → Needs Review
```

Default limits:

```ts
const AGENT_LOOP_LIMITS = {
  maxToolCallsPerItem: 6,
  maxRetriesPerItem: 2,
  minConfidenceToAutoSave: 0.75,
  minConfidenceToAvoidNeedsReview: 0.85
}
```

Low-confidence items should be saved as `needs_review`, not discarded silently.

---

## Required Agent Tools

| Tool                    | Responsibility                                                                               |
| ----------------------- | -------------------------------------------------------------------------------------------- |
| `filterContent`         | Remove obvious noise and decide whether an item is worth processing                          |
| `classifyContent`       | Classify item as task, meeting, reply-needed, news, deadline, follow-up, noise, or uncertain |
| `extractTasks`          | Extract actionable todo items from source content                                            |
| `extractEmailActions`   | Detect emails that need replies and generate reply guidance                                  |
| `extractMeetingContext` | Extract meeting prep notes, agenda hints, and follow-up tasks                                |
| `extractNewsItems`      | Summarize informative email/newsletter content                                               |
| `validateOutput`        | Validate JSON structure, confidence, source grounding, and required fields                   |
| `saveStructuredOutput`  | Persist validated results to the database                                                    |
| `markNeedsReview`       | Persist uncertain items for user review                                                      |

---

## Human-in-the-Loop Rule

For MVP and early versions:

> The AI may suggest actions, but the user must approve before the system performs sensitive actions.

Do not auto-send emails.
Do not auto-delete emails.
Do not auto-archive emails.
Do not auto-create calendar events.
Do not auto-invite attendees.
Do not silently modify external user data.

Safe pattern:

```text
AI detects item
        ↓
Dashboard shows suggestion
        ↓
User confirms, edits, or dismisses
        ↓
Agent performs approved action
```

---

## Recommended Data Models

Core entities:

* `SourceItem`
* `Task`
* `EmailAction`
* `MeetingInsight`
* `NewsItem`
* `AgentRun`
* `AgentToolCall`

These should support:

* Source tracking
* Confidence scores
* Review states
* User approval status
* Agent debugging
* Tool-call observability

---

## Recommended Folder Structure

```text
/
├── app/
│   ├── dashboard/
│   ├── review/
│   └── api/
│       ├── sync/
│       ├── agent/
│       └── actions/
├── components/
│   ├── dashboard/
│   └── shared/
├── lib/
│   ├── agent/
│   │   ├── orchestrator.ts
│   │   ├── loop.ts
│   │   ├── limits.ts
│   │   ├── types.ts
│   │   └── tools/
│   ├── integrations/
│   ├── db/
│   └── utils/
├── prisma/
├── tests/
├── .env.example
├── README.md
└── CLAUDE.md
```

If the app uses a different stack, preserve the same conceptual separation:

```text
UI
API routes / controllers
Agent orchestrator
Agent tools
Integrations
Database
Tests
```

---

## MVP Plan

### MVP 1: Read-Only Dashboard

Build first:

* Connect or stub email source
* Connect or stub calendar source
* Store raw source items
* Run bounded agentic loop
* Extract tasks
* Detect emails requiring replies
* Extract meeting context
* Summarize informative updates
* Display results in dashboard sections
* Allow user to confirm, edit, dismiss, or mark as reviewed

Do not perform external write actions in MVP 1.

### MVP 2: Drafting Assistant

Add:

* Suggested email replies
* Draft generation
* Meeting preparation notes
* Suggested task priorities
* Suggested reminders

### MVP 3: Approved Tool Actions

Add user-approved actions:

* Create reminders
* Add tasks
* Draft emails
* Send approved email drafts
* Create calendar events
* Archive emails only after explicit approval

---

## Coding Guidelines

When working in this codebase (whether you are a teammate or Claude Code):

1. Inspect existing files before creating new structure.
2. Do not assume the stack if it has already been chosen.
3. Prefer small, composable modules.
4. Keep agent tools separate from UI components.
5. Keep integration code separate from extraction logic.
6. Keep prompts and schemas versioned where possible.
7. Add types for all structured outputs.
8. Add tests for every new agent tool.
9. Do not hide low-confidence AI output; route it to `Needs Review`.
10. Do not implement external write actions unless explicitly approved.
11. Keep the dashboard user-centered and review-first.
12. Update this file when major architecture decisions change.

---

## Definition of Done for MVP 1

MVP 1 is done when:

* The app can ingest email/calendar-like source items from fixtures or read-only integrations
* The bounded agentic loop processes source items
* Tasks, email actions, meeting insights, and news items are stored
* The dashboard displays all major sections
* Users can confirm, edit, dismiss, and review AI-generated items
* Low-confidence items appear in `Needs Review`
* Agent runs and tool calls are logged for debugging
* Tests cover the core agent tools
* No external destructive actions are performed automatically

---

## Product Positioning

LifeAdmin should be positioned as:

> An AI admin dashboard that turns messy email and calendar data into clear, prioritized actions.

The product should feel like a reliable assistant, not an autonomous system that acts without permission.

Start safe, prove value, then add more automation only after user trust is established.
