# Stock Dashboard

FastAPI backend + React/TypeScript frontend with TradingView Lightweight Charts v5.
Four stacked panes: RSI, price, volume, MACD. Timeframes: D, W, M, Q, Y, 5Y.

## Run the backend (terminal 1)
    cd backend
    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

Check it: http://localhost:8000/api/chart/AAPL?timeframe=D

## Run the frontend (terminal 2)
    cd frontend
    npm install
    npm run dev

Open http://localhost:5173
