import { CAMERA_API_BASE, getSelectedUser, buildFeedTopic, CMD_FEED } from "./helpers.js";
import { sendMQTT } from "./mqtt.js";
import { cameraRunning } from "./camera_control.js";

let lastActions = {};

export async function pollDetections() {
    if (!cameraRunning) return;

    const res = await fetch(`${CAMERA_API_BASE}/detections`);
    if (!res.ok) return;

    const data = await res.json();
    const list = document.getElementById("detected-list");

    // Không có detection
    if (!data.detections?.length) {
        list.innerHTML = `<li style="color:#888;">No objects detected</li>`;
        return;
    }

    // Render lên UI
    list.innerHTML = data.detections.map(obj => {
        const c = obj.bgr ? `rgb(${obj.bgr[2]},${obj.bgr[1]},${obj.bgr[0]})` : "#888";
        return `
            <li>
                <span style="display:inline-block;width:12px;height:12px;background:${c};
                border:1px solid #000;margin-right:5px;"></span>
                <b>${obj.name}</b>
                <span style="color:#666;font-size:12px;"> 
                    (ID: ${obj.action_id}, ${obj.duration_ms}ms)
                </span>
            </li>
        `;
    }).join("");

    const user = getSelectedUser();
    const now = Date.now();

    // 🔥 Gửi MQTT dựa trên dữ liệu từ BE
    for (const obj of data.detections) {

        const action = obj.action_id;
        const duration = obj.duration_ms;

        // Nếu không có action_id hoặc duration_ms => bỏ qua
        if (!action || !duration) continue;

        const key = `${user}_${action}`;

        // Chống gửi trùng lặp (debounce theo duration)
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
