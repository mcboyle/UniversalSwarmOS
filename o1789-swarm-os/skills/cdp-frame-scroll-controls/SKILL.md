---
name: cdp-frame-scroll-controls
description: Validate CDP FPS and auto-scroll audit observations with visible-window
  and nonzero-overflow controls.
category: measurement
triggers:
- CDP FPS audit
- auto-scroll audit
---

# CDP frame and scroll measurement controls

For a frame-rate or scroll audit, use an owned temporary browser context/window and close only owned targets afterward. Do not change existing user tabs.

Before sampling, record document.visibilityState, document.hasFocus(), viewport, browser version and GPU renderer. Chrome 155 can create a hidden isolated window even after Page.bringToFront; on the owned window, Browser.setWindowBounds(windowState=normal), Emulation.setFocusEmulationEnabled(true), and Page.bringToFront produced visible RAF callbacks in the measured case. A hidden-page timeout is an observer failure, not an application FPS result.

Before judging scroll preservation, reveal the target pane and require clientHeight > 0 and scrollHeight > clientHeight. A hidden pane yielding scrollTop=0 before and after cannot establish preservation. Retain that excluded attempt, then test read-back and near-bottom follow as separate positive controls. Record node connectivity through membership changes.

Use a blank-page positive control for Canvas2D/WebGL draw detection, RAF, long tasks and error capture. Compare a rendering failure against a control without method wrappers. Report RAF scheduling cadence separately from hardware-presented frames and from idle DOM responsiveness.

Measured evidence: /home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/CODEX-SOL-2-60FPS-UX-AUDIT.md and CODEX-SOL-2-60FPS-UX-EVIDENCE/ (2026-10-18).
