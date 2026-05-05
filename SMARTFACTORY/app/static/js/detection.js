import { CAMERA_API_BASE, PCLS_API_BASE, PCLS_COLOR_CODES, getSelectedUser, buildFeedTopic, CMD_FEED } from "./helpers.js";
import { sendMQTT } from "./mqtt.js";
import { cameraRunning } from "./camera_control.js";
import { t } from "./i18n.js";

let lastActions = {};

// Debounce PCLS calls: don't resend the same color_code within PCLS_COOLDOWN ms
const PCLS_COOLDOWN = 5000;
const lastPclsSent = {};

/**
 * Notify PCLS service for a detected color.
 * Only fires for colors with a known code (red=1, blue=2, yellow=3).
 * Debounced per color_code to avoid flooding.
 * @param {string} colorName - Detected color name (e.g. "red")
 */
async function notifyPCLS(colorName) {
    const colorCode = PCLS_COLOR_CODES[colorName];
    if (!colorCode) return;                   // color not in PCLS mapping

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
 * Poll detections from camera API
 * Updates workflow steps 2 (Color Detection) and 3 (Object Tracking)
 */
export async function pollDetections() {
    if (!cameraRunning) return;

    const res = await fetch(`${CAMERA_API_BASE}/detections`);
    if (!res.ok) return;

    const data = await res.json();
    const list = document.getElementById("detected-list");

    // No detections
    if (!data.detections?.length) {
        list.innerHTML = `<li class="sf-placeholder sf-empty">${t('det.empty')}</li>`;
        return;
    }

    // Render detected objects
    list.innerHTML = data.detections.map(obj => {
        const c = obj.bgr ? `rgb(${obj.bgr[2]},${obj.bgr[1]},${obj.bgr[0]})` : "#888";
        // tracker_id = unique object ID (from Tracker)
        // action_id  = conveyor action number (used for MQTT, not for display)
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

    // Send MQTT commands + PCLS notifications based on detections
    const user = getSelectedUser();
    const now = Date.now();

    for (const obj of data.detections) {
        const action = obj.action_id;
        const duration = obj.duration_ms;

        // Skip if no action_id or duration
        if (!action || !duration) continue;

        const key = `${user}_${action}`;

        // Debounce: avoid sending duplicate commands
        if (!lastActions[key] || now - lastActions[key] > duration + 500) {
            await sendMQTT(
                buildFeedTopic(user, CMD_FEED),
                JSON.stringify({
                    action: action,
                    duration_ms: duration
                })
            );

            lastActions[key] = now;
        }

        // Notify PCLS for recognised colors (red/blue/yellow), debounced
        notifyPCLS(obj.name);
    }
}
