import { CAMERA_API_BASE } from "./helpers.js";
import { sendUART, UART_CMD } from "./uart.js";
import { cameraRunning } from "./camera_control.js";
import { t } from "./i18n.js";
import { pauseFor as pauseCycle } from "./conveyor_cycle.js";

// ── State ──────────────────────────────────────────────────────────────────
let conveyorRunning = false;
let servoOpen       = false;
let activeServoId   = 0;
let stopTimer       = null;

/**
 * Poll detections và điều khiển băng tải + servo qua UART.
 *
 * Flow:
 *   Không có hàng  → Conveyor Cycle tự chạy loop (RUN/STOP)
 *   Có hàng        → Interrupt cycle, chạy conveyor + mở servo theo color config
 *                    Sau duration_ms: đóng servo → dừng conveyor → cycle resume
 *   Hàng liên tục  → Timer reset mỗi lần detect, chờ thêm duration_ms
 */
export async function pollDetections() {
    if (!cameraRunning) return;

    const res = await fetch(`${CAMERA_API_BASE}/detections`);
    if (!res.ok) return;

    const data = await res.json();
    const list = document.getElementById("detected-list");

    // ── Không phát hiện hàng ──────────────────────────────────────────────
    if (!data.detections?.length) {
        list.innerHTML = `<li class="sf-placeholder sf-empty">${t('det.empty')}</li>`;
        // Timer vẫn chạy nếu còn — tránh giật khi mất 1 frame
        return;
    }

    // ── Render danh sách ──────────────────────────────────────────────────
    list.innerHTML = data.detections.map(obj => {
        const c   = obj.bgr ? `rgb(${obj.bgr[2]},${obj.bgr[1]},${obj.bgr[0]})` : "#888";
        const tid = obj.tracker_id ?? "?";
        return `
            <li class="py-1.5 sf-detect-item flex items-center gap-2">
                <span class="color-dot" style="background:${c}"></span>
                <span class="sf-detect-name">${obj.name}</span>
                <span class="sf-detect-meta ml-auto">#${tid} &middot; ${obj.duration_ms}ms</span>
            </li>
        `;
    }).join("");

    // ── Điều khiển băng tải + servo ───────────────────────────────────────
    const obj      = data.detections[0];
    const duration = obj.duration_ms;
    const servoId  = obj.servo_id ?? 0;

    // Interrupt conveyor cycle: nhường quyền điều khiển cho detection
    // Cycle tự resume sau khi timer dưới fire xong (duration + 100ms buffer)
    pauseCycle(duration + 100);

    // Chạy conveyor nếu chưa chạy
    if (!conveyorRunning) {
        await sendUART(UART_CMD.CONVEYOR_RUN);
        conveyorRunning = true;
    }

    // Mở servo theo cấu hình màu (nếu chưa mở)
    if (servoId > 0 && !servoOpen) {
        const openCmd = servoId === 1 ? UART_CMD.SERVO1_OPEN : UART_CMD.SERVO2_OPEN;
        await sendUART(openCmd);
        servoOpen     = true;
        activeServoId = servoId;
    }

    // Reset timer — mỗi lần detect kéo dài thêm duration_ms
    if (stopTimer) clearTimeout(stopTimer);
    stopTimer = setTimeout(async () => {
        if (servoOpen) {
            const closeCmd = activeServoId === 1 ? UART_CMD.SERVO1_CLOSE : UART_CMD.SERVO2_CLOSE;
            await sendUART(closeCmd);
            servoOpen     = false;
            activeServoId = 0;
        }
        await sendUART(UART_CMD.CONVEYOR_STOP);
        conveyorRunning = false;
        stopTimer = null;
        // Cycle sẽ tự resume (do pauseCycle đã set resumeTimer)
    }, duration);
}
