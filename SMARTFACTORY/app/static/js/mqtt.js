import { MQTT_API_BASE } from "./helpers.js";

/**
 * Send MQTT message to topic
 * @param {string} topic - MQTT topic
 * @param {string} message - Message payload
 */
export async function sendMQTT(topic, message) {
    appendMQTTLog(`→ SEND: ${topic} | ${message}`);

    await fetch(`${MQTT_API_BASE}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, message })
    });
}

/**
 * Poll MQTT connection status
 * Updates status indicator in header
 */
export async function pollMQTTStatus() {
    const res = await fetch(`${MQTT_API_BASE}/status`);
    if (!res.ok) return;

    const data = await res.json();
    const statusEl = document.getElementById('mqtt-status');

    if (!statusEl) return;

    if (data.data.connected) {
        statusEl.className = "status-indicator status-online";
        statusEl.innerHTML = '<span class="dot-pulse"></span><span>MQTT Online</span>';
    } else {
        statusEl.className = "status-indicator status-offline";
        statusEl.innerHTML = '<span class="dot-pulse"></span><span>MQTT Offline</span>';
    }
}

/**
 * Poll MQTT messages for a topic
 * @param {string} topic - MQTT topic to poll
 * @returns {any} - Last message received
 */
export async function pollMQTTMessages(topic) {
    const res = await fetch(`${MQTT_API_BASE}/messages?topic=${topic}`);
    if (!res.ok) return null;

    const data = await res.json();
    const msg = data.message;

    appendMQTTLog(`← RECV: ${topic} | ${JSON.stringify(msg)}`);
    return msg;
}

/**
 * Append message to MQTT log box
 * Uses Tailwind classes for consistent styling
 * @param {string} text - Log message
 */
export function appendMQTTLog(text) {
    const box = document.getElementById("mqtt-log");
    if (!box) return;

    // Remove placeholder if exists
    const placeholder = box.querySelector(".sf-empty");
    if (placeholder) placeholder.remove();

    const time = new Date().toLocaleTimeString();

    // Create log entry using theme-aware CSS classes
    const logEntry = document.createElement("div");
    logEntry.className = "py-1 sf-log-entry font-mono";
    logEntry.innerHTML = `<span class="sf-log-time">[${time}]</span> <span class="sf-log-text">${text}</span>`;

    // Insert at top
    box.insertBefore(logEntry, box.firstChild);

    // Limit log entries to prevent memory issues
    const maxEntries = 100;
    while (box.children.length > maxEntries) {
        box.removeChild(box.lastChild);
    }
}
