---
name: Solution Benchmarker
description: Arcade-cabinet race board for one live coding-task run.
colors:
  ground: "#0c0b10"
  panel: "#16141d"
  raised: "#201d29"
  line: "#34303f"
  divider: "#262230"
  ink: "#f4f4f7"
  muted: "#a29fae"
  on-hue: "#120f0a"
  coral: "#ff6b4a"
  sun: "#ffc531"
  mint: "#3fe0a0"
  sky: "#4ea8ff"
  pink: "#ff5fae"
  pass: "#3fe0a0"
  fail: "#ff8a73"
typography:
  banner:
    fontFamily: "Unbounded, Onest, system-ui, sans-serif"
    fontSize: "56px"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  best-score:
    fontFamily: "Unbounded, Onest, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 800
    lineHeight: 1.1
  lane-rank:
    fontFamily: "Unbounded, Onest, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 800
  headline:
    fontFamily: "Unbounded, Onest, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Unbounded, Onest, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  table-score:
    fontFamily: "Unbounded, Onest, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 800
  body:
    fontFamily: "Onest, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
  name:
    fontFamily: "Onest, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 600
  label:
    fontFamily: "Onest, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 600
  step:
    fontFamily: "Onest, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: "18px"
  small:
    fontFamily: "Onest, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
  slot-figure:
    fontFamily: "Martian Mono, ui-monospace, monospace"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.25
    fontFeature: "tnum"
  code:
    fontFamily: "Martian Mono, ui-monospace, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "20px"
  mono-small:
    fontFamily: "Martian Mono, ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "16px"
  kbd:
    fontFamily: "Martian Mono, ui-monospace, monospace"
    fontSize: "10px"
    fontWeight: 600
    lineHeight: "16px"
rounded:
  mark: "2px"
  kbd: "4px"
  slot: "10px"
  field: "12px"
  strip: "14px"
  card: "20px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "10px"
  ml: "12px"
  lg: "14px"
  xl: "16px"
  gap: "20px"
  card: "22px"
  page: "32px"
components:
  button-action:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "38px"
  button-action-disabled:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.muted}"
  button-ghost:
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "38px"
  card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.card}"
    padding: "22px"
  task-strip:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.strip}"
    padding: "12px 16px 12px 18px"
  lane:
    rounded: "{rounded.field}"
    padding: "10px 12px"
  slot-passed:
    textColor: "{colors.on-hue}"
    typography: "{typography.slot-figure}"
    rounded: "{rounded.slot}"
    padding: "0 14px"
    height: "54px"
  slot-failed:
    textColor: "{colors.ink}"
    rounded: "{rounded.slot}"
    padding: "0 14px"
    height: "54px"
  slot-waiting:
    textColor: "{colors.muted}"
    rounded: "{rounded.slot}"
    padding: "0 14px"
    height: "54px"
  step:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.muted}"
    typography: "{typography.step}"
    rounded: "{rounded.pill}"
    padding: "6px 12px"
  step-now:
    backgroundColor: "{colors.sun}"
    textColor: "{colors.on-hue}"
  step-next:
    textColor: "{colors.sun}"
  phase-stopped:
    backgroundColor: "{colors.fail}"
    textColor: "{colors.on-hue}"
    rounded: "{rounded.pill}"
    padding: "6px 12px"
  leaderboard-row:
    textColor: "{colors.ink}"
    rounded: "{rounded.slot}"
    padding: "10px"
  leaderboard-row-hover:
    backgroundColor: "{colors.raised}"
  input-field:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.field}"
    padding: "14px"
  banner:
    backgroundColor: "{colors.sun}"
    textColor: "{colors.on-hue}"
    typography: "{typography.banner}"
    padding: "28px 32px"
  dialog:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "26px"
    width: "min(560px, calc(100% - 48px))"
  measure-tile:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.muted}"
    rounded: "{rounded.field}"
    padding: "14px"
---

# Design System: Solution Benchmarker

## Overview

**Creative North Star: "The arcade cabinet"**

A near-black cabinet with five lit players. The page answers one question during a recorded interview: who is ahead, and what is each agent doing right now. Every agent owns one bright hue and carries it everywhere it appears: its diamond, its passed attempt blocks, its running stripes, its best score, its leaderboard swatch. The interviewee (`you`) races in ink. The energy comes from those hues, from heavy scoreboard type, and from small motion, not from gradients or glow.

The race board leads. Each agent is a lane: rank, name, three attempt blocks, best score. The leader's lane is outlined in its own hue and its rank and best score light up. The task and your own solution sit side by side as two equal editors, with a Python or FastAPI badge on the task (detected from the text, click to switch). Once a run starts, the task editor collapses to its title and first lines. Below the race, the leaderboard and the attempt details share a row on desktop; the details are a sticky panel with Review and Solution tabs, Review first. A score appears only once solving has ended and every review of that attempt is in, so it never jumps. Rows join the leaderboard as soon as an attempt starts, sit at the bottom with empty cells, and slide to their place when the score lands. The phase is a row of pill steps, with the current one lit in sun.

Surfaces are flat, rounded, and stepped in tone: ground, then panel, then raised. Lines are inset rings, never drop shadows.

**Key Characteristics:**

- Near-black ground; rounded panels one tone lighter; raised tiles one tone lighter again.
- Five agent hues (coral, sun, mint, sky, pink); `you` in ink.
- Passed is a solid block in the hue, failed is an outline with the score struck through, running is marching stripes.
- Unbounded 800 for the scoreboard voice, Onest for words, Martian Mono for counts and code.
- Sun yellow is the house accent: current step, focus ring, text selection, the recording banner, the dialog ring.

## Colors

A dark field lit by five player hues and one house accent; colour belongs to agents and states, not to chrome.

### Primary

- **Sun** (`sun`): the house accent as well as the second agent's hue. The current phase step fill, the next-step outline (55% mix), every focus outline (2px), text selection, the recording banner fill, and the message dialog ring.

### Secondary: the agent hues

- **Coral** (`coral`), **Sun** (`sun`), **Mint** (`mint`), **Sky** (`sky`), **Pink** (`pink`): assigned to agents by their order in the run's agent list, cycling after five. Each paints its agent's diamond, passed blocks, running stripes and ring, failed-block outline (55% mix) and strike (75% mix), the leader outline, the lead rank and best score, the leaderboard swatch, the first-row bar, and the selected-row tint and ring.
- **Ink as a player**: the interviewee's lane and rows use `ink` as their hue, so a passed `you` block is an ink block with on-hue text.
- **On-hue** (`on-hue`): text on any hue fill (passed blocks, current step, banner, stopped phase, selection).

### Tertiary: results

- **Pass** (`pass`, same value as mint): the word and check icon "Pass" in the leaderboard, and the drawn tick on completed steps.
- **Fail** (`fail`): the word and cross icon "Fail", the stopped-phase pill, the failure excerpt text, and the error notice (ring plus a 14% tint over panel).

### Neutral

- **Ground** (`ground`): the page, text fields and code panes.
- **Panel** (`panel`): cards, the task strip, idle steps, the dialog.
- **Raised** (`raised`): leaderboard row hover, measurement tiles, disabled action button.
- **Line** (`line`): field borders, ghost-button ring, waiting-slot ring, idle step dot, scrollbar thumb.
- **Divider** (`divider`): the 1px rule between lanes and between leaderboard rows.
- **Ink** (`ink`): primary text and the action button fill.
- **Muted** (`muted`): secondary text, hints, column heads, lane ranks below the leader, empty best score.

### Named Rules

**The One Hue Per Player Rule.** An agent's hue appears only on that agent's own marks. No hue is used for chrome except sun, and sun is still read as "now" or "look here".

**The Block, Outline, Stripes Rule.** An attempt's state is its form: solid hue fill for passed, hue outline with a struck score for failed, marching hue stripes inside a 2px hue ring for running, a 1px line ring with a dash for waiting. The leaderboard never paints a whole row by result; only the result word is green or red.

## Typography

**Display Font:** Unbounded (with Onest, system-ui, sans-serif)
**Body Font:** Onest (with system-ui, sans-serif)
**Label/Mono Font:** Martian Mono (with ui-monospace, monospace)

**Character:** Unbounded at 800 is the cabinet's scoreboard voice, wide and loud, used only for headings, ranks and scores. Onest keeps the sentences quiet. Martian Mono carries counts, test tallies, timings, code and key hints so columns stack.

### Hierarchy

- **Banner** (Unbounded 800, 56px, 1.1, -0.02em; 36px under 800px): the recording message only.
- **Best score** (Unbounded 800, 30px; 22px under 800px): the lane's best, in the agent hue.
- **Lane rank** (Unbounded 800, 24px; 18px under 800px): muted, hue on the leader.
- **Headline** (Unbounded 800, 22px, -0.01em): the page title.
- **Title** (Unbounded 800, 18px, -0.01em): block headings and the leaderboard score. The task name in the strip is Unbounded 800 at 16px; the leaderboard rank 15px.
- **Name** (Onest 600, 15px): agent names, measurement labels, reviewer names.
- **Body** (Onest 400, 14px, 1.45): sentences, hints, the task line.
- **Label** (Onest 600, 14px; steps 13px/18px): buttons, steps, the strip tag.
- **Small** (Onest 400, 12px): notes under slots and scores, column heads, the CLI suffix.
- **Slot figure** (Martian Mono 600, 16px, tabular): the score inside an attempt block.
- **Code** (Martian Mono 400, 13px/20px): textareas, solution pane, table numbers. Failure excerpts at 12px.
- **Mono small** (Martian Mono 400, 12px/16px): the CLI and reviewer status line under an agent name. Key hints are Martian Mono 600 at 10px.

### Named Rules

**The Scoreboard Voice Rule.** Unbounded appears only at 800 and only for headings, ranks, scores, the task name and the banner. Never for sentences or buttons.

**The Stacked Figure Rule.** Every score, rank and count is tabular. Counts, times and code are Martian Mono.

## Layout

One centred column, max 1480px, padded 28px top, 32px sides, 48px bottom; 20px between blocks. Order: header (mark and title left; steps, hidden phase and the Message button right), error notice, then either the task card (idle or editing) or the task strip (running), the race card, a lower row with the leaderboard (1.6fr) beside the "Your solution" card (1fr), and the attempt detail card when a row is opened. The banner, while shown, pushes the column down to 160px of top padding.

A lane is a four-column grid: 44px rank, 180 to 230px identity, flexible slots, 120px best score, 16px gaps. The three slots share the width equally with 8px gaps. The leaderboard is an eight-column grid (rank, agent, attempt, result, score, tests, speed, clarity) with 10px gaps; figures right-aligned. The detail splits 0.9fr measurements and reviews to 1.1fr solution, 24px gap; measurements are a two-up tile grid.

**Responsive.** At 960px and below, the lower row and the detail stack to one column. At 800px and below, page padding drops to 16px; the steps take their own full-width row and scroll horizontally; a lane becomes rank, name and best on one row with the three slots on the next; the leaderboard drops the attempt, speed and clarity columns; measurement tiles go single-column; the banner drops to 36px; the task strip hides its description line and keeps the name.

## Elevation & Depth

No drop shadows anywhere. Depth is a tone step (ground, panel, raised) and edges are inset rings drawn with `box-shadow: inset`. The only things that sit above the page are the fixed recording banner and the modal dialog, and neither casts a shadow; the dialog dims the page with a dark backdrop instead.

### Shadow Vocabulary

- **Hair ring** (`inset 0 0 0 1px` line): ghost button, waiting slot, review block. Muted on ghost hover.
- **Player ring** (`inset 0 0 0 2px` hue): leader lane, running slot, selected leaderboard row. Failed slot uses the hue at 55%.
- **Lead bar** (`inset 3px 0 0` hue): the left edge of the first leaderboard row.
- **Accent ring** (`inset 0 0 0 2px` sun): the message dialog. Sun at 55% and 1px on the next step.
- **Lane divider** (`0 -1px 0` divider): between lanes, suppressed under the leader.

### Named Rules

**The Ring Not Shadow Rule.** Emphasis is an inset ring in the owner's hue. Nothing floats.

## Shapes

Everything is rounded and soft at the corners; the only sharp move is the agent diamond. Cards and the dialog are 20px, the task strip 14px, lanes, fields, notices and tiles 12px, attempt blocks and leaderboard rows 10px, buttons and steps fully round. The agent mark is a 14px square with 4px corners rotated 45 degrees; in the leaderboard it is an unrotated 10px square with 3px corners. The brand mark is three rounded bars (sun, coral, mint) of rising height. Icons are inline 16px stroked SVGs (2px, round caps): check, cross, eye.

## Components

### Buttons

- **Shape:** fully round pill, 38px high, 0 16px padding, Onest 600 14px.
- **Action:** ink fill, ground text. Hover lifts 1px over 120ms. Disabled: raised fill, muted text, not-allowed cursor.
- **Ghost:** transparent with a 1px line ring; ring turns muted on hover. Used for Edit, Cancel, Show/Hide solution.
- **Focus:** 2px sun outline, 2px offset.
- **Key hints:** a small Martian Mono chip (10px, 1px currentColor border, 4px corners, 70% opacity) inside buttons and beside paste headings (M, T, Y, Esc).

### Phase steps

Four pills (Tests, Solving, Reviewing, Finished) on panel in muted text, each led by a 7px dot. Done steps turn ink with a drawn pass-green tick. The current step fills sun with on-hue text. Before a run, the first step is "next": sun text, sun dot, a 1px sun ring at 55%. A skipped review shows a short dash and the word "skipped". The phase word itself is screen-reader-only except when the run stops, when it shows as a fail-filled pill.

### Task card and task strip

Idle: a card with the "Task" heading and T hint, a label, a mono textarea and "Start the run". Running: the card collapses to a panel strip with a muted "Task" tag, the task name in Unbounded 800 16px (max 40%, ellipsis), the remaining text on one muted ellipsed line, and a ghost Edit button at the right. Editing reopens the card with a Cancel ghost button.

### Race lanes (signature)

Lanes sit directly on the race card, transparent, 12px corners, separated by a 1px divider. Rank in Unbounded, then the agent diamond, name (Onest 600 15px) and a mono status line (CLI and reviewer progress, or "your paste · same suite"), then three attempt blocks, then "Best" over the best score in the hue (muted dash when none). Lanes sort by best score. The leader (rank 1 with a score) gets a 2px ring in its hue and a hue-coloured rank. Before any agents exist, three half-opacity ghost lanes in the first three hues stand in under a muted sentence.

### Attempt blocks

54px tall, 10px corners, 0 14px padding, a figure line over a small line. Passed: hue fill, on-hue text, check icon, score, "n/m · pass" plus "· kept" for the chosen one. Failed: ink text, hue ring at 55%, cross icon, score struck through 2px in the hue at 75%, "n/m · fail". Running: hue text and 2px hue ring over 20px diagonal stripes of the hue at 24%, marching one tile every 800ms; reads "Running / attempt n". Waiting: muted, 1px line ring, a dash.

### Leaderboard

Every finished attempt is its own full-width button row, sorted by score. Muted column heads at 12px. Rows are transparent with 10px corners and a 1px divider between them; hover is raised. The first row has a 3px inset hue bar on its left and hue-coloured rank and score. The selected row is tinted 14% hue over raised with a 2px hue ring. The agent cell leads with the 10px hue swatch, the name, and the muted CLI. The result cell is the icon and word in pass or fail colour. Each human paste is its own "you" row (you 1, you 2, …) in ink; the solution box clears after each one, so any number can follow.

### Empty and loading states

Before a run nothing is loading, so nothing shimmers. The Leaderboard shows an empty podium: three dashed blocks in the brand-mark hues (2 sun, 1 coral, 3 mint, the logo's own heights), which rise in once over 560ms, then "The podium is empty", the attempt count, and the next run's models as hue-diamond chips under "On the grid". Before any row is selected, the Attempt card centres three dashed ghost tabs over "Nothing to inspect yet" (before a run) or "Pick an attempt" (during one). The pulsing skeleton is kept only for the short wait between Start and the first rows. Ready preflight lanes show only the check mark and "Ready".

### Attempt detail

A card titled "agent · attempt n", sticky beside the leaderboard at 20px from the top. Its height is the smaller of the leaderboard card and the viewport less 120px, so it never changes with review count and never stretches down a long leaderboard; its body scrolls under fixed header and tabs. Left: raised measurement tiles (Correctness, Performance, Readability, Score) with an ink label and muted text, the first failure as a 12px fail-coloured mono excerpt on ground, then reviews as hair-ringed blocks. Right: the solution in a mono pane on ground (1px line, 12px corners, 160 to 380px tall, scrolls), blurred 8px until "Show solution" (ghost, eye icon) reveals it.

### Inputs / Fields

Textareas, the solution pane and the message field sit on ground with a 1px line border and 12px corners; textareas are mono 13/20. Focus replaces the border with a 2px sun outline at 1px offset. The message field is 44px high, Onest 500 16px. Labels are muted and sit above.

### Notice

An error strip on a 14% fail tint over panel, a 1px fail ring, 12px corners, Onest 500, hidden when empty.

### Recording banner

A full-width sun bar fixed to the top, on-hue Unbounded 800 at 56px, 28px 32px padding, shown for 5 seconds. It drops in from above over 320ms.

### Message dialog

A modal panel, up to 560px wide, 20px corners, 26px padding, with a 2px sun ring over a dark backdrop. Heading, muted label, the message field and a muted hint. Enter sends, Escape closes.

### Motion

Motion carries state, never decoration. The running-block stripes (800ms linear, infinite) also fill the current phase pill, whose dot becomes a 700ms spinner while the phase is working, and the test-author lane while the hidden suite is being written. A row that changes rank lifts (scale 1.025, drop shadow) and slides to its new place over 720ms `cubic-bezier(.2, .8, .2, 1)`, like a card dragged on a board; rows only pushed down by an insertion slide plainly over 360ms; new rows fade up 10px. A score pops in once (520ms) when it becomes final, and three blinking dots hold its place while reviews run. Tabs fade up 6px over 240ms; the tech badge pops when detection changes. The banner drop (320ms) and the 1px action-button lift (120ms ease) are unchanged. Under `prefers-reduced-motion: reduce` every animation and transition stops; stripes and spinners still show, standing still.

### Keyboard

T task, Y your solution, A agents, L leaderboard (then Up, Down, Home, End select rows; focus stays on the same attempt when it moves), R review, S solution (Left and Right switch tabs), M message. Escape leaves any field or the leaderboard, so letters work as shortcuts again and arrows scroll the page. A muted shortcut strip sits at the foot of the page on wider screens.

## Do's and Don'ts

### Do:

- **Do** give each agent one hue by run order and use it on all of that agent's marks; draw `you` in ink.
- **Do** show attempt state as form: solid block, struck outline, marching stripes, hair ring.
- **Do** mark the leader with a 2px ring in its own hue and light its rank and best score.
- **Do** use sun for "now" and "look here": current step, focus outline, banner, dialog ring.
- **Do** collapse the task to its strip while a run is live.
- **Do** keep every animation still-able under reduced motion.

### Don't:

- **Don't** use purple-to-cyan gradients, glow halos, gradient text, or drop shadows; edges are inset rings.
- **Don't** paint a whole leaderboard row green or red; only the result word carries pass or fail.
- **Don't** use one agent's hue on another agent's marks or on general chrome.
- **Don't** set sentences or buttons in Unbounded.

## Direction

**Picked: 1 · Arcade cabinet** (restyle 2026-10-22, supersedes the earlier data-terminal direction). The user asked for playful, fun and colourful, picked board reference #4 "Neon arcade", then this variant from three. Runners-up: 2 · Timing tower (F1 broadcast) and 3 · Sticker arcade (flat brights with ink outlines and hard shadows). Mockups: `.uiux/runs/2026-10-22-playful-restyle/restyle/directions/`. The build's ink is a cool white rather than the mockup's warm cream; the build wins.

Before critique (why it changed): flat grey with under 3% colour read as a generic dark admin template; the five agents looked identical; the leader had no moment and the phase sat in small grey type; the paste boxes took the top 40% during a run.
