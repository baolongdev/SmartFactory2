import { MQTT_API_BASE } from "./helpers.js";

export async function sendMQTT(topic, message) {
    appendMQTTLog(`→ SEND: ${topic} | ${message}`);

    await fetch(`${MQTT_API_BASE}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, message })
    });
}

export async function pollMQTTStatus() {
    const res = await fetch(`${MQTT_API_BASE}/status`);
    if (!res.ok) return;

    const data = await res.json();
    const statusEl = document.getElementById('mqtt-status');

    if (data.data.connected) {
        statusEl.innerHTML = '<i class="fas fa-circle" style="color:green;"></i> MQTT Online';
    } else {
        statusEl.innerHTML = '<i class="fas fa-circle" style="color:red;"></i> MQTT Offline';
    }
}

export async function pollMQTTMessages(topic) {
    const res = await fetch(`${MQTT_API_BASE}/messages?topic=${topic}`);
    if (!res.ok) return null;

    const data = await res.json();
    const msg = data.message;

    appendMQTTLog(`← RECV: ${topic} | ${JSON.stringify(msg)}`);

    return msg;
}

export function appendMQTTLog(text) {
    const box = document.getElementById("mqtt-log");
    if (!box) return;

    const placeholder = box.querySelector(".placeholder");
    if (placeholder) placeholder.remove();

    const time = new Date().toLocaleTimeString();

    box.insertAdjacentHTML(
        "afterbegin",
        `<div class="log-item">[${time}] ${text}</div>`
    );
}

