# Firefly III DataV Dashboard

A Flask-based dashboard that visualizes Firefly III withdrawal, deposit, and transfer trends across months and key dimensions.

## Features

- Aggregates Firefly III transactions for the current natural year by default, with optional custom periods
- Displays monthly trends for withdrawals, deposits, transfers, and net cashflow
- Highlights top categories and accounts contributing to spending and income
- Presents overall figures, monthly averages, and recency indicators in a large-screen friendly layout
- Parallelizes API calls and caches responses to accelerate repeated visits

## Prerequisites

- Python 3.10+
- An accessible Firefly III API endpoint and a personal access token with permission to read transactions

## Configuration

1. Copy `config.example.yaml` to `config.yaml`.
2. Edit `config.yaml` and set:
   - `api_base_url`: Base URL of your Firefly III instance (e.g., `https://firefly.example.com`).
   - `api_token`: Your Firefly III personal access token.
   - Optionally adjust `cache_ttl_minutes` to control how long dashboard data stays cached in memory.
   - Optionally configure the reporting window:
     - Set `months` to use a rolling N-month view ending in the configured end month (defaults to the current month).
     - Or add a `period` block with ISO dates to fix the range, e.g.:

       ```yaml
       period:
         start: "2023-01-01"
         end: "2023-12-31"
       ```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the App

```bash
flask --app app run --host 0.0.0.0 --port 5000
```

Open `http://localhost:5000` in your browser to view the dashboard.

## Notes

- Dashboard data is cached in memory for `cache_ttl_minutes` (default 10). Append `?refresh=1` to the URL to force a refresh.
- Ensure the configured token has sufficient permissions; otherwise API calls will fail.
- Network latency and the amount of historical data requested can impact the first load time, but cached visits reuse prior results.
