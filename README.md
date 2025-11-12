# Firefly III DataV Dashboard

A Flask-based dashboard that visualizes Firefly III withdrawal, deposit, and transfer trends across months and key dimensions.

## Features

- Aggregates Firefly III transactions for the last N months (configurable, default 12)
- Displays monthly trends for withdrawals, deposits, and transfers
- Highlights top categories and accounts contributing to spending and income
- Presents overall figures in a large-screen friendly layout

## Prerequisites

- Python 3.10+
- An accessible Firefly III API endpoint and a personal access token with permission to read transactions

## Configuration

1. Copy `config.example.yaml` to `config.yaml`.
2. Edit `config.yaml` and set:
   - `api_base_url`: Base URL of your Firefly III instance (e.g., `https://firefly.example.com`).
   - `api_token`: Your Firefly III personal access token.
   - Optionally adjust `months` to control how many months of history are shown.

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

- The application caches nothing; each page load fetches the latest data from Firefly III.
- Ensure the configured token has sufficient permissions; otherwise API calls will fail.
- Network latency and the amount of historical data requested can impact load time.
