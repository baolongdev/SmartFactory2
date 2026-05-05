import { UART_API_BASE } from "./helpers.js";

/**
 * Gửi lệnh băng tải qua UART.
 * @param {0|1} command  — 0: dừng, 1: chạy
 */
export async function sendUART(command) {
    appendUARTLog(`→ ${command === 1 ? "1 (RUN)" : "0 (STOP)"}`);
    try {
        await fetch(`${UART_API_BASE}/command`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command }),
        });
    } catch (err) {
        console.warn("[UART] Send failed:", err);
    }
}

/**
 * Poll UART connection status, cập nhật indicator #uart-status.
 */
export async function pollUARTStatus() {
    try {
        const res = await fetch(`${UART_API_BASE}/status`);
        if (!res.ok) return;
        const { data } = await res.json();
        const el = document.getElementById("uart-status");
        if (!el) return;
        if (data.connected) {
            el.className = "status-indicator status-online";
            el.innerHTML = `<span class="dot-pulse"></span><span>UART ${data.port}</span>`;
        } else {
            el.className = "status-indicator status-offline";
            el.innerHTML = `<span class="dot-pulse"></span><span>UART Offline</span>`;
        }
    } catch (_) {}
}

/**
 * Đọc dữ liệu mới nhất nhận từ thiết bị.
 * @returns {any|null}
 */
export async function readUART() {
    try {
        const res = await fetch(`${UART_API_BASE}/read`);
        if (!res.ok) return null;
        const { data } = await res.json();
        if (data != null) appendUARTLog(`← ${JSON.stringify(data)}`);
        return data;
    } catch (_) {
        return null;
    }
}

/**
 * Ghi log vào panel #uart-log.
 * Tự động phân màu:
 *   → 1 (RUN)  — mũi tên xanh dương, text xanh lá
 *   → 0 (STOP) — mũi tên xanh dương, text xám
 *   ← ...      — mũi tên + text màu vàng (RX từ thiết bị)
 * @param {string} text
 */
export function appendUARTLog(text) {
    const box = document.getElementById("uart-log");
    if (!box) return;
    const placeholder = box.querySelector(".sf-empty");
    if (placeholder) placeholder.remove();

    const isTx = text.startsWith("→");
    const isRx = text.startsWith("←");

    // Tách arrow và phần nội dung
    const arrow   = text.slice(0, 1);          // "→" hoặc "←"
    const content = text.slice(2).trim();       // phần còn lại

    // Chọn class cho nội dung TX
    let contentClass = "sf-log-text";
    if (isTx) {
        contentClass = content.includes("RUN") ? "sf-log-run" : "sf-log-stop";
    }

    const dirClass = isTx ? "sf-log-tx" : isRx ? "sf-log-rx" : "";
    const time = new Date().toLocaleTimeString();

    const entry = document.createElement("div");
    entry.className = `py-1 sf-log-entry font-mono ${dirClass}`;
    entry.innerHTML = `<span class="sf-log-time">[${time}]</span>`
                    + `<span class="sf-log-arrow">${arrow}</span>`
                    + `<span class="${contentClass}">${content}</span>`;

    box.insertBefore(entry, box.firstChild);
    while (box.children.length > 100) box.removeChild(box.lastChild);
}
