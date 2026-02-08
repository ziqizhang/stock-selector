function refreshTicker(symbol) {
    const progressEl = document.getElementById(`progress-${symbol}`) ||
                       document.getElementById('progress');
    if (progressEl) progressEl.classList.remove('hidden');

    const ws = new WebSocket(`ws://localhost:8000/ws/refresh/${symbol}`);
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const stepEl = document.getElementById(`step-${symbol}`) ||
                       document.getElementById('step');
        if (stepEl) stepEl.textContent = data.step;
        if (data.done) {
            ws.close();
            window.location.reload();
        }
    };
    ws.onerror = () => {
        if (progressEl) progressEl.textContent = 'Error during refresh';
    };
}

function refreshAll() {
    const progressEl = document.getElementById('progress-all');
    if (progressEl) progressEl.classList.remove('hidden');

    const ws = new WebSocket('ws://localhost:8000/ws/refresh-all');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const stepEl = document.getElementById('step-all');
        if (data.type === 'ticker_start' && stepEl) {
            stepEl.textContent = `(${data.index}/${data.total}) ${data.symbol}...`;
        } else if (data.type === 'all_done') {
            ws.close();
            window.location.reload();
        } else if (stepEl) {
            stepEl.textContent = `${data.symbol}: ${data.step}`;
        }
    };
}

function scoreColor(score) {
    if (score >= 3) return '#10b981';
    if (score <= -3) return '#ef4444';
    return '#f59e0b';
}
