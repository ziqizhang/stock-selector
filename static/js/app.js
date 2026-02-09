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

function refreshSelected() {
    const checkboxes = document.querySelectorAll('.ticker-checkbox:checked');
    const symbols = Array.from(checkboxes).map(cb => cb.dataset.symbol);
    if (symbols.length === 0) return;

    const progressEl = document.getElementById('progress-selected');
    if (progressEl) progressEl.classList.remove('hidden');

    const ws = new WebSocket('ws://localhost:8000/ws/refresh-selected');
    ws.onopen = () => {
        ws.send(JSON.stringify(symbols));
    };
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const stepEl = document.getElementById('step-selected');
        if (data.type === 'ticker_start' && stepEl) {
            stepEl.textContent = `(${data.index}/${data.total}) Analyzing ${data.symbol}...`;
        } else if (data.type === 'all_done') {
            ws.close();
            window.location.reload();
        } else if (stepEl) {
            stepEl.textContent = `${data.symbol}: ${data.step}`;
        }
    };
    ws.onerror = () => {
        if (progressEl) progressEl.textContent = 'Error during refresh';
    };
}

function toggleSelectAll(masterCheckbox) {
    const checkboxes = document.querySelectorAll('.ticker-checkbox');
    checkboxes.forEach(cb => { cb.checked = masterCheckbox.checked; });
    updateRefreshSelectedBtn();
}

function updateRefreshSelectedBtn() {
    const btn = document.getElementById('btn-refresh-selected');
    if (!btn) return;
    const checked = document.querySelectorAll('.ticker-checkbox:checked').length;
    btn.disabled = checked === 0;

    const allBoxes = document.querySelectorAll('.ticker-checkbox');
    const selectAll = document.getElementById('select-all');
    if (selectAll) {
        selectAll.checked = allBoxes.length > 0 && checked === allBoxes.length;
    }
}

function scoreColor(score) {
    if (score >= 3) return '#10b981';
    if (score <= -3) return '#ef4444';
    return '#f59e0b';
}
