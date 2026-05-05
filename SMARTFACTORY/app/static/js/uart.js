import { UART_API_BASE } from "./helpers.js";

/**
 * Send a JSON command to the device via UART (through Flask backend).
 * @param {Object} data - e.g. {action: 1, duration_ms: 4000}
 */
export async function sendUART(data) {
    appendUARTLog(`→ ${JSON.stringify(data)}`);
    try {
        await fetch(`${UART_API_BASE}/send`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
    } catch (err) {
        console.warn("[UART] Send failed:", err);
    }
}

/**
 * Poll UART connection status.
 * Updates the #uart-status indicator in the header.
 */
export async function pollUARTStatus() {
    try {
        const res = await fetch(`${UART_API_BASE}/status`);
        if (!res.ok) return;
        const data = await res.json();
        const el = document.getElementById("uart-status");
        if (!el) return;
        const d = data.data;
        if (d.connected) {
            el.className = "status-indicator status-online";
            el.innerHTML = `<span class="dot-pulse"></span><span>UART ${d.port}</span>`;
        } else {
            el.className = "status-indicator status-offline";
            el.innerHTML = `<span class="dot-pulse"></span><span>UART Offline</span>`;
        }
    } catch (_) {}
}

/**
 * Read the latest data received from the device.
 * Appends to log if data is non-null.
 * @returns {Object|string|null}
 */
export async function readUART() {
    try {
        const res = await fetch(`${UART_API_BASE}/read`);
        if (!res.ok) return null;
        const data = await res.json();
        if (data.data != null) appendUARTLog(`← ${JSON.stringify(data.data)}`);
        return data.data;
    } catch (_) {
        return null;
    }
}

/**
 * Append a line to the UART log panel (#uart-log).
 * @param {string} text
 */
export function appendUARTLog(text) {
    const box = document.getElementById("uart-log");
    if (!box) return;

    const placeholder = box.querySelector(".sf-empty");
    if (placeholder) placeholder.remove();

    const time = new Date().toLocaleTimeString();
    const entry = document.createElement("div");
    entry.className = "py-1 sf-log-entry font-mono";
    entry.innerHTML = `<span class="sf-log-time">[${time}]</span> <span class="sf-log-text">${text}</span>`;
    box.insertBefore(entry, box.firstChild);

    // Keep at most 100 entries
    while (box.children.length > 100) box.removeChild(box.lastChild);
}
