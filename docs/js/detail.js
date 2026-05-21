/**
 * 好单线报 - 详情页 JS
 */

let allItems = [];

document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');

    if (!id) {
        showNotFound();
        return;
    }

    try {
        const resp = await fetch('/data/haodan.json');
        allItems = await resp.json();
        const item = allItems.find(i => i.id === id);

        if (!item) {
            showNotFound();
            return;
        }

        renderDetail(item);
        renderRelated(item);
        document.title = item.title + ' - 好单线报';
    } catch(e) {
        document.getElementById('detail-info').innerHTML = '<div style="text-align:center;color:#888;">数据加载失败</div>';
        console.error(e);
    }
});

function showNotFound() {
    document.getElementById('detail-info').innerHTML = `
        <div style="text-align:center;padding:40px;">
            <div style="font-size:48px;margin-bottom:16px;">🔍</div>
            <p style="color:#888;">商品不存在</p>
            <a href="/" style="color:#ff4142;">返回首页</a>
        </div>`;
}

function renderDetail(item) {
    // 图片
    const imgWrap = document.getElementById('detail-img');
    if (item.image) {
        imgWrap.innerHTML = `<img src="${item.image}" alt="${escHtml(item.title)}" onerror="this.style.display='none';imgWrap.classList.add('no-img')">`;
    } else {
        imgWrap.innerHTML = `<div class="detail-placeholder"><span>${(item.platform || '优')[:1]}</span></div>`;
    }

    // 信息
    const platformClass = (item.platform || '其他').replace('/', '');
    const buyLink = item.buy_link || item.original_buy_link || '';

    let html = `
        <div class="detail-platform ${platformClass}">${escHtml(item.platform || '其他')}</div>
        <h1 class="detail-title">${escHtml(item.title)}</h1>
    `;

    if (item.price) {
        html += `
        <div class="detail-price">
            <span class="price-label">到手价</span>
            <span class="price-value"><em>¥</em>${item.price}</span>
        </div>`;
    }

    if (item.discount_info) {
        html += `
        <div class="detail-discount">
            <span class="discount-badge">优惠</span>
            ${escHtml(item.discount_info)}
        </div>`;
    }

    html += '<div class="detail-meta-grid">';
    if (item.category) {
        html += `<div class="meta-item"><span class="meta-label">分类</span><span class="meta-value">${escHtml(item.category)}</span></div>`;
    }
    if (item.author) {
        html += `<div class="meta-item"><span class="meta-label">来源</span><span class="meta-value">${escHtml(item.author)}</span></div>`;
    }
    if (item.pub_time) {
        html += `<div class="meta-item"><span class="meta-label">发布时间</span><span class="meta-value">${escHtml(item.pub_time)}</span></div>`;
    }
    html += '</div>';

    // 淘口令区域
    if (item.taopassword) {
        html += `
        <div id="tpwd-section" style="margin:16px 0;">
            <div style="font-size:13px;color:#666;margin-bottom:6px;">📋 淘口令（复制后打开淘宝APP）</div>
            <div style="display:flex;gap:8px;align-items:center;">
                <input id="tpwd-input" type="text" readonly value="${escHtml(item.taopassword)}"
                    style="flex:1;padding:8px 12px;border:1px dashed #ff4400;border-radius:6px;font-size:13px;background:#fff8f5;color:#ff4400;">
                <button onclick="copyTpwd()" id="copy-tpwd-btn"
                    style="padding:8px 16px;background:#ff4400;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;">
                    复制口令
                </button>
            </div>
            <div id="tpwd-status" style="font-size:12px;color:#52c41a;margin-top:4px;display:none;">✅ 已复制，打开淘宝APP即可自动识别</div>
        </div>`;
    }

    // 购买按钮
    if (buyLink) {
        const goUrl = '/go.html?id=' + item.id;
        html += `<a href="${goUrl}" target="_blank" rel="noopener noreferrer" class="buy-btn">去${escHtml(item.platform || '购买')} ›</a>`;
    }

    document.getElementById('detail-info').innerHTML = html;

    // 描述
    if (item.description) {
        document.getElementById('detail-desc').style.display = 'block';
        document.getElementById('desc-content').textContent = item.description;
    }
}

function renderRelated(item) {
    const related = allItems.filter(i =>
        i.id !== item.id && (i.platform === item.platform || i.category === item.category)
    ).slice(0, 6);

    if (related.length === 0) return;

    document.getElementById('related-section').style.display = 'block';
    const grid = document.getElementById('related-grid');
    grid.innerHTML = related.map(r => {
        const platformClass = (r.platform || '其他').replace('/', '');
        const imgHtml = r.image
            ? `<img src="${r.image}" alt="${escHtml(r.title)}" loading="lazy" onerror="this.style.display='none'">`
            : `<div class="item-placeholder small"><span>${(r.platform || '优')[:1]}</span></div>`;
        const priceHtml = r.price ? `<span class="related-price"><em>¥</em>${r.price}</span>` : '';

        return `<a href="/detail.html?id=${r.id}" class="related-card">
            <div class="related-img">${imgHtml}</div>
            <div class="related-info">
                <h3 class="related-title">${escHtml(r.title)}</h3>
                ${priceHtml}
            </div>
        </a>`;
    }).join('');
}

function copyTpwd() {
    const input = document.getElementById('tpwd-input');
    const status = document.getElementById('tpwd-status');
    const btn = document.getElementById('copy-tpwd-btn');
    if (!input || !input.value) return;

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(input.value).then(() => {
            status.style.display = 'block';
            btn.textContent = '已复制 ✓';
            setTimeout(() => { btn.textContent = '复制口令'; status.style.display = 'none'; }, 3000);
        });
    } else {
        input.select();
        document.execCommand('copy');
        status.style.display = 'block';
        btn.textContent = '已复制 ✓';
        setTimeout(() => { btn.textContent = '复制口令'; status.style.display = 'none'; }, 3000);
    }
}

function escHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}
