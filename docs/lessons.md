# Lessons

Directives learned from corrections, failed approaches and false assumptions.
Written by `scripts/learn.py` (use `/learn`). Never delete entries; supersede or retire them.

## L-0001 · 2026-10-20 · active
**Lesson:** When an npx-launched MCP server fails with 'Connection closed' or '<bin> is not recognized', check %LOCALAPPDATA%\npm-cache\_npx for an entry with package.json but no node_modules package, and delete that folder.
**Cause:** A half-finished npx install leaves a cache entry npx treats as installed, with no bin shim to run.
**Detect:** Run the server command by hand; the error names the missing bin.
**Tags:** mcp, npx, windows

## L-0002 · 2026-10-20 · active
**Lesson:** Pin mcp<2 for Python MCP servers written against FastMCP (from mcp.server.fastmcp).
**Cause:** mcp 2.x renamed FastMCP to MCPServer and changed APIs; an unpinned install broke the vault-index server.
**Detect:** ModuleNotFoundError for mcp.server.fastmcp at server start.
**Tags:** mcp, python, dependencies

## L-0003 · 2026-10-20 · active
**Lesson:** Write Windows paths in Claude Code hook commands with forward slashes (C:/...); hooks run through Git Bash, which strips backslashes.
**Cause:** The re-index hook command used backslash paths and failed on every real Write.
**Detect:** Hook error mentioning a path with its separators missing, e.g. C:DevelopmentSecondBrainmcp.
**Tags:** hooks, windows, claude-code

## L-0004 · 2026-10-20 · active
**Lesson:** After building a hook, verify it with a real Write in a live session, not only by piping test JSON into the script.
**Cause:** Hand-piped JSON tests passed while the configured hook command itself was broken.
**Detect:** A hook that has never fired from a real tool call.
**Tags:** hooks, testing

## L-0005 · 2026-10-20 · active
**Lesson:** Find Claude Desktop (Microsoft Store install) config and logs under %LOCALAPPDATA%\Claude-Data\<package>, not %APPDATA%\Claude or the Packages LocalCache folder.
**Cause:** The Store install relocates user data; %APPDATA%\Claude only holds a marker file.
**Detect:** %APPDATA%\Claude contains only .user-data-left.* files.
**Tags:** claude-desktop, windows

## L-0006 · 2026-10-20 · active
**Lesson:** Prove each new check or invariant can fail by breaking its target on purpose before trusting a pass.
**Cause:** The first invariants run hid a regex bug (missed .ps1) and a directory walk that only pruned folders containing files; a green result alone would have proven nothing.
**Detect:** A check that has never been seen failing.
**Tags:** invariants, testing

## L-0015 · 2026-10-21 · active
**Lesson:** When merging stacked PRs, merge the lower PR without --delete-branch (or retarget the upper PR to main first); delete the base branch only after the upper PR points at main.
**Cause:** gh pr merge 10 --delete-branch deleted the base of PR #11, and GitHub closed #11 instead of retargeting it; it had to be reopened as #12.
**Detect:** Before merging a PR, run gh pr list --base <its head branch>; if any PR is listed, retarget it first.
**Tags:** github, pr, workflow

## L-0016 · 2026-10-21 · active
**Lesson:** When scanning Gmail with search_threads, request small pages (10 to 20) and metadata or snippet views only; open a full message with get_thread or get_message only when its body is needed.
**Cause:** A Gmail cleanup session spent 56% of its tool tokens on search_threads results with large pages and full bodies.
**Detect:** A single Gmail tool result over a few thousand tokens, or more than 20 threads per page.
**Tags:** tokens, gmail, tools

## L-0017 · 2026-10-21 · active
**Lesson:** In the browser, read pages with get_page_text or find before screenshots; when a screenshot is needed, use scale 0.5 or zoom on the region of interest.
**Cause:** Full-scale screenshots were the second largest tool-token cost in the token review, often taken only to read text.
**Detect:** A full-scale screenshot taken to read text, or several in a row without a click between them.
**Tags:** tokens, browser, tools

## L-0018 · 2026-10-21 · active
**Lesson:** In SecondBrain, pass a path (scripts, mcp/server.py, notes, docs) to Glob; Grep honors the root .ignore (mcp/.venv/) but Glob does not.
**Cause:** The folder is not a git repo, so searches walked 4,600 venv files (89 of 93 hits in one test); .ignore fixed Grep, but Glob still lists the venv.
**Detect:** Glob or Grep results with paths under mcp/.venv.
**Tags:** tokens, search, tools

## L-0019 · 2026-10-21 · active
**Lesson:** Do not weight the heading column higher in vault-index FTS (bm25 weights); it lowered hybrid NDCG@5 at every weight tried. Look at the vector side or the labels for weak spots instead.
**Cause:** Sweep on 2026-10-21 over 31 golden questions: heading x1 0.554, x2 0.539, x3 0.534, x5 0.530, x10 0.518.
**Detect:** A proposed search change that touches bm25(chunks_fts) column weights.
**Tags:** search, eval, vault-index

## L-0020 · 2026-10-21 · active
**Lesson:** To learn what a YouTube video says, read the author's written changelog, release notes or video description; do not try to load its transcript in the built-in browser.
**Cause:** YouTube transcripts did not load in the built-in browser pane.
**Detect:** A task needs the content of a YouTube video.
**Tags:** browser, research

## L-0021 · 2026-10-21 · active
**Lesson:** When auto mode blocks gh pr merge or an edit to Claude's own settings, do not retry or work around it; give the user the exact allow rule (such as Bash(gh pr merge:*)) to add to ~/.claude/settings.json themselves.
**Cause:** Auto mode blocks these actions even when the user asks for them; only the user can add the allow rule.
**Detect:** A permission denial on gh pr merge or on a write to .claude/settings.json in auto mode.
**Tags:** permissions, github, workflow

## L-0022 · 2026-10-21 · active
**Lesson:** Before removing a git worktree, stop any dev server started from it with preview_stop and check that no node process still holds the folder (Get-Process node); TaskStop alone can leave a child node process running.
**Cause:** TaskStop ended the parent task but a child node process kept the worktree folder locked, so removal failed.
**Detect:** git worktree remove fails with a permission or 'in use' error on Windows.
**Tags:** windows, git, worktree, dev-server
