from __future__ import annotations

import os

import time
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.observability.metrics import RATE_LIMIT_REQUESTS, EVALUATION_LATENCY

from app.config import load_config
from app.logger import get_logger
from app.middleware.limiter_middleware import RateLimitMiddleware
from app.nodes.node_app import NodeRuntime
from app.services.rate_limit_service import RateLimitService
from app.storage.redis_store import RedisQuotaStore

logger = get_logger(__name__)


class RateLimitRequest(BaseModel):
    request_id: str = Field(..., example="req-1")


class RateLimitResponse(BaseModel):
    status: str
    reason: str
    customer_id: str
    request_id: str
    node_id: str
    retry_after: int | None = None
    limit: int | None = None
    remaining: int | None = None
    policy: str | None = None
    exception_applied: bool = False


config = load_config(os.getenv("RATE_LIMIT_CONFIG_PATH"))

store = RedisQuotaStore(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=int(os.getenv("REDIS_DB", "0")),
    decode_responses=True,
    algorithm=os.getenv("RATE_LIMIT_ALGORITHM", config.algorithm),
)
quota = int(os.getenv("RATE_LIMIT_QUOTA", config.default_rpm))
window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", config.window_seconds))
service = RateLimitService(store=store, quota=quota, window_seconds=window_seconds, customer_policies=config.customers)
middleware = RateLimitMiddleware(service)
node_id = os.getenv("NODE_ID", "node-1")
runtime = NodeRuntime(middleware, node_id=node_id)

app = FastAPI(title="RelayAPI Rate Limiter", version="1.0.0")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    from app.logger import set_request_id
    req_id = request.headers.get("X-Request-Id") or request.headers.get("X-Correlation-Id")
    if req_id:
        set_request_id(req_id)
    try:
        logger.info("incoming_request", extra={"path": request.url.path, "method": request.method})
        response = await call_next(request)
        logger.info("response", extra={"status_code": response.status_code})
        return response
    finally:
        set_request_id(None)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index():
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RelayAPI Rate Limiter Dashboard</title>
    <meta name="description" content="Interactive developer dashboard and rate limiter playground for RelayAPI.">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #090d16;
            --bg-card: rgba(30, 41, 59, 0.4);
            --border-color: rgba(255, 255, 255, 0.08);
            --primary: #38bdf8;
            --primary-glow: rgba(56, 189, 248, 0.15);
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.15);
            --danger: #ef4444;
            --danger-glow: rgba(239, 68, 68, 0.15);
            --warning: #f59e0b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-main);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(56, 189, 248, 0.05) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.05) 0%, transparent 40%);
        }

        header {
            border-bottom: 1px solid var(--border-color);
            background: rgba(15, 23, 42, 0.6);
            backdrop-filter: blur(12px);
            position: sticky;
            top: 0;
            z-index: 10;
        }

        .header-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 1.25rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo-area {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .logo-icon {
            width: 2rem;
            height: 2rem;
            background: linear-gradient(135deg, var(--primary) 0%, #0284c7 100%);
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1.2rem;
            box-shadow: 0 0 15px var(--primary-glow);
        }

        h1 {
            font-size: 1.25rem;
            font-weight: 600;
            letter-spacing: -0.025em;
            background: linear-gradient(to right, #ffffff, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .badge-node {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            padding: 0.35rem 0.75rem;
            border-radius: 20px;
            font-size: 0.8rem;
            color: var(--primary);
            font-family: 'JetBrains Mono', monospace;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .badge-node::before {
            content: '';
            display: inline-block;
            width: 6px;
            height: 6px;
            background-color: var(--success);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--success);
        }

        main {
            max-width: 1200px;
            margin: 2.5rem auto;
            padding: 0 2rem;
            width: 100%;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2.5rem;
            flex-grow: 1;
        }

        @media (max-width: 900px) {
            main {
                grid-template-columns: 1fr;
                gap: 2rem;
            }
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 2rem;
            backdrop-filter: blur(16px);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .card-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #ffffff;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.75rem;
            margin-bottom: 0.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        label {
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--text-muted);
        }

        .input-wrapper {
            position: relative;
        }

        input {
            width: 100%;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            color: var(--text-main);
            font-family: inherit;
            font-size: 0.95rem;
            outline: none;
            transition: var(--transition);
        }

        input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 10px var(--primary-glow);
        }

        .presets {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.5rem;
        }

        .preset-btn {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            padding: 0.35rem 0.75rem;
            border-radius: 6px;
            font-size: 0.8rem;
            cursor: pointer;
            color: var(--text-muted);
            transition: var(--transition);
        }

        .preset-btn:hover, .preset-btn.active {
            background: var(--primary-glow);
            border-color: var(--primary);
            color: #ffffff;
        }

        .btn-group {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 1rem;
            margin-top: 1rem;
        }

        button.btn-primary {
            background: linear-gradient(135deg, var(--primary) 0%, #0284c7 100%);
            border: none;
            color: #000000;
            font-weight: 600;
            padding: 0.85rem 1.5rem;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.95rem;
            transition: var(--transition);
            box-shadow: 0 4px 12px rgba(56, 189, 248, 0.25);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }

        button.btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(56, 189, 248, 0.4);
            filter: brightness(1.1);
        }

        button.btn-secondary {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            color: var(--danger);
            font-weight: 500;
            padding: 0.85rem 1rem;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.95rem;
            transition: var(--transition);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }

        button.btn-secondary:hover {
            background: var(--danger-glow);
            border-color: var(--danger);
        }

        .status-tracker {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid var(--border-color);
            padding: 1.25rem;
            border-radius: 8px;
        }

        .tracker-item {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .tracker-val {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.5rem;
            font-weight: 600;
            color: #ffffff;
        }

        .tracker-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .progress-container {
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 0.5rem;
        }

        .progress-bar {
            height: 100%;
            width: 100%;
            background: linear-gradient(90deg, var(--success) 0%, var(--primary) 100%);
            border-radius: 3px;
            transition: width 0.4s ease;
        }

        .progress-bar.warning {
            background: var(--warning);
        }

        .progress-bar.danger {
            background: var(--danger);
        }

        .logs-container {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            max-height: 400px;
            overflow-y: auto;
            padding-right: 0.5rem;
        }

        .logs-container::-webkit-scrollbar {
            width: 6px;
        }
        .logs-container::-webkit-scrollbar-track {
            background: transparent;
        }
        .logs-container::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }

        .log-item {
            background: rgba(15, 23, 42, 0.5);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            animation: slideIn 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28) forwards;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .log-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .log-meta {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-size: 0.8rem;
            color: var(--text-muted);
        }

        .log-customer {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 500;
            color: var(--primary);
        }

        .log-req-id {
            font-family: 'JetBrains Mono', monospace;
        }

        .status-badge {
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            text-transform: uppercase;
        }

        .status-badge.accepted {
            background: var(--success-glow);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .status-badge.rejected {
            background: var(--danger-glow);
            color: var(--danger);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .log-details {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.5rem;
            font-size: 0.75rem;
            color: var(--text-muted);
            border-top: 1px dashed var(--border-color);
            padding-top: 0.5rem;
        }

        .detail-field span {
            font-family: 'JetBrains Mono', monospace;
            color: #ffffff;
        }

        .toast {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid var(--border-color);
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            gap: 0.75rem;
            z-index: 100;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        .toast.show {
            transform: translateY(0);
            opacity: 1;
        }

        .toast.success {
            border-left: 4px solid var(--success);
        }

        .toast.error {
            border-left: 4px solid var(--danger);
        }
    </style>
</head>
<body>
    <header>
        <div class="header-container">
            <div class="logo-area">
                <div class="logo-icon">R</div>
                <h1>RelayAPI Rate Limiter</h1>
            </div>
            <div id="node-badge" class="badge-node">node-1</div>
        </div>
    </header>

    <main>
        <div class="card">
            <div class="card-title">
                <span>Playground</span>
                <span style="font-size: 0.8rem; font-weight: normal; color: var(--text-muted)">Configure and send a request</span>
            </div>

            <div class="form-group">
                <label for="customer-input">Customer ID</label>
                <div class="input-wrapper">
                    <input type="text" id="customer-input" value="cust-1">
                </div>
                <div class="presets">
                    <button class="preset-btn active" data-id="cust-1">cust-1 (Default)</button>
                    <button class="preset-btn" data-id="northwind">northwind (Enterprise)</button>
                    <button class="preset-btn" data-id="alpha">alpha (Local)</button>
                    <button class="preset-btn" data-id="beta">beta (Local)</button>
                </div>
            </div>

            <div class="form-group">
                <label for="request-input">Request ID</label>
                <input type="text" id="request-input" readonly>
            </div>

            <div class="status-tracker">
                <div class="tracker-item">
                    <span id="tracker-remaining" class="tracker-val">-</span>
                    <span class="tracker-label">Remaining Quota</span>
                </div>
                <div class="tracker-item">
                    <span id="tracker-limit" class="tracker-val">-</span>
                    <span class="tracker-label">Limit (RPM)</span>
                </div>
                <div style="grid-column: span 2;">
                    <div class="progress-container">
                        <div id="tracker-progress" class="progress-bar"></div>
                    </div>
                </div>
            </div>

            <div class="btn-group">
                <button id="btn-submit" class="btn-primary">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                    Send Request
                </button>
                <button id="btn-reset" class="btn-secondary">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"></path></svg>
                    Reset Window
                </button>
            </div>
        </div>

        <div class="card">
            <div class="card-title">
                <span>Evaluation History</span>
                <span id="log-count" class="preset-btn" style="cursor: default;">0 Requests</span>
            </div>
            <div id="logs-list" class="logs-container">
                <div style="text-align: center; color: var(--text-muted); padding: 3rem 0;">
                    No requests sent in this session yet.
                </div>
            </div>
        </div>
    </main>

    <div id="toast" class="toast">
        <span id="toast-text">Success!</span>
    </div>

    <script>
        const nodeBadge = document.getElementById('node-badge');
        const customerInput = document.getElementById('customer-input');
        const requestInput = document.getElementById('request-input');
        const btnSubmit = document.getElementById('btn-submit');
        const btnReset = document.getElementById('btn-reset');
        const logsList = document.getElementById('logs-list');
        const logCountBadge = document.getElementById('log-count');
        const toast = document.getElementById('toast');
        const toastText = document.getElementById('toast-text');

        const trackerRemaining = document.getElementById('tracker-remaining');
        const trackerLimit = document.getElementById('tracker-limit');
        const trackerProgress = document.getElementById('tracker-progress');

        let requestIndex = 1;
        let logs = [];

        function generateRequestId() {
            const date = new Date();
            const timeStr = date.toTimeString().split(' ')[0].replace(/:/g, '');
            requestInput.value = `req-${timeStr}-${Math.floor(Math.random() * 1000)}`;
        }

        // Initialize request id
        generateRequestId();

        // Customer Preset click
        document.querySelectorAll('.preset-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                customerInput.value = btn.dataset.id;
                updateTrackerFromLast(btn.dataset.id);
            });
        });

        customerInput.addEventListener('input', () => {
            document.querySelectorAll('.preset-btn').forEach(b => {
                if (b.dataset.id === customerInput.value) {
                    b.classList.add('active');
                } else {
                    b.classList.remove('active');
                }
            });
            updateTrackerFromLast(customerInput.value);
        });

        function updateTrackerFromLast(customerId) {
            const customerLogs = logs.filter(l => l.customer_id === customerId);
            if (customerLogs.length > 0) {
                const last = customerLogs[0]; // array is unshifted
                updateTracker(last.remaining, last.limit);
            } else {
                trackerRemaining.innerText = '-';
                trackerLimit.innerText = '-';
                trackerProgress.style.width = '100%';
                trackerProgress.className = 'progress-bar';
            }
        }

        function updateTracker(remaining, limit) {
            if (remaining === null || limit === null) {
                trackerRemaining.innerText = '-';
                trackerLimit.innerText = '-';
                trackerProgress.style.width = '100%';
                trackerProgress.className = 'progress-bar';
                return;
            }

            trackerRemaining.innerText = remaining;
            trackerLimit.innerText = limit;

            const percentage = limit > 0 ? (remaining / limit) * 100 : 0;
            trackerProgress.style.width = `${percentage}%`;

            if (percentage < 20) {
                trackerProgress.className = 'progress-bar danger';
            } else if (percentage < 50) {
                trackerProgress.className = 'progress-bar warning';
            } else {
                trackerProgress.className = 'progress-bar';
            }
        }

        function showToast(text, type = 'success') {
            toastText.innerText = text;
            toast.className = `toast show ${type}`;
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }

        // Submit Request
        btnSubmit.addEventListener('click', async () => {
            const customerId = customerInput.value.trim();
            const requestId = requestInput.value.trim();

            if (!customerId) {
                showToast('Please enter a Customer ID', 'error');
                return;
            }

            btnSubmit.disabled = true;
            btnSubmit.innerText = 'Evaluating...';

            try {
                const response = await fetch('/request', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Customer-Id': customerId
                    },
                    body: JSON.stringify({ request_id: requestId })
                });

                const data = await response.json();
                
                // Add to history
                addLogItem(data, response.status);
                
                // Update tracker
                updateTracker(data.remaining, data.limit);

                if (response.status === 200) {
                    showToast(`Request accepted! (Remaining: ${data.remaining})`, 'success');
                } else if (response.status === 429) {
                    showToast(`Rejected: Quota exceeded. Retry in ${data.retry_after}s`, 'error');
                } else {
                    showToast(`Error: ${data.reason || 'Invalid request'}`, 'error');
                }
            } catch (e) {
                showToast('Failed to contact server', 'error');
                console.error(e);
            } finally {
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Send Request`;
                generateRequestId();
            }
        });

        // Reset Customer Window
        btnReset.addEventListener('click', async () => {
            const customerId = customerInput.value.trim();
            if (!customerId) {
                showToast('Please enter a Customer ID to reset', 'error');
                return;
            }

            btnReset.disabled = true;
            try {
                const response = await fetch(`/reset/${customerId}`, {
                    method: 'POST'
                });
                const data = await response.json();
                if (response.ok) {
                    showToast(`Reset window for ${customerId}`, 'success');
                    updateTracker(data.limit || 100, data.limit || 100);
                } else {
                    showToast('Failed to reset customer window', 'error');
                }
            } catch (e) {
                showToast('Failed to reset customer window', 'error');
                console.error(e);
            } finally {
                btnReset.disabled = false;
            }
        });

        function addLogItem(data, statusCode) {
            if (logs.length === 0) {
                logsList.innerHTML = '';
            }

            // Unshift to put at top
            logs.unshift(data);
            logCountBadge.innerText = `${logs.length} Request${logs.length > 1 ? 's' : ''}`;

            const nodeBadgeVal = data.node_id || 'node-1';
            nodeBadge.innerText = nodeBadgeVal;

            const isAccepted = data.status === 'accepted';
            const logItem = document.createElement('div');
            logItem.className = 'log-item';
            
            logItem.innerHTML = `
                <div class="log-header">
                    <div class="log-meta">
                        <span class="log-customer">${data.customer_id}</span>
                        <span class="log-req-id">${data.request_id}</span>
                    </div>
                    <span class="status-badge ${isAccepted ? 'accepted' : 'rejected'}">
                        ${isAccepted ? 'Accepted' : '429 Rejected'}
                    </span>
                </div>
                <div class="log-details">
                    <div class="detail-field">Limit: <span>${data.limit ?? '-'}</span></div>
                    <div class="detail-field">Remaining: <span>${data.remaining ?? '-'}</span></div>
                    <div class="detail-field">Node: <span>${data.node_id}</span></div>
                    <div class="detail-field">Policy: <span>${data.policy}</span></div>
                    <div class="detail-field">Exception: <span>${data.exception_applied ? 'Yes' : 'No'}</span></div>
                    <div class="detail-field">${!isAccepted && data.retry_after ? 'Retry: <span>' + data.retry_after + 's</span>' : ''}</div>
                </div>
            `;

            logsList.insertBefore(logItem, logsList.firstChild);
        }
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)


@app.get("/metrics")
def get_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/reset/{customer_id}")
def reset_customer(customer_id: str):
    runtime.middleware.service.store.reset_customer_window(customer_id)
    limit = quota
    customer_policies = runtime.middleware.service.customer_policies
    if customer_id in customer_policies:
        limit = customer_policies[customer_id].rpm
    return {"status": "ok", "message": f"Reset customer {customer_id}", "limit": limit}


@app.post("/request", response_model=RateLimitResponse)
def submit_request(payload: RateLimitRequest, x_customer_id: str | None = Header(None)):
    from app.logger import set_request_id
    set_request_id(payload.request_id)
    try:
        if not x_customer_id:
            RATE_LIMIT_REQUESTS.labels(
                customer_id="unknown",
                status="rejected",
                node_id=node_id,
                policy="none",
            ).inc()
            raise HTTPException(status_code=400, detail="Missing X-Customer-Id header")

        start_time = time.perf_counter()
        response = runtime.handle_request({"customer_id": x_customer_id, "request_id": payload.request_id})
        duration = time.perf_counter() - start_time

        EVALUATION_LATENCY.observe(duration)

        status = response["status"]
        policy = response.get("policy") or "default"
        RATE_LIMIT_REQUESTS.labels(
            customer_id=x_customer_id,
            status=status,
            node_id=node_id,
            policy=policy,
        ).inc()

        if response["status"] == "accepted":
            return response

        headers: dict[str, str] = {}
        if response.get("retry_after") is not None:
            headers["Retry-After"] = str(response["retry_after"])

        status_code = 429 if response["reason"] == "quota_exceeded" else 400
        return JSONResponse(status_code=status_code, content=response, headers=headers)
    finally:
        set_request_id(None)
