(() => {
    // Telegram WebApp
    const tg = window.Telegram?.WebApp;
    if (tg) {
        tg.ready();
        tg.expand();
        // Apply Telegram theme colours if available
        const theme = tg.themeParams;
        if (theme?.bg_color) {
            document.documentElement.style.setProperty('--bg', theme.bg_color);
        }
        if (theme?.secondary_bg_color) {
            document.documentElement.style.setProperty('--bg-card', theme.secondary_bg_color);
        }
        if (theme?.text_color) {
            document.documentElement.style.setProperty('--text', theme.text_color);
        }
        if (theme?.hint_color) {
            document.documentElement.style.setProperty('--text-muted', theme.hint_color);
        }
        if (theme?.button_color) {
            document.documentElement.style.setProperty('--accent', theme.button_color);
        }
    }

    const API = '';  // same origin
    let currentPage = 1;
    let totalPages = 1;

    const citySelect = document.getElementById('citySelect');
    const minPriceEl = document.getElementById('minPrice');
    const maxPriceEl = document.getElementById('maxPrice');
    const applyBtn = document.getElementById('applyBtn');
    const listingsEl = document.getElementById('listings');
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    const loadMoreWrap = document.getElementById('loadMoreWrap');
    const totalBadge = document.getElementById('totalBadge');
    const searchInput = document.getElementById('searchInput');
    const ctx = document.getElementById('priceChart').getContext('2d');

    // ===== Chart =====
    let chartInstance = null;

    async function updateChart(city) {
        try {
            const url = city ? `${API}/api/histogram?city=${encodeURIComponent(city)}` : `${API}/api/histogram`;
            const data = await fetchJSON(url);

            if (chartInstance) {
                chartInstance.destroy();
            }

            if (!data.labels || data.labels.length === 0) {
                return;
            }

            chartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'Объявления',
                        data: data.data,
                        backgroundColor: 'rgba(233, 69, 96, 0.5)',
                        borderColor: 'rgba(233, 69, 96, 1)',
                        borderWidth: 1,
                        borderRadius: 4,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        title: {
                            display: true,
                            text: 'Распределение цен ($)',
                            color: '#a0a0b8',
                            font: { size: 12, family: 'Inter' }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#6b6b80', font: { size: 10 } }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#6b6b80', font: { size: 10 } }
                        }
                    },
                    animation: { duration: 800 }
                }
            });

        } catch (e) {
            console.error("Chart error", e);
        }
    }


    // ===== Fetch helpers =====
    async function fetchJSON(url) {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(resp.statusText);
        return resp.json();
    }

    // ===== Placeholder Logic =====
    function updateSearchPlaceholder() {
        if (!citySelect.value) {
            searchInput.placeholder = "сначала выберите город";
            searchInput.classList.add("no-city");
        } else {
            searchInput.placeholder = "Поиск по ключевым словам...";
            searchInput.classList.remove("no-city");
        }
    }

    // ===== Load cities =====
    async function loadCities() {
        try {
            const data = await fetchJSON(`${API}/api/cities`);
            data.cities.forEach(city => {
                const opt = document.createElement('option');
                opt.value = city;
                opt.textContent = city;
                citySelect.appendChild(opt);
            });
        } catch (e) {
            console.error('Failed to load cities', e);
        }
    }

    // ===== Render listings =====
    function renderCard(l, idx) {
        const dateStr = l.date ? new Date(l.date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
        const origPrice = l.price_original && l.currency && l.currency !== 'USD'
            ? `${l.price_original.toLocaleString()} ${l.currency}`
            : '';

        const card = document.createElement('article');
        card.className = 'card';
        card.style.animationDelay = `${idx * 0.06}s`;
        card.innerHTML = `
<div class="card-header">
<span class="card-city">${esc(l.city || '—')}</span>
<span class="card-date">${dateStr}</span>
</div>
<div class="card-price">$${l.price_usd != null ? l.price_usd.toLocaleString() : '—'}</div>
${origPrice ? `<div class="card-price-original">${esc(origPrice)}</div>` : ''}
<p class="card-text">${esc(l.text || '')}</p>
<a class="card-link" href="${esc(l.link)}" target="_blank" rel="noopener">Открыть в Telegram</a>
`;
        return card;
    }

    function esc(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function showSkeletons(n) {
        for (let i = 0; i < n; i++) {
            const sk = document.createElement('div');
            sk.className = 'skeleton skeleton-card';
            listingsEl.appendChild(sk);
        }
    }
    function removeSkeletons() {
        listingsEl.querySelectorAll('.skeleton').forEach(el => el.remove());
    }

    // ===== Load listings =====
    async function loadListings(page = 1, append = false) {
        if (!append) {
            listingsEl.innerHTML = '';
            showSkeletons(3);
        }

        const params = new URLSearchParams();
        const city = citySelect.value;
        if (city) params.set('city', city);
        const minP = minPriceEl.value;
        const maxP = maxPriceEl.value;
        if (minP) params.set('min_price', minP);
        if (maxP) params.set('max_price', maxP);

        const searchVal = searchInput.value.trim();

        if (searchVal && !city) {
            removeSkeletons();
            listingsEl.innerHTML = `
              <div class="empty-state">
                <div class="emoji">☝️</div>
                <p>Сначала выберите город<br>чтобы использовать поиск.</p>
              </div>`;
            return;
        }

        if (searchVal) params.set('search', searchVal);

        params.set('page', page);
        params.set('per_page', 20);

        try {
            const data = await fetchJSON(`${API}/api/listings?${params}`);
            removeSkeletons();

            if (data.listings.length === 0 && !append) {
                listingsEl.innerHTML = `
  <div class="empty-state">
    <div class="emoji">🔍</div>
    <p>Объявлений не найдено.<br>Попробуйте изменить параметры.</p>
  </div>`;
            } else {
                data.listings.forEach((l, i) => listingsEl.appendChild(renderCard(l, i)));
            }

            totalBadge.textContent = `${data.total} объявл.`;
            currentPage = data.page;
            totalPages = data.pages;
            loadMoreWrap.style.display = currentPage < totalPages ? '' : 'none';

            if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        } catch (e) {
            removeSkeletons();
            console.error('Failed to load listings', e);
            if (!append) {
                listingsEl.innerHTML = `
  <div class="empty-state">
    <div class="emoji">⚠️</div>
    <p>Не удалось загрузить данные.<br>Попробуйте позже.</p>
  </div>`;
            }
        }
    }

    // ===== Events =====
    applyBtn.addEventListener('click', () => {
        currentPage = 1;
        loadListings(1);
    });

    citySelect.addEventListener('change', () => {
        updateChart(citySelect.value);
        updateSearchPlaceholder();
    });

    loadMoreBtn.addEventListener('click', () => {
        loadListings(currentPage + 1, true);
    });

    let searchTimeout;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        if (!citySelect.value) {
            return;
        }

        searchTimeout = setTimeout(() => {
            currentPage = 1;
            loadListings(1);
        }, 500);
    });

    [minPriceEl, maxPriceEl].forEach(el => {
        el.addEventListener('keydown', e => { if (e.key === 'Enter') applyBtn.click(); });
    });

    // ===== Init =====
    updateSearchPlaceholder();
    loadCities();
    loadListings();
    updateChart();

    // ===== Admin & Suggestions Logic =====
    const suggestFab = document.getElementById('suggestFab');
    const suggestModal = document.getElementById('suggestModal');
    const adminFab = document.getElementById('adminFab');
    const adminPanel = document.getElementById('adminPanel');

    window.closeModal = (id) => {
        document.getElementById(id).classList.remove('active');
    };

    suggestFab.addEventListener('click', () => {
        document.getElementById('suggContentListing').value = '';
        document.getElementById('suggContentSource').value = '';
        document.getElementById('suggPrice').value = '';

        const modalCity = document.getElementById('suggCity');
        modalCity.innerHTML = citySelect.innerHTML;
        if (modalCity.options[0] && modalCity.options[0].value === '') {
            modalCity.remove(0);
        }

        suggestModal.classList.add('active');
        toggleSuggestFields();
    });

    window.toggleSuggestFields = () => {
        const type = document.getElementById('suggType').value;
        document.getElementById('listingFields').style.display = type === 'listing' ? 'block' : 'none';
        document.getElementById('sourceFields').style.display = type === 'source' ? 'block' : 'none';
    };

    document.getElementById('sendSuggBtn').addEventListener('click', async () => {
        const type = document.getElementById('suggType').value;
        let content = '';
        let city = null;
        let price = null;

        if (type === 'listing') {
            content = document.getElementById('suggContentListing').value.trim();
            city = document.getElementById('suggCity').value;
            price = parseFloat(document.getElementById('suggPrice').value);
            if (!price) return alert('Укажите цену');
        } else {
            content = document.getElementById('suggContentSource').value.trim();
        }

        if (!content) return alert('Заполните описание');
        if (type === 'source' && !content.includes(' - ')) {
            return alert('Используйте формат: @канал - Город');
        }

        try {
            const res = await fetch(`${API}/api/suggest`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': tg.initData || ''
                },
                body: JSON.stringify({ type, content, city, price })
            });

            const data = await res.json();
            if (res.ok) {
                alert(data.message || 'Готово!');
                closeModal('suggestModal');
            } else {
                alert(data.detail || 'Ошибка отправки');
            }
        } catch (e) {
            alert('Ошибка сети');
        }
    });

    async function checkAdmin() {
        if (!tg.initData) return;
        try {
            const res = await fetch(`${API}/api/admin/stats`, {
                headers: { 'Authorization': tg.initData }
            });
            if (res.ok) {
                adminFab.style.display = 'flex';
            }
        } catch (e) {
            console.log('Not admin or network error');
        }
    }

    // Make globally accessible
    window.loadAdminDashboard = loadAdminDashboard;
    window.closeAdmin = () => {
        adminPanel.classList.remove('active');
    };

    adminFab.addEventListener('click', () => {
        adminPanel.classList.add('active');
        loadAdminDashboard();
    });

    // Run Parser Button
    const runParserBtn = document.getElementById('runParserBtn');
    if (runParserBtn) {
        runParserBtn.addEventListener('click', async () => {
            if (!confirm('Запустить обновление базы? Это может занять несколько минут.')) return;

            const originalText = runParserBtn.textContent;
            runParserBtn.disabled = true;
            runParserBtn.textContent = '🔄 Обновление...';

            try {
                const res = await fetch(`${API}/api/admin/run_parser`, {
                    method: 'POST',
                    headers: { 'Authorization': tg.initData || '' }
                });
                const data = await res.json();
                if (res.ok) {
                    alert(data.message || 'Готово!');
                    loadAdminDashboard(); // Refresh stats
                } else {
                    alert('Ошибка: ' + (data.detail || 'неизвестно'));
                }
            } catch (e) {
                alert('Ошибка сети: ' + e.message);
            } finally {
                runParserBtn.disabled = false;
                runParserBtn.textContent = originalText;
            }
        });
    }

    window.switchTab = (tabId) => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

        const btn = document.querySelector(`.tab-btn[onclick*="${tabId}"]`);
        if (btn) btn.classList.add('active');
        const panel = document.getElementById(`tab-${tabId}`);
        if (panel) panel.classList.add('active');

        loadAdminDashboard();
    };

    async function loadAdminDashboard() {
        if (!tg.initData) return;
        const headers = { 'Authorization': tg.initData };

        // 1. Stats
        fetch(`${API}/api/admin/stats`, { headers })
            .then(r => r.json())
            .then(data => {
                const grid = document.getElementById('adminStats');
                grid.innerHTML = `
                    <div class="stat-card">
                        <div class="stat-val">${data.total_users}</div>
                        <div class="stat-label">Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-val">${data.active_users_24h}</div>
                        <div class="stat-label">Active (24h)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-val">${data.total_channels}</div>
                        <div class="stat-label">Channels</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-val" style="color:${data.error_channels > 0 ? '#e74c3c' : 'var(--accent)'}">${data.error_channels}</div>
                        <div class="stat-label">Errors</div>
                    </div>
                `;
            });

        // 2. Suggestions (Separated)
        fetch(`${API}/api/admin/suggestions`, { headers })
            .then(r => r.json())
            .then(list => {
                const listEl = document.getElementById('adminListingSuggestions');
                const sourceEl = document.getElementById('adminSourceSuggestions');

                const listings = list.filter(s => s.type === 'listing');
                const sources = list.filter(s => s.type === 'source');

                const renderSugg = (s) => `
                    <div class="list-item">
                        <div class="list-info">
                            <strong>${esc(s.type)}</strong>: ${esc(s.content)}
                            <small>${new Date(s.created_at).toLocaleString()}</small>
                        </div>
                        <div>
                            <button class="action-btn btn-appr" onclick="modSugg(${s.id}, 'approve')">✓</button>
                            <button class="action-btn btn-rej" onclick="modSugg(${s.id}, 'reject')">✗</button>
                        </div>
                    </div>
                `;

                if (listEl) {
                    listEl.innerHTML = listings.length ? listings.map(renderSugg).join('') : '<p class="empty-text">Нет новых объявлений</p>';
                }
                if (sourceEl) {
                    sourceEl.innerHTML = sources.length ? sources.map(renderSugg).join('') : '<p class="empty-text">Нет предложений источников</p>';
                }
            });

        // 3. Channels
        fetch(`${API}/api/admin/channels`, { headers })
            .then(r => r.json())
            .then(list => {
                const el = document.getElementById('adminChannels');
                el.innerHTML = list.map(c => `
                    <div class="list-item">
                        <div class="list-info">
                            <strong>@${esc(c.username)}</strong> (${esc(c.city)})
                            <small>Status: ${c.status} | Errors: ${c.error_count}</small>
                        </div>
                        <div style="display:flex; align-items:center; gap:10px;">
                            ${c.status === 'active' ? '🟢' : '🔴'}
                            <button class="action-btn btn-rej" style="padding:4px 8px;" onclick="deleteChannel(${c.id}, '@${c.username}')">🗑️</button>
                        </div>
                    </div>
                `).join('');
            });
    }

    window.deleteChannel = async (id, name) => {
        if (!confirm(`Удалить канал ${name}?`)) return;
        try {
            const res = await fetch(`${API}/api/admin/channels/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': tg.initData || '' }
            });
            if (res.ok) {
                loadAdminDashboard();
            } else {
                alert('Ошибка при удалении');
            }
        } catch (e) { alert('Ошибка сети'); }
    };

    window.modSugg = async (id, action) => {
        if (!confirm(`Confirm ${action}?`)) return;
        try {
            const res = await fetch(`${API}/api/admin/suggestions/${id}/${action}`, {
                method: 'POST',
                headers: { 'Authorization': tg.initData || '' }
            });
            if (res.ok) {
                loadAdminDashboard(); // Refresh
            } else {
                alert('Error');
            }
        } catch (e) { alert('Network error'); }
    };

    // Auto-refresh logic
    let dashboardInterval = null;
    const intervalSelect = document.getElementById('autoUpdateInterval');

    if (intervalSelect) {
        // Load saved
        const saved = localStorage.getItem('admin_refresh_interval') || '0';
        intervalSelect.value = saved;

        intervalSelect.addEventListener('change', () => {
            const val = intervalSelect.value;
            localStorage.setItem('admin_refresh_interval', val);
            startDashboardTimer(val);
        });

        // Initial if panel is open... wait, usually better when active
        if (saved !== '0') startDashboardTimer(saved);
    }

    function startDashboardTimer(mins) {
        if (dashboardInterval) clearInterval(dashboardInterval);
        const ms = parseInt(mins) * 60 * 1000;
        if (ms > 0) {
            dashboardInterval = setInterval(() => {
                const panel = document.getElementById('adminPanel');
                if (panel && panel.classList.contains('active')) {
                    console.log('Auto-refreshing admin dashboard...');
                    loadAdminDashboard();
                }
            }, ms);
        }
    }

    checkAdmin();
})();
