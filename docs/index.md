---
hide:
  - navigation
  - toc
---

<div class="rg-hero" markdown>

<img src="assets/images/profile-avatar.jpg" alt="originalrgsec" class="rg-hero__avatar">

<p class="rg-hero__tagline">
  Build AI workspaces that remember what you're building and why.
</p>

<p class="rg-hero__sub">
  OWB scaffolds a structured workspace — knowledge vault, context files, development rules, security scanner — from a single command. Then it keeps that workspace current as your projects evolve.
</p>

<div class="rg-hero__actions">
  <a href="getting-started/install/" class="rg-btn rg-btn--primary">Get Started</a>
  <a href="getting-started/why-owb/" class="rg-btn rg-btn--secondary">Why OWB?</a>
</div>

</div>

<div class="rg-section" markdown>

<p class="rg-section__title">The problem is not your model. The problem is context.</p>

<p class="rg-section__desc">
  Modern coding agents are capable. The question is whether they have the information they need to be useful on <em>your</em> projects, across sessions, without you re-explaining everything. OWB solves the context problem by giving you a repeatable structure that persists project state, captures decisions, and surfaces the right information at the right time.
</p>

</div>

<div class="rg-features" markdown>

<div class="rg-feature" markdown>
<div class="rg-feature__icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#D4A017" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg></div>
<div class="rg-feature__title">One-Command Setup</div>
<div class="rg-feature__desc">
<code>owb init</code> generates an Obsidian knowledge vault, personal context files, development rules, and custom skills. An interactive wizard guides first-time users through model selection, vault structure, and security settings. Fifteen minutes from install to a working workspace.
</div>
</div>

<div class="rg-feature" markdown>
<div class="rg-feature__icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#D4A017" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></div>
<div class="rg-feature__title">Three-Layer Security Scanner</div>
<div class="rg-feature__desc">
Every file that enters the workspace — upstream updates, third-party skills, migrated content — runs through structural validation, pattern matching against 42 known attack signatures, and optional LLM-powered semantic analysis. Prompt injection gets caught before it reaches your sessions.
</div>
</div>

<div class="rg-feature" markdown>
<div class="rg-feature__icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#D4A017" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg></div>
<div class="rg-feature__title">Drift Detection and Migration</div>
<div class="rg-feature__desc">
<code>owb diff</code> compares your workspace against the reference and tells you exactly what has drifted. <code>owb migrate</code> brings it up to date with interactive file-by-file review. Your customizations are preserved. Nothing overwrites without your consent.
</div>
</div>

<div class="rg-feature" markdown>
<div class="rg-feature__icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#D4A017" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg></div>
<div class="rg-feature__title">Knowledge Vault</div>
<div class="rg-feature__desc">
An Obsidian vault with 18 note templates, structured project management, a decision index, research pipeline, and session logging. Your agent starts every session by reading a bootstrap file that tells it where each project stands and what to do next. No re-explaining.
</div>
</div>

<div class="rg-feature" markdown>
<div class="rg-feature__icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#D4A017" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg></div>
<div class="rg-feature__title">Model-Agnostic, Vendor-Extensible</div>
<div class="rg-feature__desc">
OWB works with any LLM provider through LiteLLM — Anthropic, OpenAI, Ollama, or anything else that speaks the protocol. Downstream packages depend on OWB as a core library and overlay their own vendor-specific defaults, configuration namespaces, and extensions.
</div>
</div>

<div class="rg-feature" markdown>
<div class="rg-feature__icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#D4A017" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg></div>
<div class="rg-feature__title">Skill Evaluation Pipeline</div>
<div class="rg-feature__desc">
Before a skill enters the workspace, the evaluator classifies it, generates a test suite, runs the tests against both a baseline and the skill-augmented model, and scores across four dimensions. Incorporate/reject decisions are backed by quantitative evidence, not vibes.
</div>
</div>

</div>

<div class="rg-section" markdown>

<p class="rg-section__title">How it works</p>

<p class="rg-section__desc">
  OWB operates across three phases: design the workspace structure once, build it with a single command, and operate it as projects evolve. The tooling handles drift, upgrades, and security continuously so you can focus on the work.
</p>

</div>

<div style="display:flex; justify-content:center; gap:1rem; flex-wrap:wrap; max-width:1000px; margin:2rem auto; padding:0 1rem;">
  <div style="display:flex; flex-direction:column; gap:0.75rem; align-items:center;">
    <div style="background:#D4A017; color:#0A0A14; padding:0.6rem 1.2rem; border-radius:6px; font-weight:600; font-size:0.9rem; font-family:JetBrains Mono,monospace;">owb init</div>
    <div style="color:#D4A017; font-size:1.2rem;">&#x25BC;</div>
  </div>
  <div style="display:flex; flex-direction:column; gap:0.5rem; align-items:center; flex:1; min-width:200px;">
    <div style="background:#12121E; color:#F0F0F0; border:2px solid #D4A017; padding:0.75rem 1.5rem; border-radius:8px; font-weight:600; width:100%; text-align:center;">Workspace</div>
    <div style="display:flex; gap:0.5rem; width:100%; justify-content:center; flex-wrap:wrap;">
      <div style="background:#1B2A4A; color:#F0F0F0; border:1px solid #E8B830; padding:0.5rem 0.75rem; border-radius:6px; font-size:0.85rem; flex:1; text-align:center; min-width:120px;">Knowledge Vault</div>
      <div style="background:#1B2A4A; color:#F0F0F0; border:1px solid #E8B830; padding:0.5rem 0.75rem; border-radius:6px; font-size:0.85rem; flex:1; text-align:center; min-width:120px;">Context Files</div>
      <div style="background:#1B2A4A; color:#F0F0F0; border:1px solid #E8B830; padding:0.5rem 0.75rem; border-radius:6px; font-size:0.85rem; flex:1; text-align:center; min-width:120px;">Dev Rules & Skills</div>
    </div>
  </div>
</div>
<div style="display:flex; justify-content:center; gap:0.75rem; flex-wrap:wrap; max-width:700px; margin:0 auto 2rem; padding:0 1rem;">
  <div style="background:#D4A017; color:#0A0A14; padding:0.45rem 0.9rem; border-radius:6px; font-weight:600; font-size:0.8rem; font-family:JetBrains Mono,monospace;">owb diff</div>
  <div style="background:#D4A017; color:#0A0A14; padding:0.45rem 0.9rem; border-radius:6px; font-weight:600; font-size:0.8rem; font-family:JetBrains Mono,monospace;">owb migrate</div>
  <div style="background:#D4A017; color:#0A0A14; padding:0.45rem 0.9rem; border-radius:6px; font-weight:600; font-size:0.8rem; font-family:JetBrains Mono,monospace;">owb security scan</div>
  <div style="background:#D4A017; color:#0A0A14; padding:0.45rem 0.9rem; border-radius:6px; font-weight:600; font-size:0.8rem; font-family:JetBrains Mono,monospace;">owb eval</div>
</div>

<div class="rg-install" markdown>

<p class="rg-install__title">Start building</p>

```bash
pip install open-workspace-builder
owb init
```

That is the entire setup. The wizard handles the rest.

[Read the first-run guide →](howto-first-run.md){ .rg-btn .rg-btn--primary }

</div>
