# SpendGuard Landing Page

## Original problem statement
Build ONLY the SpendGuard landing page first, then refine it into a premium, minimal, cinematic fintech product-launch experience. SpendGuard is an evidence-driven trust layer for autonomous AI payments that evaluates Authority, Intent, Evidence, and Behavior before producing ALLOW / VERIFY / BLOCK decisions. The experience must remain unmistakably SpendGuard, preserve existing behavior, and avoid becoming a dashboard.

## User personas
- Fintech or AI-product buyer evaluating whether SpendGuard feels credible and enterprise-ready.
- Technical evaluator checking whether the trust model is understandable before requesting a product demo.
- Prospective customer encountering autonomous-payment risk for the first time.

## Core requirements
- Frontend-only landing page; no live demo API or backend changes.
- Preserve all existing routes, CTA behavior, integrations, demo flows, test IDs, and SpendGuard logic.
- Navigation: SpendGuard; Product; How it works; Trust; Demo; Open Console →.
- Sections: spacious trust-orbit hero; problem statement; four horizontal trust checks; Sony WH-1000XM6 live decision; RTX 4060/3050 evidence conflict; premium Trust Receipt; vertical observability timeline; isolated count-up metrics; final autonomy/control CTA.
- Near-black/midnight palette, ivory text, muted gray secondary text, restrained violet/indigo accents, subtle atmosphere, editorial serif headlines, modern sans UI text, responsive behavior, and reduced-motion support.

## Architecture decisions
- React/CRACO frontend remains the application stack.
- Existing Framer Motion package is used only for scroll reveals and subtle hero parallax; ambient motion is CSS.
- Single-page anchor navigation remains intact; Open Console preserves its previous in-page destination.
- Client-side jsPDF generates the sample Trust Receipt PDF; no backend or storage integration is used.
- No backend, MongoDB, Gemini, authentication, or third-party API integration was added.

## Implemented
- 2026-07: Initial cinematic SpendGuard landing page and passing baseline frontend validation.
- 2026-07: Premium minimal redesign with fewer panels, stronger whitespace, editorial hierarchy, restrained violet accents, trust-orbit hero, chaptered storytelling, editorial marquee, count-up metrics, and calmer product preview.
- 2026-07: Interactive Sony purchase replay from Purchase Request through Authority, Intent, Behavior, and Evidence, ending in the evidence-conflict BLOCKED decision.
- 2026-07: Downloadable polished sample Trust Receipt PDF with intent, selected product, transaction details, four trust checks, final VERIFY decision, reason, and observable decision trail.
- 2026-07: Scenario Library comparing ALLOW, VERIFY, and BLOCK outcomes through the same four-check evaluation model.
- 2026-07: Concise founder note explaining evidence-backed autonomy before the final CTA.
- 2026-07: Reveal component forwards test IDs and other props correctly.

## Verification
- Production frontend build passes after Scenario Library and Founder Note additions.
- Desktop and mobile screenshots checked; no horizontal overflow.
- Sony replay verified through Purchase Request, Authority, Intent, Behavior, Evidence, and final BLOCKED state.
- Scenario Library verified for ALLOW, VERIFY, and BLOCK; reduced-motion mode jumps directly to each final state.
- Receipt PDF download still works as spendguard-trust-receipt-000184.pdf; PDF content analysis previously confirmed all required fields and the eight-event decision trail.
- Open Console still reaches the existing in-page console preview; Gemini remains unimplemented by user choice.
- Standalone ESLint was not run because the starter project has no ESLint v9 configuration file.

## Prioritized backlog
- P0: None for the current landing-page scope.
- P1: Connect Open Console to a real console experience only when that product scope is requested.
- P1: Gemini decision explanations remain explicitly out of scope unless the user reverses the current decision.
- P2: Receipt Image export remains intentionally deferred by the user.

## Next tasks
- Keep the landing page frontend-only unless the user asks for a live demo API.
- Build the internal console as a separate experience only when explicitly requested.
- Preserve the current Open Console destination and behavior until a real console exists.