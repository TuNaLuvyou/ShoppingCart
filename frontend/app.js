const nodes = [{id:'A', p:5001}, {id:'B', p:5002}, {id:'C', p:5003}];
const cache = {};

// Hàm gọi API dùng chung
const call = async (port, path, method = 'GET', body = null) => {
    try {
        const res = await fetch(`http://localhost:${port}${path}`, {
            method, headers: {'Content-Type': 'application/json'},
            body: body ? JSON.stringify(body) : null,
            signal: AbortSignal.timeout(1000)
        });
        return res.ok ? await res.json() : null;
    } catch { return null; }
};

const updateUI = async () => {
    const sid = document.getElementById('session-id').value || 'user_dat_123';
    
    for (const n of nodes) {
        const data = await call(n.p, `/cart/${sid}`);
        const card = document.getElementById(`card-node-${n.id}`);
        
        // Chỉ vẽ lại nếu dữ liệu thay đổi
        if (JSON.stringify(data) === cache[n.id]) continue;
        cache[n.id] = JSON.stringify(data);

        // Cập nhật trạng thái Online/Offline
        const isOnline = !!data;
        card.classList.toggle('offline', !isOnline);
        const indicator = card.querySelector('.status-indicator');
        const itemsContainer = card.querySelector('.cart-items');
        
        if (!isOnline) {
            indicator.innerHTML = '<div class="dot offline"></div><span class="status-text">Offline</span>';
            itemsContainer.innerHTML = '<div style="color:var(--danger); text-align:center; padding:2rem; font-size:0.85rem"><i class="fa-solid fa-plug-circle-xmark"></i> Node đang mất kết nối...</div>';
            card.querySelectorAll('input, button').forEach(el => el.disabled = true);
            continue;
        }

        card.querySelectorAll('input, button').forEach(el => el.disabled = false);
        const items = data.raw_data.items || {};
        const activeCount = Object.values(items).filter(i => i.status === 'active').length;
        
        indicator.innerHTML = `
            <span class="badge badge-port" style="margin-right:10px">${activeCount} items</span>
            <div class="dot online"></div><span class="status-text">Online</span>
        `;

        // Render danh sách sản phẩm bằng Template Strings
        itemsContainer.innerHTML = Object.entries(items).map(([name, info]) => `
            <div class="cart-item ${info.status === 'deleted' ? 'is-deleted' : ''}">
                <div class="item-main">
                    <span class="item-name">${name}</span>
                    <span class="badge status-badge ${info.status}">${info.status}</span>
                    ${info.status === 'active' ? `<button onclick="doAction('${n.id}', ${n.p}, 'remove', '${name}')" class="btn-remove"><i class="fa-solid fa-trash"></i></button>` : ''}
                </div>
                <div class="item-meta"><i class="fa-regular fa-clock"></i> ${JSON.stringify(info.vclock).replace(/"/g,'')}</div>
            </div>
        `).join('') || '<div style="color:var(--text-secondary); text-align:center; padding:1rem; font-size:0.85rem">Giỏ hàng trống</div>';

        
        if (!card.querySelector('.btn-clear-history')) {
            const footer = document.createElement('div');
            footer.className = 'raw-data-toggle';
            footer.innerHTML = `<button onclick="clearHistory('${n.id}', ${n.p})" class="btn btn-raw" style="color:var(--warning); border-color:var(--warning); margin-right:10px"><i class="fa-solid fa-broom"></i> Clean Tombstones</button>`;
            card.querySelector('.node-body').appendChild(footer);
        }

        card.querySelector('.raw-data-view').innerText = JSON.stringify(data.raw_data, null, 2);
    }
};

window.clearHistory = async (id, port) => {
    if (!confirm(`Dọn dẹp tất cả sản phẩm đã xóa (Tombstones) tại Node ${id}? Các sản phẩm đang Active sẽ được giữ lại.`)) return;
    cache[id] = null;
    await call(port, '/clear', 'POST');
    updateUI();
};

// Hàm xử lý Add/Remove
window.doAction = async (id, port, act, item) => {
    const sid = document.getElementById('session-id').value || 'user_dat_123';
    cache[id] = null; 
    await call(port, `/cart/${sid}/${act}`, 'POST', {item});
    updateUI();
};

// Gán sự kiện cho các nút
nodes.forEach(n => {
    const card = document.getElementById(`card-node-${n.id}`);
    card.querySelector('.btn-add').onclick = () => {
        const input = card.querySelector('.input-item');
        if(input.value) { doAction(n.id, n.p, 'add', input.value); input.value = ''; }
    };
    card.querySelector('.btn-raw').onclick = () => card.querySelector('.raw-data-view').classList.toggle('hidden');
});

document.getElementById('btn-sync-all').onclick = async (e) => {
    const btn = e.currentTarget;
    btn.innerHTML = "Syncing...";
    nodes.forEach(n => cache[n.id] = null);
    await Promise.all(nodes.map(n => call(n.p, '/sync', 'POST')));
    updateUI();
    btn.innerHTML = '<i class="fa-solid fa-rotate"></i> Global Sync';
};

setInterval(updateUI, 3000);
updateUI();
