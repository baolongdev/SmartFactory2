import { CAMERA_API_BASE, PCLS_API_BASE, PCLS_COLOR_CODES } from "./helpers.js";
import { sendUART } from "./uart.js";
import { cameraRunning } from "./camera_control.js";
import { t } from "./i18n.js";

let lastActions = {};

// Debounce PCLS calls per color_code
const PCLS_COOLDOWN = 5000;
const lastPclsSent = {};

/**
 * Notify PCLS service for a detected color (red/blue/yellow only), debounced.
 * @param {string} colorName
 */
async function notifyPCLS(colorName) {
    const colorCode = PCLS_COLOR_CODES[colorName];
    if (!colorCode) return;

    const now = Date.now();
    if (lastPclsSent[colorCode] && now - lastPclsSent[colorCode] < PCLS_COOLDOWN) return;
    lastPclsSent[colorCode] = now;

    try {
        await fetch(`${PCLS_API_BASE}/notify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ color_code: colorCode, color_name: colorName }),
        });
    } catch (err) {
        console.warn("[PCLS] Notify failed:", err);
    }
}

/**
 * Poll detections from camera API and send UART commands.
 * Updates the detected-objects list in the UI.
 */
export async function pollDetections() {
    if (!cameraRunning) return;

    const res = await fetch(`${CAMERA_API_BASE}/detections`);
    if (!res.ok) return;

    const data = await res.json();
    const list = document.getElementById("detected-list");

    if (!data.detections?.length) {
        list.innerHTML = `<li class="sf-placeholder sf-empty">${t('det.empty')}</li>`;
        return;
    }

    // Render detected objects
    list.innerHTML = data.detections.map(obj => {
        const c = obj.bgr ? `rgb(${obj.bgr[2]},${obj.bgr[1]},${obj.bgr[0]})` : "#888";
        const tid = obj.tracker_id ?? "?";
        return `
            <li class="py-1.5 sf-detect-item flex items-center gap-2">
                <span class="color-dot" style="background:${c}"></span>
                <span class="sf-detect-name">${obj.name}</span>
                <span class="sf-detect-meta ml-auto">
                    #${tid} &middot; ${obj.duration_ms}ms
                </span>
            </li>
        `;
    }).join("");

    // Send UART commands based on detections
    const now = Date.now();
    for (const obj of data.detections) {
        const action   = obj.action_id;
        const duration = obj.duration_ms;
        if (!action || !duration) continue;

        // Debounce: avoid sending duplicate commands within duration + 500ms
        if (!lastActions[action] || now - lastActions[action] > duration + 500) {
            await sendUART({ action, duration_ms: duration });
            lastActions[action] = now;
        }

        // Notify PCLS for red/blue/yellow (debounced)
        notifyPCLS(obj.name);
    }
}
