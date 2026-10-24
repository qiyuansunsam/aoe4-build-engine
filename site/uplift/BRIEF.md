# UI uplift experiments — shared brief

Project: Mathmatically Correct AoE 4 (`C:/Users/Sam/projects/aoe4-build-crafter`). Single-file app:
`site/index.template.html` + `site/crafter.css` + `site/crafter.js` (+ `games.css`, `catalog.css`,
`context-actions.*`, `build-timeline.css`) are inlined by `python -X utf8 site/build.py`.
Read `DESIGN.md` (material: neutral glass, blue A / amber B accents, Fraunces display, IBM Plex Sans/Mono)
and the two skills `C:/Users/Sam/.claude/skills/forward-deployments/SKILL.md` (motion spec, tell list)
and `C:/Users/Sam/.claude/skills/ui-craft/SKILL.md` (craft numbers) before writing CSS.

## Goal

Sam's words: "a total uplift of the ui... a lot more animations everywhere, also the ui looks like it
lacks style, needs to animate it and using forward deployment skill's ui element designs (don't change
layout and features just how it looks)". Your deliverable is **two alternative looks for one area**,
each a self-contained CSS file (+ optional small JS file for animation hooks), with screenshots, so the
best-looking one can be chosen.

## Hard rules

1. **Do not edit any shared file** (`crafter.css`, `crafter.js`, `games.css`, `catalog.css`,
   `context-actions.*`, `build-timeline.css`, `index.template.html`, `build.py`, anything in `data/`,
   `server/`, `engine/`). Only create files under `site/uplift/` named `<area>-<variant>.css` /
   `<area>-<variant>.js` and screenshots under `site/uplift/shots/`.
2. **No layout or feature changes.** Same DOM, same grid areas, same controls, same copy. You may
   restyle (surfaces, borders, shadows, colour tokens within the existing blue/amber system, type
   weights/sizes from the 12/14/16/20/24/30/36 scale, radii, icons' containers) and add motion.
3. **Motion**: use `transform`/`opacity` transitions and CSS keyframes; ease-out
   `cubic-bezier(.23,1,.32,1)` for user-triggered motion; 100–160 ms micro feedback, 150–250 ms
   popovers, ≤ 300 ms otherwise, one orchestrated reveal on page render (stagger 40–60 ms). Every
   animation must be wrapped so `@media (prefers-reduced-motion: reduce)` keeps only opacity/colour
   fades. Nothing loops idly. Numbers that change on the timeline may tween (JS, ≤ 400 ms, cancelable).
4. **JS hooks**: `crafter.js` declares global functions (`drawChart`, `drawMoment`, `drawDetail`,
   `renderWorkspace`, `navigate`, `renderBuilds`, `renderGames`, `renderDatabase`, `setTime`...). Your
   `.js` runs after them, so you may wrap one: `const _prev=drawMoment; drawMoment=function(){ _prev();
   /* add classes / animate */ };`. Never change behaviour, state, or data; only add classes, data
   attributes or Web Animations. Guard every hook with try/catch so a failure never breaks the app.
5. Both themes must look finished: `html[data-theme=light]` (White) and `html[data-theme=dark]`
   (VS Code dark). Keep WCAG AA contrast. Keep `:focus-visible` rings visible.
6. Strip the tells listed in forward-deployments §7 (identical grey shadows on everything, hover-lift on
   every card, purple washes, fade-up on every section...). The look should feel like one considered
   material system: glass surfaces with rim light, depth from layered translucency, confident type.

## Build, serve, screenshot

```
cd C:/Users/Sam/projects/aoe4-build-crafter
python -X utf8 site/build.py --out site/uplift/dist-<area>-<variant> --extra-css site/uplift/<area>-<variant>.css [--extra-js site/uplift/<area>-<variant>.js]
python -m http.server <your port> -d site/uplift/dist-<area>-<variant>   # run in background with a timeout wrapper
```

Screenshot with the Playwright already installed at `C:/Users/Sam/projects/codex-setup/browser-tools`
(see `site/verify-reference-comparison.cjs` for the require path and the `applyBuild('observed:<id>',path)`
/ `state.metric` / `renderWorkspace()` page globals). Viewport 1440×1000. Set the theme with
`localStorage.setItem('aoe-crafter-v2', JSON.stringify({theme:'dark'}))` in an init script (or `'light'`).
Comparison deep link: `#workspace`; a build: `#builds/french-observed-4v4`; games: `#games`; library:
`#database`. Save `site/uplift/shots/<area>-<variant>-<theme>-<page>.png`. Also record one short GIF or a
3-frame sequence of your main motion if you can (Playwright video is fine), otherwise describe it.

Use `python -X utf8` for Python. Write files with the Write tool (shell heredocs mangle non-ASCII).
Every background command gets `timeout` and `</dev/null`. Never wait on a human.

## Report back (keep it short)

For each variant: file paths, one-paragraph visual thesis, the motion list (moment → duration), the
screenshot paths, and anything you could not verify. State which of your two variants you prefer and why.
