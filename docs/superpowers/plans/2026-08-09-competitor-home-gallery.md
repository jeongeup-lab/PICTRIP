# Competitor Home Gallery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture or source the public home screen for seven PicTrip-overlap projects and present the images in one static HTML comparison gallery.

**Architecture:** Store all gallery-owned PNGs under one `screenshots/` directory and keep provenance in both `README.md` and each HTML card. Live projects are captured from their public deployment; non-live projects use an official repository mockup or a generated evidence-status image that explicitly says no public home UI exists.

**Tech Stack:** Static HTML/CSS, Chromium screenshots, GitHub CLI/API, PowerShell verification.

## Global Constraints

- Gallery scope is exactly seven projects: TripCraft Korea, NextSpot, Gangneung Node, TapGyeong, TripPing, 에움길, IT-DA.
- Never invent a competitor UI when no public UI exists.
- Source labels are exactly `LIVE`, `REPO MOCKUP`, or `NO PUBLIC UI`.
- Desktop captures use 1440×1000; mobile-first captures use 430×932 when the deployed layout is mobile-only.
- HTML preserves each image's original aspect ratio and provides GitHub and Live links where available.

---

### Task 1: Source inventory and output structure

**Files:**
- Create: `ai-shared/competitor-home-gallery-2026-08-09/README.md`
- Create: `ai-shared/competitor-home-gallery-2026-08-09/screenshots/`

**Interfaces:**
- Consumes: the seven-project scope and source rules from the design spec.
- Produces: one provenance row per project with `project`, `github`, `home_source`, `status`, and `capture_date` values represented in Markdown.

- [ ] **Step 1: Confirm repositories and deployment candidates**

Run `gh repo view` for all seven repositories and inspect their README/homepage metadata. Record a source as live only when the public URL renders a project home page.

- [ ] **Step 2: Create the gallery README**

Write a seven-row table with project name, GitHub URL, home source URL or repository asset path, status label, and one-line note.

- [ ] **Step 3: Verify the inventory count**

Run a PowerShell check that counts seven Markdown table rows under the project table. Expected: `7`.

### Task 2: Capture live home screens

**Files:**
- Create: `ai-shared/competitor-home-gallery-2026-08-09/screenshots/nextspot-home.png`
- Create: `ai-shared/competitor-home-gallery-2026-08-09/screenshots/gangneung-node-home.png`
- Create: `ai-shared/competitor-home-gallery-2026-08-09/screenshots/tapgyeong-home.png`
- Create: `ai-shared/competitor-home-gallery-2026-08-09/screenshots/eumgil-home.png`

**Interfaces:**
- Consumes: verified public home URLs from Task 1.
- Produces: PNG files that Task 4 references by exact filename.

- [ ] **Step 1: Open each public home URL and wait for stable render**

Use the browser connection for visual inspection. For screenshot fallback, use Chromium headless with a 10-second virtual-time budget and the viewport defined in Global Constraints.

- [ ] **Step 2: Capture the four public homes**

Capture NextSpot's main map home, Gangneung Node's root home, TapGyeong's root home, and 에움길's root landing page. Do not capture GitHub pages in place of product homes.

- [ ] **Step 3: Inspect every PNG**

Open each image and confirm it contains project UI rather than an error page, blank frame, browser chrome, or cookie/login blocker.

### Task 3: Add repository mockups and honest fallback images

**Files:**
- Create: `ai-shared/competitor-home-gallery-2026-08-09/screenshots/tripcraft-home.png`
- Create: `ai-shared/competitor-home-gallery-2026-08-09/screenshots/tripping-home.png`
- Create: `ai-shared/competitor-home-gallery-2026-08-09/screenshots/it-da-home.png`

**Interfaces:**
- Consumes: official repository assets when present.
- Produces: three PNG files using the same filenames expected by Task 4.

- [ ] **Step 1: Copy the official TripCraft home prototype**

Use the repository's `docs/deliverables/proposal-tripcraft/assets/screens/s1.png` as `tripcraft-home.png`, preserving pixels without modification.

- [ ] **Step 2: Check TripPing and IT-DA for public home assets**

Search each repository tree for PNG/JPG/WebP/GIF and inspect README links and deployment metadata. Use an asset only when it is clearly a product home screen.

- [ ] **Step 3: Produce evidence-status images when needed**

If a project has no public home asset, render a neutral 1440×1000 status panel stating project name, `NO PUBLIC UI`, what public evidence exists, and the GitHub URL. The panel must not mimic or speculate about the project's product UI.

### Task 4: Build the comparison gallery

**Files:**
- Create: `ai-shared/competitor-home-gallery-2026-08-09/index.html`

**Interfaces:**
- Consumes: the seven exact PNG filenames created in Tasks 2 and 3 plus provenance rows from Task 1.
- Produces: a standalone responsive HTML gallery.

- [ ] **Step 1: Implement the page shell**

Create a compact header with title, capture time, and a legend for `LIVE`, `REPO MOCKUP`, and `NO PUBLIC UI`.

- [ ] **Step 2: Implement seven project cards**

Each card contains project name, provenance badge, image link, one-line entry flow, GitHub link, and optional Live link. Use CSS Grid with two columns above 900px and one column below 900px.

- [ ] **Step 3: Keep image comparison honest**

Use `object-fit: contain`, show full image bounds, and place mobile screenshots on a neutral canvas rather than cropping them to fill a desktop card.

### Task 5: Verify the gallery

**Files:**
- Create: `ai-shared/competitor-home-gallery-2026-08-09/gallery-preview.png`

**Interfaces:**
- Consumes: all Task 1–4 outputs.
- Produces: fresh evidence that the gallery renders and all references resolve.

- [ ] **Step 1: Validate project and image counts**

Parse `index.html` and assert exactly seven `.project-card` elements and seven project image references.

- [ ] **Step 2: Validate local paths**

Resolve every local `src` and local `href` from the HTML directory. Expected: zero missing files.

- [ ] **Step 3: Validate remote links**

Run `gh repo view` for seven GitHub repositories and HTTP checks for every Live link. Expected: all GitHub repositories resolve and every listed Live URL returns HTTP 200.

- [ ] **Step 4: Render and inspect the HTML**

Capture `index.html` at 1440×1200 as `gallery-preview.png`, inspect the image, and confirm the header and first cards are readable without horizontal overflow.

- [ ] **Step 5: Run final whitespace checks**

Run `git diff --check` and report only the gallery files and intentional documentation commits.
