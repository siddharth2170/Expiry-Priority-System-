# Food Rescue & Expiry-Priority System

An internal system for a network of foodbanks to transfer surplus food between
each other **before it expires**, reducing waste. It includes a Streamlit
dashboard that maps foodbank locations, lets a foodbank raise food requests, and
runs a matching engine that recommends and confirms rescue transfers based on
expiry, urgency, and delivery distance.

## Requirements

- **Python 3.9–3.13** (the dependency stack ships prebuilt wheels for these
  versions; newer versions such as 3.14 may not have wheels yet)
- The Python packages listed in [`requirements.txt`](requirements.txt):

  | Package | Version | Purpose |
  | --- | --- | --- |
  | `streamlit` | `>=1.30` | Web dashboard framework |
  | `folium` | `>=0.15` | Interactive Leaflet maps |
  | `streamlit-folium` | `>=0.20` | Renders folium maps in Streamlit with click events |

## Running the app

The easiest way is the setup script:

```bash
./run.sh
```

This will:

1. Create a local virtual environment in `.venv/` (only on first run).
2. Activate it.
3. Upgrade `pip` and install everything from `requirements.txt`.
4. Launch the Streamlit app (`streamlit run app.py`).

Once running, Streamlit prints a local URL (default
[http://localhost:8501](http://localhost:8501)) — open it in your browser.

### Running manually

If you prefer to do it by hand:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Running the tests

The test suite uses Python's built-in `unittest` (no extra dependencies). From
the project root:

```bash
python3 -m unittest discover -s tests -t .
```

Add `-v` for verbose, per-test output:

```bash
python3 -m unittest discover -s tests -t . -v
```

The tests cover the custom `PriorityQueue`, the batch-based `FoodItem`/`Batch`
model, the `Inventory` ordering and lazy deletion, the `ExpiryLog`,
`FoodRequest` validation, the `DeliveryGraph` (Dijkstra routing), the
`MatchingEngine` (per-request ranking, contention-aware allocation, exclusions,
partial fills), and the `TransactionLog` / match execution.

## App structure

- **Food Rescue Network** (`app.py`) — home page with a map of our foodbank and
  the other foodbanks in the network. Grey lines are delivery routes; the green
  line is the engine's top recommended transfer for our hub; clicking a bank
  highlights the shortest path from our hub (blue). The click panel shows that
  bank's expiry-ordered inventory and, for other banks, whether our hub can
  serve one of its requests ("Match with our hub"). Below the map are the
  network's expired items and a running list of recent rescues (donations).
- **Food Requests** (`pages/1_Food_Requests.py`) — raise a request for a food
  category and quantity, and view our hub's open requests.
- **Transfer Matches** (`pages/2_Matches.py`) — the engine scores every
  `(request, source)` pairing on one scale (urgency, expiry pressure, and
  delivery distance) and then allocates scarce stock **best-first**, so a
  contested item goes to whichever bank the weights favour — a close, low-urgency
  need can beat a far, critical one, and vice versa. Each request shows its
  allocated transfer(s) plus the ranked alternatives for transparency. Confirm a
  match to rescue the food: it is removed from the source, logged as a donation,
  and the request is served. Rescued-units stats are shown per source foodbank.

### Core data structures (all custom, no library heaps/graphs)

- `PriorityQueue` — binary min-heap used everywhere below.
- `Inventory` — per-category expiry min-heaps for "what spoils first".
- `RequestQueue` — requests ranked by urgency blended with waiting time.
- `DeliveryGraph` — adjacency-map graph with Dijkstra shortest paths.
- `ExpiryLog` / `TransactionLog` — append-only logs of expired and rescued food.
- `MatchingEngine` (`src/matching/engine.py`) — `find_candidates` ranks sources
  for one request; `allocate` scores every `(request, source)` pairing and hands
  scarce stock to the best-scoring requests first (contention-aware), then
  executes confirmed rescues.

Foodbank, inventory, and request data is seeded from `src/data/sample_data.py`.
Session state (each browser session's mutable copy of the network) lives in
`src/app_state.py`.

## Performance & scalability

The pipeline includes four scalability optimizations: precomputed shortest paths
(one Dijkstra per destination, served by lookup), spatial-grid graph
construction (avoids the `O(V^2)` distance scan), cross-rerun caching with
in-place inventory updates (Streamlit reruns reuse derived structures), and the
contention-aware allocation described above. Each is documented — problem,
change, code location, complexity, tests, and how to tune in — in
[`OPTIMIZATIONS.md`](OPTIMIZATIONS.md).
