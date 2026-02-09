/**
 * SubKiller Mini App — клиентская логика
 */

// ============== Инициализация ==============

const tg = window.Telegram?.WebApp;
let userId = null;
let userData = null;
let subsData = [];
let analyticsData = null;
let currentSubId = null;
let painInterval = null;

document.addEventListener('DOMContentLoaded', async () => {
    if (tg) {
        tg.ready();
        tg.expand();
        tg.setHeaderColor('#12121e');
        tg.setBackgroundColor('#12121e');

        if (tg.initDataUnsafe?.user) {
            userId = tg.initDataUnsafe.user.id;
        }
    }

    // Фоллбэк: параметр URL
    if (!userId) {
        const params = new URLSearchParams(
            window.location.search
        );
        userId = params.get('user_id');
    }

    if (!userId) {
        showToast('Откройте через Telegram бота');
        hideLoading();
        return;
    }

    await loadAll();
    setupTabs();
    setupForm();
    hideLoading();
});


// ============== Загрузка данных ==============

async function loadAll() {
    try {
        const [userRes, subsRes, analytRes] =
            await Promise.all([
                fetch(`/api/user/${userId}`),
                fetch(`/api/subscriptions/${userId}`),
                fetch(`/api/analytics/${userId}`),
            ]);

        if (userRes.ok) {
            userData = await userRes.json();
            renderUserInfo();
        }
        if (subsRes.ok) {
            const data = await subsRes.json();
            subsData = data.subscriptions || [];
            renderSubscriptions();
        }
        if (analytRes.ok) {
            analyticsData = await analytRes.json();
            renderAnalytics();
            startPainCounter();
        }

        // Загружаем популярные подписки
        const popRes = await fetch(
            '/api/popular-subscriptions'
        );
        if (popRes.ok) {
            const popData = await popRes.json();
            renderPopularSubs(popData);
            fillCategorySelect(popData.categories);
        }

        // Загружаем ачивки
        const achRes = await fetch(
            `/api/achievements/${userId}`
        );
        if (achRes.ok) {
            const achData = await achRes.json();
            renderAchievements(achData);
        }
    } catch (e) {
        console.error('Load error:', e);
        showToast('Ошибка загрузки данных');
    }
}


// ============== Рендеринг ==============

function renderUserInfo() {
    if (!userData) return;
    const badge = document.getElementById('premium-badge');
    if (userData.is_premium) {
        badge.classList.remove('hidden');
    }
}

function renderSubscriptions() {
    const container = document.getElementById('subs-list');

    if (!subsData.length) {
        container.innerHTML =
            '<p class="empty-state">' +
            'Нет подписок. Добавь первую!</p>';
        return;
    }

    // Сортировка: active → trial → cancelled
    const sorted = [...subsData].sort((a, b) => {
        const order = {
            active: 0, trial: 1,
            paused: 2, cancelled: 3
        };
        return (order[a.status] || 9) -
               (order[b.status] || 9);
    });

    let html = '';
    for (const sub of sorted) {
        const statusClass = getSubClass(sub);
        const icon = getCategoryIcon(sub.category);
        const price = formatMoney(sub.monthly_price);
        let meta = sub.category_name;

        if (sub.is_trial && sub.trial_end_date) {
            const d = daysUntil(sub.trial_end_date);
            meta += ` • 🆓 Trial: ${d} дн.`;
        } else if (sub.days_until_billing !== null &&
                   sub.days_until_billing >= 0) {
            meta += ` • ⏰ через ${sub.days_until_billing} дн.`;
        }

        if (sub.status === 'cancelled') {
            meta += ' • ❌ Отменена';
        }

        const usageEmoji = {
            high: '🟢', medium: '🟡',
            low: '🔴', none: '⚫', unknown: '⚪'
        };
        const ue = usageEmoji[sub.usage_level] || '⚪';

        html += `
            <div class="sub-card ${statusClass}"
                 onclick="openSubModal(${sub.id})">
                <div class="sub-left">
                    <div class="sub-icon">${icon}</div>
                    <div class="sub-info">
                        <div class="sub-name">
                            ${ue} ${sub.name}
                        </div>
                        <div class="sub-meta">${meta}</div>
                    </div>
                </div>
                <div>
                    <div class="sub-price">${price}</div>
                    <div class="sub-period">/мес</div>
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
}

function renderAnalytics() {
    if (!analyticsData) return;

    // Health
    const healthCard = document.getElementById('health-card');
    healthCard.classList.remove('hidden');

    const scoreEl = document.getElementById('health-score');
    scoreEl.textContent = analyticsData.health_score;
    scoreEl.style.color = getScoreColor(
        analyticsData.health_score
    );

    const barFill = document.getElementById('health-bar-fill');
    barFill.style.width = analyticsData.health_score + '%';
    barFill.style.background = getScoreColor(
        analyticsData.health_score
    );

    document.getElementById('total-monthly').textContent =
        formatMoney(analyticsData.total_monthly);
    document.getElementById('wasted-monthly').textContent =
        formatMoney(analyticsData.wasted_monthly);
    document.getElementById('saved-monthly').textContent =
        formatMoney(analyticsData.saved_monthly);

    // Investments
    document.getElementById('invest-5y').textContent =
        formatMoney(analyticsData.investments.sp500_5y);
    document.getElementById('invest-10y').textContent =
        formatMoney(analyticsData.investments.sp500_10y);

    // Categories
    const catList = document.getElementById('categories-list');
    let catHtml = '';
    const cats = analyticsData.categories || {};
    const sortedCats = Object.entries(cats)
        .sort((a, b) => b[1] - a[1]);

    for (const [name, amount] of sortedCats) {
        catHtml += `
            <div class="category-item">
                <span>${name}</span>
                <span>${formatMoney(amount)}/мес</span>
            </div>
        `;
    }
    catList.innerHTML = catHtml || '<p class="empty-state">' +
        'Нет данных</p>';

    // Pain banner
    if (analyticsData.wasted_monthly > 0) {
        document.getElementById('pain-banner')
            .classList.remove('hidden');
    }
}

function renderPopularSubs(data) {
    const grid = document.getElementById('popular-subs');
    const subs = (data.subscriptions || []).slice(0, 12);
    let html = '';

    for (const sub of subs) {
        html += `
            <div class="popular-item"
                 onclick="quickAdd('${sub.name}',
                    ${sub.price}, '${sub.category}')">
                <div class="popular-name">${sub.name}</div>
                <div class="popular-price">
                    ${sub.price}₽/мес
                </div>
            </div>
        `;
    }

    grid.innerHTML = html;
}

function fillCategorySelect(categories) {
    const sel = document.getElementById('sub-category');
    let html = '';
    for (const [key, name] of Object.entries(
        categories || {}
    )) {
        html += `<option value="${key}">${name}</option>`;
    }
    sel.innerHTML = html;
}

function renderAchievements(data) {
    const earnedEl = document.getElementById(
        'earned-achievements'
    );
    const lockedEl = document.getElementById(
        'locked-achievements'
    );
    const lockedTitle = document.getElementById(
        'locked-title'
    );

    let earnedHtml = '';
    for (const a of data.earned || []) {
        earnedHtml += `
            <div class="achievement-card">
                <span class="ach-emoji">${a.emoji}</span>
                <div class="ach-info">
                    <div class="ach-name">${a.name}</div>
                    <div class="ach-desc">
                        ${a.description}
                    </div>
                </div>
            </div>
        `;
    }
    earnedEl.innerHTML = earnedHtml ||
        '<p class="empty-state">' +
        'Пока нет ачивок. Начни экономить!</p>';

    if (data.locked?.length) {
        lockedTitle.style.display = 'block';
        let lockedHtml = '';
        for (const a of data.locked.slice(0, 6)) {
            lockedHtml += `
                <div class="achievement-card locked">
                    <span class="ach-emoji">🔒</span>
                    <div class="ach-info">
                        <div class="ach-name">${a.name}</div>
                        <div class="ach-desc">
                            ${a.description}
                        </div>
                    </div>
                </div>
            `;
        }
        lockedEl.innerHTML = lockedHtml;
    }
}


// ============== Pain Counter ==============

function startPainCounter() {
    if (!analyticsData?.pain_counter) return;
    const pc = analyticsData.pain_counter;
    if (pc.per_minute <= 0) return;

    const amountEl = document.getElementById('pain-amount');
    const todayEl = document.getElementById('pain-today');

    let accumulated = pc.today;
    const perSecond = pc.per_minute / 60;

    if (painInterval) clearInterval(painInterval);
    painInterval = setInterval(() => {
        accumulated += perSecond;
        amountEl.textContent = accumulated.toFixed(2) + '₽';
        todayEl.textContent = 'Сегодня: ' +
            formatMoney(accumulated);
    }, 1000);
}


// ============== Modal ==============

function openSubModal(subId) {
    const sub = subsData.find(s => s.id === subId);
    if (!sub) return;

    currentSubId = subId;

    document.getElementById('modal-title').textContent =
        sub.name;

    let bodyHtml = `
        <p>💰 Цена: <b>${formatMoney(sub.price)}</b>
            (${sub.billing_cycle_name})</p>
        <p>📅 В месяц: <b>
            ${formatMoney(sub.monthly_price)}</b></p>
        <p>📁 Категория: ${sub.category_name}</p>
        <p>📊 Статус: ${sub.status}</p>
    `;

    if (sub.next_billing_date) {
        const d = daysUntil(sub.next_billing_date);
        bodyHtml += `<p>⏰ Списание: ${sub.next_billing_date}
            (через ${d} дн.)</p>`;
    }

    if (sub.is_trial && sub.trial_end_date) {
        const td = daysUntil(sub.trial_end_date);
        bodyHtml += `<p>🆓 Trial: ${td} дн. осталось</p>`;
    }

    if (sub.notes) {
        bodyHtml += `<p>📝 ${sub.notes}</p>`;
    }

    document.getElementById('modal-body').innerHTML =
        bodyHtml;

    // Устанавливаем текущий usage
    const usageSel = document.getElementById('modal-usage');
    usageSel.value = sub.usage_level || 'unknown';

    // Кнопки
    const cancelBtn = document.getElementById(
        'btn-cancel-sub'
    );
    if (sub.status === 'cancelled') {
        cancelBtn.style.display = 'none';
    } else {
        cancelBtn.style.display = 'block';
    }

    // Скрываем альтернативы
    document.getElementById('alternatives-section')
        .classList.add('hidden');

    // Показываем модал
    document.getElementById('sub-modal')
        .classList.remove('hidden');

    // Обработчики
    document.getElementById('btn-save-usage').onclick =
        () => saveUsage(subId);
    document.getElementById('btn-cancel-sub').onclick =
        () => cancelSub(subId);
    document.getElementById('btn-find-alt').onclick =
        () => findAlternatives(sub.name);
}

function closeModal() {
    document.getElementById('sub-modal')
        .classList.add('hidden');
    currentSubId = null;
}

// Клик на backdrop
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-backdrop')) {
        closeModal();
    }
});


// ============== Действия ==============

async function saveUsage(subId) {
    const usage = document.getElementById(
        'modal-usage'
    ).value;

    try {
        const res = await fetch(
            `/api/subscriptions/${userId}/${subId}`,
            {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    usage_level: usage
                }),
            }
        );

        if (res.ok) {
            showToast('✅ Сохранено!');
            closeModal();
            await loadAll();
        } else {
            showToast('❌ Ошибка');
        }
    } catch (e) {
        showToast('❌ Ошибка сети');
    }
}

async function cancelSub(subId) {
    const sub = subsData.find(s => s.id === subId);
    if (!confirm(
        `Отменить ${sub?.name}? ` +
        `Экономия: ${formatMoney(sub?.monthly_price)}/мес`
    )) return;

    try {
        const res = await fetch(
            `/api/subscriptions/${userId}/${subId}`,
            { method: 'DELETE' }
        );

        if (res.ok) {
            const data = await res.json();
            showToast(
                `✅ Отменена! Экономия: ` +
                `${formatMoney(data.saved_monthly)}/мес`
            );
            closeModal();
            await loadAll();
        } else {
            showToast('❌ Ошибка');
        }
    } catch (e) {
        showToast('❌ Ошибка сети');
    }
}

async function findAlternatives(subName) {
    const section = document.getElementById(
        'alternatives-section'
    );
    const list = document.getElementById(
        'alternatives-list'
    );

    list.innerHTML = '<p>🔍 Ищу...</p>';
    section.classList.remove('hidden');

    try {
        const res = await fetch(
            `/api/alternatives/${encodeURIComponent(subName)}`
        );
        if (res.ok) {
            const data = await res.json();
            const alts = data.alternatives || [];

            if (!alts.length) {
                list.innerHTML =
                    '<p>Альтернативы не найдены</p>';
                return;
            }

            let html = '';
            for (const alt of alts) {
                const priceText = alt.price === 0
                    ? '🆓 Бесплатно'
                    : `${alt.price}₽/мес`;
                html += `
                    <div class="alt-item">
                        <div class="alt-name">
                            ${alt.name}
                        </div>
                        <div class="alt-price">
                            ${priceText}
                        </div>
                        <div class="alt-coverage">
                            Покрытие: ${alt.coverage}%
                        </div>
                    </div>
                `;
            }
            list.innerHTML = html;
        }
    } catch (e) {
        list.innerHTML = '<p>Ошибка загрузки</p>';
    }
}


// ============== Добавление ==============

function quickAdd(name, price, category) {
    document.getElementById('sub-name').value = name;
    document.getElementById('sub-price').value = price;
    document.getElementById('sub-category').value = category;
    document.getElementById('sub-cycle').value = 'monthly';

    // Переключаемся на вкладку добавления
    // и скроллим к форме
    switchTab('add');
    document.getElementById('add-form')
        .scrollIntoView({ behavior: 'smooth' });
}

function setupForm() {
    const form = document.getElementById('add-form');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const name = document.getElementById(
            'sub-name'
        ).value.trim();
        const price = parseFloat(
            document.getElementById('sub-price').value
        );
        const cycle = document.getElementById(
            'sub-cycle'
        ).value;
        const category = document.getElementById(
            'sub-category'
        ).value;
        const dateVal = document.getElementById(
            'sub-date'
        ).value;
        const isTrial = document.getElementById(
            'sub-trial'
        ).checked;

        if (!name || !price) {
            showToast('Заполни название и цену');
            return;
        }

        try {
            const body = {
                name,
                price,
                category,
                billing_cycle: cycle,
                is_trial: isTrial,
            };

            if (dateVal) {
                body.next_billing_date = dateVal;
                if (isTrial) {
                    body.trial_end_date = dateVal;
                }
            }

            const res = await fetch(
                `/api/subscriptions/${userId}`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(body),
                }
            );

            if (res.ok) {
                showToast('✅ Подписка добавлена!');
                form.reset();
                switchTab('subscriptions');
                await loadAll();
            } else {
                showToast('❌ Ошибка');
            }
        } catch (e) {
            showToast('❌ Ошибка сети');
        }
    });
}


// ============== Tabs ==============

function setupTabs() {
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            switchTab(tab.dataset.tab);
        });
    });
}

function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => {
        t.classList.toggle(
            'active', t.dataset.tab === tabName
        );
    });
    document.querySelectorAll('.tab-content').forEach(c => {
        c.classList.toggle(
            'active',
            c.id === 'tab-' + tabName
        );
    });
}


// ============== Helpers ==============

function formatMoney(amount) {
    if (amount === null || amount === undefined) return '0₽';
    const num = Math.round(amount);
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + ' млн ₽';
    }
    return num.toLocaleString('ru-RU') + '₽';
}

function daysUntil(dateStr) {
    const target = new Date(dateStr);
    const now = new Date();
    const diff = target - now;
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function getSubClass(sub) {
    if (sub.status === 'cancelled') return 'cancelled';
    if (sub.is_trial) return 'trial';
    if (sub.usage_level === 'none' ||
        sub.usage_level === 'low') return 'unused';
    if (sub.usage_level === 'high' ||
        sub.usage_level === 'medium') return 'active-used';
    return '';
}

function getCategoryIcon(cat) {
    const icons = {
        streaming: '🎬', music: '🎵',
        cloud: '☁️', productivity: '📝',
        education: '📚', fitness: '💪',
        gaming: '🎮', news: '📰',
        social: '📱', vpn: '🔐',
        ai: '🤖', design: '🎨',
        development: '💻', finance: '💰',
        food: '🍕', transport: '🚗',
        dating: '❤️', other: '📦',
    };
    return icons[cat] || '📦';
}

function getScoreColor(score) {
    if (score >= 80) return '#4cd964';
    if (score >= 60) return '#ffcc00';
    if (score >= 40) return '#ff9500';
    return '#ff3b30';
}

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.remove('hidden');
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

function hideLoading() {
    document.getElementById('loading')
        .classList.add('hidden');
    document.getElementById('tabs').style.display = 'flex';
}