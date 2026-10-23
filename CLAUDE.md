# SecondBrain

Personal knowledge base. Markdown files are the record; the search index and the knowledge graph can be rebuilt or corrected from them.

## Style
- Replies and files: simple, concise, to the point.
- Who I am and my goals: `notes/topics/about-me.md`, `notes/topics/goals.md` (create them; edit freely).

## Where things are
- `notes/`: the Obsidian vault (`inbox/`, `topics/`, `daily/`); `notes/index.md` maps it.
- `docs/adr/`: architecture decision records (`/adr`).
- `docs/lessons.md`: dated lessons written as directives (`/learn`, via `scripts/learn.py`). Never edit by hand.
- `mcp/`: the `vault-index` MCP server (hybrid FTS5 + sqlite-vec search) and its re-index hook.
- `docs/handoffs/`: notes that carry work into a fresh session (`/handoff`).
- `.claude/commands/`: slash commands listed below.
- `eval/`: retrieval golden set and `run_eval.py`. Run it before and after any search change; keep a change only if it beats `eval/baseline.json`.

## Search before you guess
- `search_notes` (vault-index): the primary source. Use it before answering anything about past decisions, notes, lessons or this system. `get_note` reads a full file.
- `search_nodes` (memory graph): a map of entities and relations only. Use it to find related topics, then confirm in the files.
- Before working in an area, search `docs/lessons.md` for its lessons (`search_notes` with `path_prefix`).
- If the graph and a file disagree, the file wins; fix the graph.
- `<SecondBrain root>` in commands means the absolute path of this folder.

## Writing memory (deliberately, never by default)
- A decision → `/adr`. A correction, failed approach or false assumption → `/learn`.
- Graph: only entities for durable things (projects, systems, people, tools) and relations between them. Each observation is one short fact that names its source file. No full text, no lessons, no session narration.
- Record nothing when nothing durable was learned. Never store secrets, keys or tokens.

## Commands
- `/recall <topic>`: notes and graph together, summarised with sources.
- `/adr <title>`: write a decision record and link it in the graph.
- `/learn <what happened>`: record a lesson as a directive.
- `/ingest <path>`: index a file or folder and add its durable entities to the graph.
- `/handoff [topic]`: write a handoff note and continue in a fresh session.

## Long sessions
- One session per task. A context guard hook warns at the soft limit and requires `/handoff` at the hard limit (`.claude/handoff.json`). Prefer a handoff over `/compact`.
- When a session starts from a handoff note, read it first and set its `status` to `picked-up`.

## Maintenance
- `scripts/invariants.py` runs at session start and checks that each pipeline reaches its consumer. If it reports failures, tell the user and fix the root cause before other work.
- Edits made with Write/Edit in this folder are re-indexed by a hook. After deleting files or editing elsewhere, run `index_paths` with no arguments.
