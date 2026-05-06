import { UART_API_BASE } from "./helpers.js";

// ── Command table (mirrors uart_service.py COMMANDS) ──────────────────────
export const UART_CMD = {
    CONVEYOR_STOP:  0,
    CONVEYOR_RUN:   1,
    SERVO1_CLOSE:   2,
    SERVO1_OPEN:    3,
    SERVO2_CLOSE:   4,
    SERVO2_OPEN:    5,
    EMERGENCY_STOP: 6,
};

const CMD_LABEL = {
    0: "0 — CONVEYOR STOP",
    1: "1 — CONVEYOR RUN",
    2: "2 — SERVO1 CLOSE",
    3: "3 — SERVO1 OPEN",
    4: "4 — SERVO2 CLOSE",
    5: "5 — SERVO2 OPEN",
    6: "6 — EMERGENCY STOP",
};

// TX log CSS class per command
const CMD_CLASS = {
    0: "sf-log-stop",
    1: "sf-log-run",
    2: "sf-log-servo",
    3: "sf-log-servo",
    4: "sf-log-servo",
    5: "sf-log-servo",
    6: "sf-log-estop",
};

/**
 * Gửi lệnh đơn (0–5) qua UART.
 * @param {number} command  0–5
 */
export async function sendUART(command) {
    appendUARTLog(`→ ${CMD_LABEL[command] ?? command}`);
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
 * Dừng khẩn cấp: gửi 0 + 2 + 4 qua backend /api/uart/estop.
 */
export async function emergencyStop() {
    appendUARTLog(`→ ${CMD_LABEL[6]}`);
    try {
        await fetch(`${UART_API_BASE}/estop`, { method: "POST" });
    } catch (err) {
        console.warn("[UART] Emergency stop failed:", err);
    }
}

/**
 * Poll UART connection status.
 * Cập nhật header indicator (#uart-status) và card info panel.
 */
export async function pollUARTStatus() {
    try {
        const res = await fetch(`${UART_API_BASE}/status`);
        if (!res.ok) return;
        const { data } = await res.json();

        // ── Header indicator ─────────────────────────────────────────────
        const el = document.getElementById("uart-status");
        if (el) {
            el.className = data.connected
                ? "status-indicator status-online"
                : "status-indicator status-offline";
            el.innerHTML = `<span class="dot-pulse"></span><span>UART</span>`;
        }

        // ── Card: connection row ─────────────────────────────────────────
        const badge = document.getElementById("uart-conn-badge");
        const text  = document.getElementById("uart-conn-text");
        if (badge && text) {
            badge.className = data.connected
                ? "uart-badge uart-badge-connected"
                : "uart-badge uart-badge-offline";
            text.textContent = data.connected ? "Connected" : "Offline";
        }
        const port = document.getElementById("uart-conn-port");
        const baud = document.getElementById("uart-conn-baud");
        if (port) port.textContent = data.port     || "—";
        if (baud) baud.textContent = data.baudrate ? `${data.baudrate} bps` : "—";

        // ── Card: last command ───────────────────────────────────────────
        const last = document.getElementById("uart-conn-last");
        if (last) {
            const cmd = data.last_command;
            if (cmd === null || cmd === undefined) {
                last.textContent  = "—";
                last.style.color  = "";
            } else {
                last.textContent  = CMD_LABEL[cmd] ?? String(cmd);
                last.style.color  = cmd === 1 ? "var(--success)"
                                  : cmd === 6 ? "var(--destructive)"
                                  : cmd === 0 ? "var(--fg-subtle)"
                                  : "var(--warning)";
            }
        }

        // ── Card: device state badges ────────────────────────────────────
        _setStateBadge("uart-state-conveyor",
            data.conveyor_running, "RUNNING", "STOPPED");
        _setStateBadge("uart-state-servo1",
            data.servo1_open,      "OPEN",    "CLOSED");
        _setStateBadge("uart-state-servo2",
            data.servo2_open,      "OPEN",    "CLOSED");

    } catch (_) {}
}

function _setStateBadge(id, active, labelOn, labelOff) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = active ? labelOn : labelOff;
    el.className = active
        ? "uart-state-badge uart-state-on"
        : "uart-state-badge uart-state-off";
}

/**
 * Đọc dữ liệu mới nhất nhận từ thiết bị.
 * @returns {string|null}
 */
export async function readUART() {
    try {
        const res = await fetch(`${UART_API_BASE}/read`);
        if (!res.ok) return null;
        const { data } = await res.json();
        if (data != null) appendUARTLog(`← ${data}`);
        return data;
    } catch (_) {
        return null;
    }
}

/**
 * Ghi log vào panel #uart-log với màu theo loại lệnh.
 * @param {string} text
 */
export function appendUARTLog(text) {
    const box = document.getElementById("uart-log");
    if (!box) return;
    const placeholder = box.querySelector(".sf-empty");
    if (placeholder) placeholder.remove();

    const isTx = text.startsWith("→");
    const isRx = text.startsWith("←");
    const arrow   = text.slice(0, 1);
    const content = text.slice(2).trim();

    // Map content to CSS class
    let contentClass = "sf-log-text";
    if (isTx) {
        if      (content.includes("RUN"))       contentClass = "sf-log-run";
        else if (content.includes("EMERGENCY")) contentClass = "sf-log-estop";
        else if (content.includes("SERVO"))     contentClass = "sf-log-servo";
        else                                    contentClass = "sf-log-stop";
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
