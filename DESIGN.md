<!-- SEED: established with the user before implementation; re-run /impeccable document once there's code to capture the actual tokens and components. -->
---
name: coding-task-benchmark
description: Dark local console for one live coding-task run.
---

# Design System: coding-task-benchmark

## Overview

**Creative North Star: "The night editor"**

**Direction: data terminal.** Chosen because the page is watched like a code editor during one interview, and it needs a point of view without becoming a dashboard. The dealt sheet (seed 495464882) is a dark monitoring screen: cards darker than the ground, tabular figures, and every selection marked by the same 1px accent line. Calm and precise, with that one move kept intact.

The screen's question is which solution is ahead, and what each agent is doing right now. Its face is Public Sans for words and IBM Plex Mono for scores, counts, and times, so the columns stay stacked while attempts update. Its signature is the attempt board: one row per agent, three slots, the selected slot carrying the accent line along its bottom edge. That board is the largest block.

The dealt shell was a 50px icon rail. This product has one screen, so the rail is dropped. The name sits in the title row. The recording message is the exception to the dark ground: a full-width light bar, held for 5 seconds, because the people watching the recording have to read it.

**Key Characteristics:**

- Dark ground, darker cards, one blue line for selection.
- Words in Public Sans. Figures and code in IBM Plex Mono.
- Pass and fail are written, not painted across a row.
- The attempt board leads. The leaderboard and the open solution sit with it.
- The flashed message inverts the ground so the recording can read it.

## Colors

One dark field. Colour is a 1px line, a status word, or the inverted message. It stays under 3% of the screen.

### Primary

- **Editor blue** (`{colors.accent}` when extracted; sheet value `#4a8ad6`): the selection line only. As wide as the selected label, on the nearest edge.

### Neutral

- **Terminal ground** (sheet `#171719`): the page.
- **Card well** (sheet `#131217`): cards, darker than the ground.
- **Raised row** (sheet `#212023`): a hovered or grouped row.
- **Ink** (sheet `#ffffff`): primary text and ordinary numbers.
- **Muted ink** (sheet `#8a8c92`): secondary text. Nothing fainter: the sheet's dimmer grey failed contrast.
- **Hairline** (sheet `#222224` edge, `#1b1a1f` rule): separation where a tone step is not enough.
- **Message paper** (sheet `#f2f2f3`): the recording banner only, with terminal-ground text.

### Named Rules

**The One Line Rule.** The accent is a 1px line. It is never a fill, a pill, or a button.

**The Sign Rule.** A number stays white or grey. A change carries its sign in the text. Green and red are for a result that needs a decision, such as the word "fail", not for every figure.

## Typography

**Body Font:** Public Sans (Inter, system-ui, sans-serif)
**Figure Font:** IBM Plex Mono (ui-monospace, monospace), for scores, counts, times, and real code.

**Character:** A text face for the task and the labels. A mono face so the score columns do not shift as an attempt finishes.

### Hierarchy

- **Title** (600, 26px): the task name, the only title.
- **Section** (400, 20px, muted): a block name.
- **Card title** (600, 16px): an agent or a panel.
- **Body** (400, 13px): labels and sentences.
- **Small** (400, 12px): a note under a score.
- **Figures** (400, 20px, mono, tabular): the profile and the test counts.

### Named Rules

**The Stacked Figure Rule.** Every score, count, and time is tabular mono. Prose stays in Public Sans.

## Layout

One column on the ground, no sidebar. Padding 32px. One gap, 24px, between blocks. Dense, because five agents and three attempts have to be on the first screen with the leaderboard's first rows.

The title row holds the task name and the phase. Under it, the attempt board spans the width. The leaderboard and the open solution share the next row. The task paste and the solution paste are the actions, and each sits with the block it fills.

On a phone the board becomes one agent per row, the attempts under the name, and the solution under the board.

## Elevation & Depth

Depth is a tone step: the card is darker than the ground. The sheet's card shadow (`0 12px 28px rgba(0,0,0,.2)`) belongs to those cards only. Nothing else floats, except the recording banner, which replaces the top of the ground rather than hovering over it.

### Named Rules

**The Flat Chrome Rule.** Controls, the title, and the banner do not cast a shadow.

## Shapes

Cards are slightly rounded (6px). Controls that are buttons are fully round, as the sheet sets. Selection is not a shape: it is the 1px line.

## Do's and Don'ts

### Do:

- **Do** mark the selected attempt, the selected solution, and the active field with the same 1px editor-blue line.
- **Do** write pass, fail, and kept as words. Colour only the word "fail", and only in the negative ink.
- **Do** keep the flashed message full width, on message paper, large enough to read across the room, for 5 seconds.
- **Do** show an empty score as a grey dash and a real zero as 0.

### Don't:

- **Don't** add a sidebar, a rail of icons, or a second destination.
- **Don't** use a filled pill, a gradient, a glow, or an icon in a coloured tile.
- **Don't** paint a whole row green or red because the attempt passed or failed.
- **Don't** set the recording message in the dark body size. It is the one line the watchers are there to read.
