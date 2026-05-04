import { CAMERA_API_BASE, getSelectedUser, buildFeedTopic, CMD_FEED } from "./helpers.js";
import { sendMQTT } from "./mqtt.js";
import { cameraRunning } from "./camera_control.js";

let lastActions = {};

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
        list.innerHTML = `<li class="sf-placeholder sf-empty">No objects detected</li>`;
        return;
    }

    // Update workflow: Step 2 completed, Step 3 active
    if (window.updateWorkflowStep) {
        window.updateWorkflowStep(3, true);
    }

    // Render detected objects
    list.innerHTML = data.detections.map(obj => {
        const c = obj.bgr ? `rgb(${obj.bgr[2]},${obj.bgr[1]},${obj.bgr[0]})` : "#888";
        return `
            <li class="py-1.5 sf-detect-item flex items-center gap-2">
                <span class="color-dot" style="background:${c}"></span>
                <span class="sf-detect-name">${obj.name}</span>
                <span class="sf-detect-meta ml-auto">
                    ID:${obj.action_id} &middot; ${obj.duration_ms}ms
                </span>
            </li>
        `;
    }).join("");

    // Send MQTT commands based on detections
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
    }
}
