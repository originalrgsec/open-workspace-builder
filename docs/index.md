---
hide:
  - navigation
  - toc
---

<div class="vx-hero" markdown>

<img src="assets/images/logo-white.png" alt="Volcanix" class="vx-hero__logo">

<p class="vx-hero__tagline">
  Build AI workspaces that remember what you're building and why.
</p>

<p class="vx-hero__sub">
  OWB scaffolds a structured workspace — knowledge vault, context files, development rules, security scanner — from a single command. Then it keeps that workspace current as your projects evolve.
</p>

<div class="vx-hero__actions">
  <a href="getting-started/install/" class="vx-btn vx-btn--primary">Get Started</a>
  <a href="getting-started/why-owb/" class="vx-btn vx-btn--secondary">Why OWB?</a>
</div>

</div>

<div class="vx-section" markdown>

<p class="vx-section__title">The problem is not Claude. The problem is context.</p>

<p class="vx-section__desc">
  Claude is capable. The question is whether it has the information it needs to be useful on <em>your</em> projects, across sessions, without you re-explaining everything. OWB solves the context problem by giving you a repeatable structure that persists project state, captures decisions, and surfaces the right information at the right time.
</p>

</div>

<div class="vx-features" markdown>

<div class="vx-feature" markdown>
<div class="vx-feature__icon">&#x1F680;</div>
<div class="vx-feature__title">One-Command Setup</div>
<div class="vx-feature__desc">
<code>owb init</code> generates an Obsidian knowledge vault, personal context files, development rules, and custom skills. An interactive wizard guides first-time users through model selection, vault structure, and security settings. Fifteen minutes from install to a working workspace.
</div>
</div>

<div class="vx-feature" markdown>
<div class="vx-feature__icon">&#x1F6E1;</div>
<div class="vx-feature__title">Three-Layer Security Scanner</div>
<div class="vx-feature__desc">
Every file that enters the workspace — upstream updates, third-party skills, migrated content — runs through structural validation, pattern matching against 42 known attack signatures, and optional LLM-powered semantic analysis. Prompt injection gets caught before it reaches your sessions.
</div>
</div>

<div class="vx-feature" markdown>
<div class="vx-feature__icon">&#x1F504;</div>
<div class="vx-feature__title">Drift Detection and Migration</div>
<div class="vx-feature__desc">
<code>owb diff</code> compares your workspace against the reference and tells you exactly what has drifted. <code>owb migrate</code> brings it up to date with interactive file-by-file review. Your customizations are preserved. Nothing overwrites without your consent.
</div>
</div>

<div class="vx-feature" markdown>
<div class="vx-feature__icon">&#x1F9E0;</div>
<div class="vx-feature__title">Knowledge Vault</div>
<div class="vx-feature__desc">
An Obsidian vault with 18 note templates, structured project management, a decision index, research pipeline, and session logging. Claude starts every session by reading a bootstrap file that tells it where each project stands and what to do next. No re-explaining.
</div>
</div>

<div class="vx-feature" markdown>
<div class="vx-feature__icon">&#x1F9E9;</div>
<div class="vx-feature__title">Model-Agnostic, Vendor-Extensible</div>
<div class="vx-feature__desc">
OWB works with any LLM provider through LiteLLM — Anthropic, OpenAI, Ollama, or anything else that speaks the protocol. Downstream packages like CWB (Claude Workspace Builder) depend on OWB as a core library and overlay their own vendor-specific defaults.
</div>
</div>

<div class="vx-feature" markdown>
<div class="vx-feature__icon">&#x1F9EA;</div>
<div class="vx-feature__title">Skill Evaluation Pipeline</div>
<div class="vx-feature__desc">
Before a skill enters the workspace, the evaluator classifies it, generates a test suite, runs the tests against both a baseline and the skill-augmented model, and scores across four dimensions. Incorporate/reject decisions are backed by quantitative evidence, not vibes.
</div>
</div>

</div>

<div class="vx-section" markdown>

<p class="vx-section__title">How it works</p>

<p class="vx-section__desc">
  OWB operates across three phases: design the workspace structure once, build it with a single command, and operate it as projects evolve. The tooling handles drift, upgrades, and security continuously so you can focus on the work.
</p>

</div>

<div style="display:flex; justify-content:center; gap:1rem; flex-wrap:wrap; max-width:1000px; margin:2rem auto; padding:0 1rem;">
  <div style="display:flex; flex-direction:column; gap:0.75rem; align-items:center;">
    <div style="background:#E8920D; color:#0F0F1A; padding:0.6rem 1.2rem; border-radius:6px; font-weight:600; font-size:0.9rem; font-family:JetBrains Mono,monospace;">owb init</div>
    <div style="color:#E8920D; font-size:1.2rem;">&#x25BC;</div>
  </div>
  <div style="display:flex; flex-direction:column; gap:0.5rem; align-items:center; flex:1; min-width:200px;">
    <div style="background:#1A1A2E; color:#E0E0E0; border:2px solid #E8920D; padding:0.75rem 1.5rem; border-radius:8px; font-weight:600; width:100%; text-align:center;">Workspace</div>
    <div style="display:flex; gap:0.5rem; width:100%; justify-content:center; flex-wrap:wrap;">
      <div style="background:#16213E; color:#E0E0E0; border:1px solid #F5B041; padding:0.5rem 0.75rem; border-radius:6px; font-size:0.85rem; flex:1; text-align:center; min-width:120px;">Knowledge Vault</div>
      <div style="background:#16213E; color:#E0E0E0; border:1px solid #F5B041; padding:0.5rem 0.75rem; border-radius:6px; font-size:0.85rem; flex:1; text-align:center; min-width:120px;">Context Files</div>
      <div style="background:#16213E; color:#E0E0E0; border:1px solid #F5B041; padding:0.5rem 0.75rem; border-radius:6px; font-size:0.85rem; flex:1; text-align:center; min-width:120px;">Dev Rules & Skills</div>
    </div>
  </div>
</div>
<div style="display:flex; justify-content:center; gap:0.75rem; flex-wrap:wrap; max-width:700px; margin:0 auto 2rem; padding:0 1rem;">
  <div style="background:#E8920D; color:#0F0F1A; padding:0.45rem 0.9rem; border-radius:6px; font-weight:600; font-size:0.8rem; font-family:JetBrains Mono,monospace;">owb diff</div>
  <div style="background:#E8920D; color:#0F0F1A; padding:0.45rem 0.9rem; border-radius:6px; font-weight:600; font-size:0.8rem; font-family:JetBrains Mono,monospace;">owb migrate</div>
  <div style="background:#E8920D; color:#0F0F1A; padding:0.45rem 0.9rem; border-radius:6px; font-weight:600; font-size:0.8rem; font-family:JetBrains Mono,monospace;">owb security scan</div>
  <div style="background:#E8920D; color:#0F0F1A; padding:0.45rem 0.9rem; border-radius:6px; font-weight:600; font-size:0.8rem; font-family:JetBrains Mono,monospace;">owb eval</div>
</div>

<div class="vx-install" markdown>

<p class="vx-install__title">Start building</p>

```bash
pip install git+https://github.com/VolcanixLLC/open-workspace-builder.git
owb init
```

That is the entire setup. The wizard handles the rest.

[Read the first-run guide →](howto-first-run.md){ .vx-btn .vx-btn--primary }

</div>
