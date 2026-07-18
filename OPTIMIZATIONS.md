# Scalability Optimizations

This document describes the four scalability optimizations applied to the
Expiry-Priority-System matching pipeline. For each one it covers **what problem
it solves**, **what we changed**, **where the code lives**, the **complexity
before → after**, the **tests that verify it**, and **how to tune or extend it**.

The core flow is: build a delivery graph of foodbanks → precompute shortest
paths → score every feasible `(request, source)` pairing → greedily allocate
scarce stock best-first. All four optimizations target either the graph/pathing
work or the per-interaction recompute cost in the Streamlit UI. Everything is
grounded in the current source; the referenced tests all pass via
`python3 -m unittest discover -s tests` (100 tests).

---

## 1. Precomputed shortest paths (Dijkstra once per destination)

**Problem.** The naive approach runs Dijkstra separately for every
`(request, source)` pair when computing delivery distance and route. With `R`
requests and `S` candidate sources that is up to `R * S` full Dijkstra runs, and
most of that work is redundant because many pairs share the same destination.

**What we did.** Because the delivery graph is undirected, a single Dijkstra run
rooted at a *destination* answers the distance and route from **every** source
to that destination. We run Dijkstra once per distinct requester and cache the
result, then serve all distance/route queries by dictionary lookup.

- `DeliveryGraph.dijkstra(source)` returns `(distances, predecessors)` — the
  `dist` map (`dist[node]` = shortest distance from `source`) and the `prev` map
  (`prev[node]` = node reached just before `node`). It uses lazy deletion on the
  custom `PriorityQueue` (a node can be queued multiple times; repeats are
  skipped after the first pop).
- `build_path_index(graph, destinations)` builds
  `{dest_id: (distances, predecessors)}`, one Dijkstra run per **distinct**
  destination. It uses `dict.fromkeys(destinations)` so duplicate requesters are
  solved only once (order preserved).
- `_distance(paths, source, dest)` returns `dist.get(source)` from the cached
  entry (or `None` if unreachable). `_route(paths, source, dest)` rebuilds the
  hop list by walking `prev` from `source` toward `dest`.
- **Route reconstruction is deferred until a pairing wins/returns.** In
  `find_candidates`, candidates are scored with `route=[]`, and `_route` is only
  called for the returned `top_n` after they are popped from the heap. In
  `allocate`, `_route` is only called for pairings that actually win stock (most
  scored pairs lose contention and are discarded, so their routes are never
  built).

**Where.**
- `src/data_structures/delivery_graph.py` → `DeliveryGraph.dijkstra`
- `src/matching/engine.py` → `build_path_index`, `PathIndex` (a `dict` alias),
  `_distance`, `_route`, and the deferred-route loops in `find_candidates` and
  `allocate`. `find_all` builds one path index for all ordered requesters and
  threads it through every `find_candidates` call.

**Complexity.**

| Aspect | Before | After |
| --- | --- | --- |
| Dijkstra runs | one per `(request, source)` pair — up to `R * S` | one per distinct requester — `D ≤ R` |
| Distance query | full Dijkstra | `O(1)` dict lookup |
| Route builds | one per scored pair | only for returned/winning pairings |

(Each Dijkstra run is `O(E log V)` with the binary-heap `PriorityQueue`.)

**How it's verified** (`tests/test_matching_engine.py`, `tests/test_delivery_graph.py`):
- `TestPathIndex.test_distance_and_route_match_shortest_path` — indexed distance
  and route equal `graph.shortest_path`.
- `TestPathIndex.test_unreachable_distance_is_none` — unreachable → `None` /
  empty route.
- `TestPathIndex.test_dedupes_destinations` — duplicate destinations solved once.
- `TestPrecomputedParity.test_allocate_parity_with_and_without_paths` and
  `TestPrecomputedParity.test_find_candidates_parity_with_and_without_paths` —
  passing a prebuilt index yields identical results to building on the fly.
- `TestDijkstra.test_distances_match_shortest_distances`,
  `TestDijkstra.test_predecessors_rebuild_shortest_path`,
  `TestDijkstra.test_unreachable_absent_from_distances` — `dijkstra` output is
  correct and its predecessors rebuild the route (rooted at the destination).

**How to tune or extend.**
- To support new query types (e.g. nearest-K), add helpers alongside `_distance`
  / `_route` that read from the same `(dist, prev)` entries — no extra Dijkstra
  needed.
- The index is only valid while edge weights are unchanged. If graph topology or
  weights change, rebuild it (see optimization 3 for how the UI handles this —
  coordinates are static, so the index is built once per session).
- If the destination set grows large and sparse, consider bidirectional or
  goal-directed search per query instead of full single-source runs.

---

## 2. Spatial-grid graph construction

**Problem.** Building the delivery graph by measuring every pair of banks is
`O(V^2)` haversine calls. With a distance threshold, most of those pairs are too
far to ever become an edge, so the vast majority of the haversine work is wasted.

**What we did.** `DeliveryGraph.from_foodbanks(foodbanks, threshold_km)` buckets
banks into a spatial grid and only measures banks that could possibly be within
`threshold_km`:

- Coordinates are projected onto an approximate local km plane: `ky = 111.0`
  km per degree latitude, and `kx = 111.0 * cos(radians(max_abs_lat))` km per
  degree longitude (falling back to `1e-9` to avoid divide-by-zero). Using the
  **largest** `|latitude|` in the set gives the smallest `kx`, so east–west
  distance is never *over*-estimated — which guarantees no close pair is ever
  bucketed too far apart and missed.
- Banks are placed into grid cells of side `threshold_km`. Two banks within the
  threshold must fall in the same or an adjacent cell, so each bank only compares
  against its own cell and the 8 neighbours (a 3×3 window).
- The **exact haversine still gates every edge** (`if distance <= threshold_km`).
  The grid only prunes far pairs; it never decides an edge on its own, so the
  result is identical to a brute-force scan. A `seen` set of `frozenset` pairs
  ensures each unordered pair is measured once.
- The dense `O(V^2)` path is deliberately **kept** when `threshold_km is None`
  (fully-connected graph), where every pair is an edge and pruning buys nothing.

**Where.**
- `src/data_structures/delivery_graph.py` → `DeliveryGraph.from_foodbanks`
  (dispatch + dense path) and `DeliveryGraph._add_edges_via_grid` (grid path);
  `haversine` is the exact distance gate.
- `src/matching/engine.py` → `graph_for` calls `from_foodbanks` with
  `DELIVERY_THRESHOLD_KM` from `src/constants.py`.

**Complexity.**

| Path | Haversine calls | When used |
| --- | --- | --- |
| Dense (`threshold_km is None`) | `O(V^2)` | fully-connected graph |
| Grid (`threshold_km` set) | `~O(V * avg_neighbors)` | sparse, thresholded graph |

**How it's verified** (`tests/test_delivery_graph.py`):
- `TestGridConstruction.test_grid_matches_brute_force_various_thresholds` — grid
  edges equal brute-force edges across thresholds `0.5 … 200.0`.
- `TestGridConstruction.test_grid_matches_brute_force_high_latitude` — correct
  near the poles, where longitude degrees are short (small `kx`).
- `TestGridConstruction.test_grid_handles_empty_and_single` — empty and
  single-bank inputs produce no edges and don't error.
- `TestDeliveryGraph.test_from_foodbanks_fully_connected` — no threshold →
  every pair connected.
- `TestDeliveryGraph.test_from_foodbanks_threshold_sparsifies` — a threshold
  drops long edges and forces multi-hop routing.

**How to tune or extend.**
- `DELIVERY_THRESHOLD_KM` (`src/constants.py`, currently `4.5`) sets both the
  edge cutoff and the grid cell size; it is shared by the map visualization and
  the matching engine so their distances agree. Raising it links more banks
  directly (denser graph, larger cells); lowering it sparsifies further.
- The grid assumes a roughly local region (single projection plane). For a truly
  global dataset spanning many latitudes, switch to a per-band projection or a
  geospatial index (e.g. an R-tree / geohash).
- Any change here must preserve edge-for-edge parity with the brute-force scan —
  the `TestGridConstruction` tests enforce this.

---

## 3. Cross-rerun caching + incremental inventory updates (Streamlit)

**Problem.** Streamlit reruns the entire script on every interaction — including
idle interactions like clicking a map marker. Rebuilding the graph, path index,
per-bank inventories, and the full allocation plan on every rerun makes the UI
scale with interaction count, not with actual data changes.

**What we did.** Derived structures are cached in `st.session_state` and only
recomputed when their inputs actually change:

- **Graph and path index are built once per session.** `get_graph` builds the
  delivery graph on first use and stores it under `GRAPH_KEY`; `get_path_index`
  builds one Dijkstra per bank and stores it under `PATHIDX_KEY`. Both depend
  only on (static) coordinates, so they are never rebuilt during a session.
- **Inventories are persistent and mutated in place.** `get_inventories` builds
  `{foodbank_id: Inventory}` once (`INVENTORIES_KEY`). It is safe to keep
  long-lived because `Inventory.by_category` / `items` read live from `_by_id`
  plus `active_batches()`, so in-place batch changes show up without a rebuild.
  `add_food_item` calls `inventories[hub_id].add(item)` and `confirm_match`
  calls `inventories[source].remove(food_id)` when a product is depleted —
  incremental edits rather than full rebuilds.
- **Allocations are memoized on a network-version counter.**
  `get_allocations` keys the cached plan (`ALLOC_KEY`) on
  `(_version(), today.toordinal())`. It recomputes only when the key changes.
  The version counter lives under `VERSION_KEY` (`"network_version"`), starts at
  `0` in `_ensure_state`, is read by `_version`, and is incremented by
  `_bump_version`. Every mutation of stock or requests bumps it:
  `add_food_item`, `add_request`, `remove_request`, `reduce_request`,
  `record_donation`, and `confirm_match`. Idle reruns leave the version
  unchanged, so the cached allocation plan is reused verbatim.
- Seed data is deep-copied into session state in `_ensure_state`, so mutations
  never touch the pristine module-level data.

**Where.**
- `src/app_state.py` → keys `GRAPH_KEY`, `PATHIDX_KEY`, `INVENTORIES_KEY`,
  `ALLOC_KEY`, `VERSION_KEY`; functions `_ensure_state`, `_version`,
  `_bump_version`, `get_graph`, `get_path_index`, `get_inventories`,
  `get_allocations`, `add_food_item`, `confirm_match` (and the other mutators
  that bump the version).
- `get_allocations` passes the cached `paths` and `inv_by_source` into
  `allocate`, tying this optimization back to #1 and #4.

**Complexity.**

| Work | Per idle rerun (before) | Per idle rerun (after) |
| --- | --- | --- |
| Graph build | rebuilt | reused (`O(1)`) |
| Path index | rebuilt | reused (`O(1)`) |
| Inventories | rebuilt | reused, edited in place |
| Allocation plan | recomputed | reused when version unchanged (`O(1)`) |

**How it's verified.** This is UI/session wiring around the engine, so it is
exercised indirectly rather than by a dedicated Streamlit test. The correctness
of the underlying pieces it caches is covered by
`TestPrecomputedParity.test_allocate_parity_with_and_without_paths` (passing a
prebuilt `paths` / inventories does not change results) and the full
`TestAllocate` / `TestPathIndex` suites. The whole suite runs green with
`python3 -m unittest discover -s tests`.

**How to tune or extend.**
- Any **new** mutation of stock or requests must call `_bump_version()`, or the
  memoized allocation plan will go stale. This is the single invariant to respect
  when extending state.
- If coordinates ever become mutable (e.g. adding/removing foodbanks at runtime),
  invalidate `GRAPH_KEY` and `PATHIDX_KEY` too — they are currently assumed
  static for the session.
- The allocation cache key also includes `today.toordinal()`, so the plan
  refreshes when the day rolls over (expiry/aging shift). Extend the key if you
  add other time- or context-dependent inputs.

---

## 4. Contention-aware allocation

**Problem.** Ranking sources for each request in isolation (as `find_candidates`
does) doesn't resolve **contention**: when several banks want the same scarce
stock, someone has to lose. A per-request view can hand the same item to
everyone.

**What we did.** `allocate` scores **every** feasible `(request, source)`
pairing on one shared scale and commits greedily best-first, decrementing sources
as stock is claimed:

- **Scoring** (`score_pair`) blends four signals into one number where *lower is
  better* (to match the min-heap `PriorityQueue`):

  ```
  score = MATCH_W_URG * urgency.value
        + MATCH_W_EXP * days_to_expiry
        + MATCH_W_DIST * distance_km
        - MATCH_W_AGE * age_days
  ```

  Weights come from `src/constants.py`: `MATCH_W_URG = 10.0` (per urgency level;
  `CRITICAL=0` is best so urgent needs score lower), `MATCH_W_EXP = 2.0` (per day
  of shelf life — favour rescuing soonest-to-spoil), `MATCH_W_DIST = 1.0` (per
  km travelled), `MATCH_W_AGE = 1.0` (per day a request has waited; older
  requests drift ahead). `age_days = max(0, (today - request.submitted_at).days)`.
- **Greedy allocation.** Every pairing is pushed onto one min-heap keyed on
  score. Draining best-first, each pop is the globally best still-standing
  pairing. Shared ledgers — `remaining_need` per request and `remaining_stock`
  per `(source_id, food_id)` — let competing pairings see each other's
  commitments. `fill = min(need, available)` supports **partial fulfillment**, so
  a request can be filled across several sources and one source can serve several
  requests until it runs dry.
- **Per-source precompute.** Before the scoring loop, `soonest_by_source` caches
  each source's soonest-to-expire line per category once
  (`src -> category -> (item, batch)`), turning the inner loop into an `O(1)`
  lookup instead of rebuilding a category heap per pair.
- **Deferred routes.** `_route` is called only for pairings that actually win
  stock (ties back to optimization #1).

**Why urgency stays in the score.** Standalone requests are already ordered by
the `RequestQueue` (urgency blended with waiting time), so within a *single*
request urgency and aging are constant and only distance/expiry separate its
candidate sources. But `allocate` compares pairings from **different** requests
against each other for the same stock — that is exactly where urgency must bite,
so a more urgent need can outweigh a cheaper (closer) delivery, and vice versa.
Removing urgency from the score would let a low-priority, nearby request steal
scarce stock from a critical, slightly-farther one.

**Where.**
- `src/matching/engine.py` → `score_pair`, `allocate` (heap + `remaining_need` /
  `remaining_stock` ledgers + `soonest_by_source`), `MatchCandidate` fields
  (`fill_quantity`, `is_partial`).
- `src/matching/models.py` → `MatchCandidate` (with `is_partial` =
  `fill_quantity < request.quantity`).
- `src/constants.py` → the four `MATCH_W_*` weights.

**Complexity.**

| Aspect | Detail |
| --- | --- |
| Pairings scored | `O(R * S)` `(request, source)` pairs |
| Distance per pair | `O(1)` index lookup (optimization #1) |
| Soonest-line per pair | `O(1)` from `soonest_by_source` |
| Allocation drain | one heap pop per pairing, best-first |
| Routes built | only for winning pairings |

**How it's verified** (`tests/test_matching_engine.py`):
- `TestAllocate.test_scarce_stock_goes_to_better_scoring_request` — closer of two
  equal-urgency requests wins the single source; loser gets nothing.
- `TestAllocate.test_urgency_wins_when_distances_are_close` — CRITICAL-but-far
  beats LOW-but-close for a small distance gap.
- `TestAllocate.test_proximity_wins_when_far_enough` — a large distance gap lets
  LOW-close out-score CRITICAL-far (the trade-off runs both ways).
- `TestAllocate.test_request_filled_across_multiple_sources` — a request larger
  than any one source draws from the best sources first (`A: 10, B: 5`).
- `TestAllocate.test_one_source_serves_two_requests_until_dry` — leftover stock
  partially fills the next-best request (`is_partial`).
- `TestFindCandidates.*` (e.g. `test_returns_top_two_in_score_order`,
  `test_soon_expiry_can_outweigh_distance`, `test_partial_fill_when_stock_below_request`)
  cover the shared `score_pair` scoring and partial-fill behaviour.
- `TestFindAll.test_orders_requests_by_urgency` — `find_all` returns requests
  most-urgent-first via the `RequestQueue`.

**How to tune or extend.**
- Adjust the four `MATCH_W_*` weights in `src/constants.py` to change the
  trade-off. Their relative magnitudes are what matter: e.g. raising
  `MATCH_W_URG` makes urgency dominate distance; raising `MATCH_W_AGE` makes old
  requests surface faster. The `test_*_wins_when_*` tests encode concrete
  break-even points, so update them if you retune.
- To add a new signal (e.g. a route-hop penalty or perishability class), add a
  weight constant and a term to `score_pair` — every caller (`find_candidates`,
  `allocate`) picks it up automatically because they share the function.
- Greedy allocation is fast and predictable but not globally optimal. If you need
  optimal contention resolution, replace the greedy drain with a min-cost
  matching / assignment solver over the same scored pairs.

---

## How to run the tests

```bash
python3 -m unittest discover -s tests
```
