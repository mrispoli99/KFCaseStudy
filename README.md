# KnowFully case: Q4 2026 commercial view

A Streamlit prototype of the executive view from the case readout, built on the synthetic case data.

## Run it

```bash
cd knowfully_dashboard
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

It opens at http://localhost:8501.

## What's in it

| Tab | Shows |
|---|---|
| Executive view | Six headline measures, forecast vs plan by brand, exception flags, initiatives, review cadence |
| Q4 forecast | Roll-up vs plan, chance of booking at least $X, deal-level expected value, prior Q4s, method and data notes |
| B2C measurement | Platform vs GA4 ROAS by channel, the one test to run, brand-month vs Finance |

Assumptions are fixed at the forecast workbook's defaults, so the numbers match the workbook and the deck (base $141,657; low $80,689; high $165,263; 57.1% chance of plan). To change one, edit `Assumptions` in `forecast.py`.

## Files

- `app.py`: the Streamlit layout and charts (Vega-Lite, bundled with Streamlit)
- `forecast.py`: all calculations in plain pandas/numpy, testable without Streamlit
- `data/Synthetic_Case_Data_1.xlsx`: the case workbook (synthetic data)
- `.streamlit/config.toml`: KnowFully-matched theme
