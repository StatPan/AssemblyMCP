# AssemblyMCP UX Redesign Plan

Issue: [#60](https://github.com/StatPan/AssemblyMCP/issues/60)

## Purpose

AssemblyMCP should feel like a legislative research product, not a flat list of
National Assembly API wrappers. This plan defines the target UX before changing
the public MCP tool contract.

The reference point is KoreaLawMCP, but the goal is not feature-by-feature
copying. KoreaLawMCP works well because it compresses a broad official API
surface into a small workflow-oriented MCP surface, leads with user jobs, and
uses explicit failure markers to prevent LLM hallucination. AssemblyMCP should
translate those ideas into the National Assembly domain: bills, members,
committees, meetings, voting records, schedules, and reports.

## Current Tool Surface

Current public tools in `assemblymcp/server.py`: 19

### Meta

- `ping`
- `get_assembly_info`
- `get_api_code_guide`

### Discovery

- `list_api_services`
- `get_api_spec`
- `call_api_raw`

### Atomic Lookup

- `search_bills`
- `get_bill_details`
- `get_bill_history`
- `get_member_info`
- `search_meetings`
- `get_plenary_schedule`
- `get_committee_info`
- `get_member_voting_history`
- `get_legislative_reports`

### Workflow / Analysis

- `analyze_legislative_issue`
- `get_committee_work_summary`
- `get_representative_report`
- `get_bill_voting_results`
- `analyze_voting_trends`

## Problems To Solve

1. **No single first-call UX**

   `get_assembly_info` is helpful, but it is prose status text. LLM clients need
   a structured "which tool should I use for this user intent?" guide.

2. **Workflow tools overlap without a stable naming model**

   Existing workflow tools use mixed verbs: `analyze_`, `get_..._report`,
   `get_..._summary`, `get_..._results`. That is workable internally, but the
   public UX should make tool purpose clear at a glance.

3. **Failure responses are natural-language first**

   Several tools return strings such as "찾을 수 없습니다." That is readable for
   humans, but weak for LLM control flow. KoreaLawMCP's strongest lesson is that
   failure must be machine-readable.

4. **Raw API discovery is available but not framed**

   The raw path is powerful:

   `list_api_services(keyword)` -> `get_api_spec(service_id)` -> `call_api_raw(...)`

   It should be documented as a deliberate fallback path, not as an equal peer
   to user-facing workflow tools.

5. **README has to reflect actual tool behavior**

   The README should be organized by user job and public tool groups, not by
   internal service categories.

## Target UX Model

### Tool Groups

Use four public groups:

| Group | Purpose | Examples |
| --- | --- | --- |
| Workflow | Answer common legislative research jobs end-to-end | `issue_brief`, `bill_timeline`, `legislative_impact_map` |
| Verification | Check whether citations, names, IDs, and claims are real | `verify_legislative_claims` |
| Lookup | Stable atomic retrieval for entities and records | `search_bills`, `get_bill_details`, `get_committee_info` |
| Discovery | Explore all remaining National Assembly API datasets | `list_api_services`, `get_api_spec`, `call_api_raw` |

### Desired Public Surface

The target public surface should stay close to 15-18 tools. AssemblyMCP already
has 19 tools, so the redesign should prefer consolidation and contract cleanup
over adding many new tools.

Recommended target:

#### Workflow

- `issue_brief(topic)`
- `bill_timeline(bill_id)`
- `legislative_impact_map(target)`
- `watch_action_plan(topic)`
- `member_activity_brief(member_name)`
- `committee_work_brief(committee_name)`

#### Verification

- `verify_legislative_claims(citations_or_text)`

#### Lookup

- `search_bills(...)`
- `get_bill_details(bill_id)`
- `get_member_info(name)`
- `get_committee_info(...)`
- `search_meetings(...)`
- `get_plenary_schedule(...)`
- `get_member_voting_history(...)`
- `get_legislative_reports(keyword)`

#### Discovery

- `list_api_services(keyword)`
- `get_api_spec(service_id)`
- `call_api_raw(service_id, params)`
- `get_api_code_guide()`

### Naming Rules

Prefer names that describe the user's job:

- `*_brief`: compact, user-facing synthesis from multiple sources.
- `*_timeline`: chronological lifecycle.
- `*_impact_map`: relation graph or graph-ready relation list.
- `verify_*`: official-data verification with failure markers.
- `search_*`: list/search lookup.
- `get_*`: exact or near-exact entity retrieval.

Avoid adding more `analyze_*` tools unless they clearly return analytical
metrics rather than an entity brief.

## Proposed Workflow Tools

### `issue_brief(topic)`

User job: "What is happening in the National Assembly about this topic?"

Inputs:

- `topic: str`
- `age: str = "22"`
- `limit: int = 5`

Output sections:

- `topic`
- `bills`: related bills, status, proposer, committee
- `committees`: inferred committees and confidence
- `meetings`: relevant meeting records when discoverable
- `reports`: NABO/news references
- `voting_signal`: available voting summaries
- `follow_up`: suggested next tools and queries
- `warnings`: `[PARTIAL]` sections when subqueries fail

Internal sources:

- `BillService.search_bills`
- `MeetingService.search_meetings` / `get_meeting_records`
- `SmartService.get_legislative_reports`
- `BillService.get_bill_voting_summary`

### `bill_timeline(bill_id)`

User job: "What happened to this bill?"

This should either replace or wrap `get_bill_history`. The current
`get_bill_history` is close, but the redesigned contract should include stable
event types and source references.

Output event types:

- `introduced`
- `referred_to_committee`
- `committee_meeting`
- `plenary_vote`
- `final_disposition`
- `unknown`

Each event should include:

- `date`
- `event_type`
- `title`
- `source_tool`
- `source_id`
- `confidence`

### `legislative_impact_map(target)`

User job: "What is connected to this bill/topic/member/committee?"

This should return structured relations, not just prose.

Target types:

- `topic`
- `bill`
- `member`
- `committee`

Output:

- `nodes`: bills, members, committees, meetings, reports
- `edges`: relation type, source node, target node, evidence
- `mermaid`: optional graph text for compatible clients
- `top_followups`: next tool calls

Relation examples:

- `bill -> committee`: current committee
- `bill -> member`: proposer
- `bill -> meeting`: discussed in
- `bill -> vote`: voted in plenary
- `topic -> report`: related report/news

### `watch_action_plan(topic)`

User job: "How should I keep tracking or responding to this issue?"

This is the AssemblyMCP-native version of KoreaLawMCP's `action_plan`. It should
not give legal advice. It should give legislative monitoring steps.

Steps:

1. Normalize topic and alternate keywords.
2. Identify relevant bills and committees.
3. Identify meeting/schedule sources to monitor.
4. Identify voting/report signals.
5. Provide next queries and tool calls.

## Verification Contract

### Tool: `verify_legislative_claims(citations_or_text)`

This should verify structured citations and eventually free-form text.

Supported claim types:

- `bill`: bill title, `BILL_ID`, or `BILL_NO`
- `member`: member name
- `committee`: committee name or code
- `vote`: bill vote count/result claim
- `meeting`: committee/date/bill meeting claim

### Failure Markers

All verification and workflow tools should use shared markers:

| Marker | Meaning |
| --- | --- |
| `[NOT_FOUND]` | Official data lookup completed, no match found |
| `[AMBIGUOUS]` | Multiple plausible official matches |
| `[VERIFY_FAILED]` | User-provided claim conflicts with official data |
| `[API_FAILED]` | Official API failed, timed out, or returned invalid data |
| `[PARTIAL]` | Workflow returned useful data but one or more sections failed |

Marker payloads should include:

- `message`
- `attempted_queries`
- `source_tools`
- `suggested_next_queries`
- `llm_instruction`: for example, "Do not infer a missing result as fact."

## Compatibility Plan

1. Keep current tools while adding new workflow contracts.
2. Add new workflow tools as non-breaking wrappers.
3. Deprecate old workflow names only after README and examples migrate.
4. Keep raw discovery tools stable.
5. Do not rename raw tools in the first pass. Issue #48 can decide naming
   changes later.

## Implementation Phases

### Phase 0: Planning

- [x] Create tracking issue #60.
- [x] Start Gira ticket and branch.
- [x] Document current tool groups.
- [ ] Decide whether #60 supersedes or complements #48.
- [ ] Decide final names for workflow tools.
- [ ] Decide whether to keep a structured first-call guide tool.

### Phase 1: Failure and Verification Foundation

- [ ] Add shared response helpers for failure markers.
- [ ] Add tests for marker formatting.
- [ ] Implement `verify_legislative_claims` for bill/member/committee.
- [ ] Add vote and meeting claim verification.
- [ ] Ensure invalid input returns a machine-readable error.

### Phase 2: First Workflow Tool

- [ ] Implement `issue_brief(topic)` as the first end-to-end workflow.
- [ ] Limit output size with top-N and follow-up hints.
- [ ] Return `[PARTIAL]` when one section fails.
- [ ] Add mocked unit tests and one optional live smoke script.

### Phase 3: Timeline and Impact

- [ ] Upgrade or wrap `get_bill_history` as `bill_timeline`.
- [ ] Design `legislative_impact_map` relation schema.
- [ ] Add graph-ready output without requiring clients to render it.

### Phase 4: Documentation

- [ ] Rewrite README around user jobs and tool groups.
- [ ] Update README_EN in sync.
- [ ] Add examples for stdio, Streamable HTTP `/mcp`, and raw discovery.
- [ ] Document failure markers and LLM behavior rules.

## Open Questions

1. Should `get_assembly_info` remain prose, or should it become a structured
   first-call UX guide?
2. Should `analyze_legislative_issue` become `issue_brief`, or should both
   coexist for one release?
3. Should `get_representative_report` become `member_activity_brief`?
4. Should `get_committee_work_summary` become `committee_work_brief`?
5. Should raw tools be renamed as proposed in #48, or should they remain stable
   for compatibility?

## Non-Goals For The First PR

- No npm/npx packaging.
- No hosted connector deployment changes.
- No broad API wrapper expansion.
- No breaking tool removal.
- No legal advice or user action guidance beyond legislative monitoring.

## Verification Commands

Before merging implementation PRs:

```bash
uv run --frozen ruff check .
uv run --frozen pytest -q
```
