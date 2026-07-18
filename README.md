# Food Rescue & Expiry-Priority System

An internal system for a network of foodbanks to transfer surplus food between
each other **before it expires**, reducing waste. It includes a Streamlit
dashboard that maps foodbank locations and lets a foodbank raise food requests.

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

## App structure

- **Food Rescue Network** (`app.py`) — home page with a map of our foodbank and
  the other foodbanks in the network. Click a marker to see its detail panel.
- **Food Requests** (`pages/1_Food_Requests.py`) — raise a request for a food
  category and quantity, and view open requests.

Foodbank and inventory data is seeded from `src/data/sample_data.py`.
