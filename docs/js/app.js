/**
 * 好单线报 - 静态站点 JS
 * 功能：加载数据、渲染列表、筛选、搜索、分页
 */

const PER_PAGE = 20;
let allItems = [];
let filteredItems = [];

// ====== 初始化 ======
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    bindEvents();
});

async function loadData() {
    try {
        const resp = await fetch('/data/haodan.json');
        allItems = await resp.json();
        // 按时间倒序
        allItems.sort((a, b) => (b.scraped_at || '').localeCompare(a.scraped_at || ''));
        filteredItems = [...allItems];
        renderFilters();
        renderFromURL();
    } catch(e) {
        document.getElementById('item-grid').innerHTML =
            '<div class="empty-state"><div class="empty-icon">📦</div><p>数据加载失败</p></div>';
        console.error('加载数据失败:', e);
    }
}

function bindEvents() {
    // 搜索
    document.getElementById('search-form').addEventListener('submit', (e) => {
        e.preventDefault();
        applyFilters();
    });
    document.getElementById('search-input').addEventListener('input', debounce(() => {
        applyFilters();
    }, 300));
}

// ====== 筛选 ======
function renderFilters() {
    const platforms = [...new Set(allItems.map(i => i.platform).filter(Boolean))].sort();
    const params = new URLSearchParams(window.location.search);
    const currentPlatform = params.get('platform') || '';

    const group = document.getElementById('filter-group');
    // 保留 label
    let html = '<span class="filter-label">平台：</span>';
    html += `<a href="javascript:void(0)" class="filter-tag ${!currentPlatform ? 'active' : ''}" onclick="setFilter('')">全部</a>`;
    platforms.forEach(p => {
        html += `<a href="javascript:void(0)" class="filter-tag ${currentPlatform === p ? 'active' : ''}" onclick="setFilter('${p}')">${p}</a>`;
    });
    group.innerHTML = html;
}

function setFilter(platform) {
    const url = new URL(window.location);
    if (platform) url.searchParams.set('platform', platform);
    else url.searchParams.delete('platform');
    url.searchParams.set('page', '1');
    window.history.pushState({}, '', url);
    renderFromURL();
    renderFilters();
}

function applyFilters() {
    const keyword = document.getElementById('search-input').value.trim();
    const params = new URLSearchParams(window.location.search);
    const platform = params.get('platform') || '';

    filteredItems = allItems.filter(item => {
        if (platform && item.platform !== platform) return false;
        if (keyword && !item.title.toLowerCase().includes(keyword.toLowerCase())) return false;
        return true;
    });

    // 更新 URL
    const url = new URL(window.location);
    if (keyword) url.searchParams.set('q', keyword);
    else url.searchParams.delete('q');
    url.searchParams.set('page', '1');
    window.history.pushState({}, '', url);

    renderList(1);
}

function renderFromURL() {
    const params = new URLSearchParams(window.location.search);
    const platform = params.get('platform') || '';
    const keyword = params.get('q') || '';
    const page = parseInt(params.get('page') || '1');

    // 设置搜索框
    document.getElementById('search-input').value = keyword;

    // 过滤
    filteredItems = allItems.filter(item => {
        if (platform && item.platform !== platform) return false;
        if (keyword && !item.title.toLowerCase().includes(keyword.toLowerCase())) return false;
        return true;
    });

    renderList(page);
}

// ====== 渲染列表 ======
function renderList(page) {
    const total = filteredItems.length;
    const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));
    page = Math.max(1, Math.min(page, totalPages));
    const start = (page - 1) * PER_PAGE;
    const pageItems = filteredItems.slice(start, start + PER_PAGE);

    const params = new URLSearchParams(window.location.search);
    const keyword = params.get('q') || '';

    // 结果信息
    let infoHtml = `<span>共 <strong>${total}</strong> 条优惠</span>`;
    if (keyword) infoHtml += `<span class="search-keyword">搜索: "${keyword}"</span>`;
    document.getElementById('results-info').innerHTML = infoHtml;

    // 卡片网格
    if (pageItems.length === 0) {
        document.getElementById('item-grid').innerHTML =
            '<div class="empty-state"><div class="empty-icon">📦</div><p>暂无优惠数据</p></div>';
        document.getElementById('pagination').innerHTML = '';
        return;
    }

    const grid = document.getElementById('item-grid');
    grid.innerHTML = pageItems.map(item => {
        const platformClass = (item.platform || '其他').replace('/', '');
        const imgHtml = item.image
            ? `<img src="${item.image}" alt="${escHtml(item.title)}" loading="lazy" onerror="this.style.display='none';this.parentElement.classList.add('no-img')">`
            : `<div class="item-placeholder"><span>${(item.platform || '优')[:1]}</span></div>`;

        const priceHtml = item.price ? `<span class="item-price"><em>¥</em>${item.price}</span>` : '';
        const discountHtml = item.discount_info ? `<span class="item-discount">${escHtml(item.discount_info)}</span>` : '';
        const timeStr = item.pub_time || (item.scraped_at ? item.scraped_at.substring(0, 10) : '');

        return `<a href="/detail.html?id=${item.id}" class="item-card">
            <div class="item-img-wrap">${imgHtml}</div>
            <div class="item-body">
                <div class="item-platform ${platformClass}">${escHtml(item.platform || '其他')}</div>
                <h3 class="item-title">${escHtml(item.title)}</h3>
                <div class="item-meta">${priceHtml}${discountHtml}</div>
                <div class="item-footer">
                    <span class="item-time">${timeStr}</span>
                    <span class="item-go">去购买 ›</span>
                </div>
            </div>
        </a>`;
    }).join('');

    // 分页
    renderPagination(page, totalPages);
}

function renderPagination(currentPage, totalPages) {
    if (totalPages <= 1) {
        document.getElementById('pagination').innerHTML = '';
        return;
    }

    const params = new URLSearchParams(window.location.search);
    const platform = params.get('platform') || '';
    const q = params.get('q') || '';

    function pageUrl(page) {
        const p = new URLSearchParams();
        if (platform) p.set('platform', platform);
        if (q) p.set('q', q);
        p.set('page', page);
        return '/?' + p.toString();
    }

    let html = '';
    // 上一页
    if (currentPage > 1) {
        html += `<a href="${pageUrl(currentPage - 1)}" class="page-btn" onclick="goPage(${currentPage - 1});return false;">上一页</a>`;
    }

    // 页码
    for (let p = 1; p <= totalPages; p++) {
        if (p === currentPage) {
            html += `<span class="page-btn active">${p}</span>`;
        } else if (p <= 3 || p > totalPages - 3 || (p >= currentPage - 2 && p <= currentPage + 2)) {
            html += `<a href="${pageUrl(p)}" class="page-btn" onclick="goPage(${p});return false;">${p}</a>`;
        } else if (p === 4 || p === totalPages - 3) {
            html += '<span class="page-dots">...</span>';
        }
    }

    // 下一页
    if (currentPage < totalPages) {
        html += `<a href="${pageUrl(currentPage + 1)}" class="page-btn" onclick="goPage(${currentPage + 1});return false;">下一页</a>`;
    }

    document.getElementById('pagination').innerHTML = html;
}

function goPage(page) {
    const url = new URL(window.location);
    url.searchParams.set('page', page);
    window.history.pushState({}, '', url);
    renderList(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ====== 工具函数 ======
function escHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function debounce(fn, delay) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// 浏览器前进后退
window.addEventListener('popstate', () => {
    renderFromURL();
    renderFilters();
});
