import { CAMERA_API_BASE, PCLS_API_BASE, PCLS_COLOR_CODES } from "./helpers.js";
import { sendUART, UART_CMD } from "./uart.js";
import { cameraRunning } from "./camera_control.js";
import { t } from "./i18n.js";
import { pauseFor as pauseCycle } from "./conveyor_cycle.js";

// ── Conveyor + servo state ─────────────────────────────────────────────────
// Chỉ gửi UART khi trạng thái thay đổi (tránh spam liên tục).
let conveyorRunning = false;   // băng tải đang chạy?
let servoOpen       = false;   // servo đang mở?
let activeServoId   = 0;       // servo nào đang mở (1 hoặc 2)
let stopTimer       = null;    // timer dừng sau duration_ms

// ── PCLS debounce ──────────────────────────────────────────────────────────
const PCLS_COOLDOWN = 5000;
const lastPclsSent  = {};

/**
 * Notify PCLS service cho màu phát hiện (red/blue/yellow), debounced 5s.
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
 * Poll detections và điều khiển băng tải qua UART.
 *
 * Logic băng tải:
 *   - Phát hiện vật thể → gửi 1 (chạy băng tải)
 *   - Reset timer: sau duration_ms kể từ lần detect cuối → gửi 0 (dừng)
 *   - Không phát hiện → để timer tự chạy, không gửi 0 ngay lập tức
 *     (tránh giật khi object thoáng mất 1 frame)
 */
export async function pollDetections() {
    if (!cameraRunning) return;

    const res = await fetch(`${CAMERA_API_BASE}/detections`);
    if (!res.ok) return;

    const data = await res.json();
    const list = document.getElementById("detected-list");

    // ── Render danh sách vật thể ───────────────────────────────────────────
    if (!data.detections?.length) {
        list.innerHTML = `<li class="sf-placeholder sf-empty">${t('det.empty')}</li>`;
        // Không gửi 0 ngay — để timer xử lý để tránh giật
        return;
    }

    list.innerHTML = data.detections.map(obj => {
        const c   = obj.bgr ? `rgb(${obj.bgr[2]},${obj.bgr[1]},${obj.bgr[0]})` : "#888";
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

    // ── Điều khiển băng tải + servo ───────────────────────────────────────
    // Dùng object đầu tiên (max_objects=1 nên chỉ có 1)
    const obj      = data.detections[0];
    const duration = obj.duration_ms;
    const servoId  = obj.servo_id ?? 0;

    // Interrupt conveyor cycle — nhường quyền điều khiển cho detection
    // Cycle sẽ tự resume sau duration + 500ms buffer
    pauseCycle(duration + 500);

    // Gửi lệnh chạy băng tải nếu chưa chạy
    if (!conveyorRunning) {
        await sendUART(UART_CMD.CONVEYOR_RUN);
        conveyorRunning = true;
    }

    // Mở servo nếu chưa mở (servo_id 1 hoặc 2)
    if (servoId > 0 && !servoOpen) {
        const openCmd = servoId === 1 ? UART_CMD.SERVO1_OPEN : UART_CMD.SERVO2_OPEN;
        await sendUART(openCmd);
        servoOpen     = true;
        activeServoId = servoId;
    }

    // Reset timer dừng — mỗi lần detect thành công kéo dài thêm duration_ms
    if (stopTimer) clearTimeout(stopTimer);
    stopTimer = setTimeout(async () => {
        // Đóng servo trước khi dừng băng tải
        if (servoOpen) {
            const closeCmd = activeServoId === 1 ? UART_CMD.SERVO1_CLOSE : UART_CMD.SERVO2_CLOSE;
            await sendUART(closeCmd);
            servoOpen     = false;
            activeServoId = 0;
        }
        await sendUART(UART_CMD.CONVEYOR_STOP);
        conveyorRunning = false;
        stopTimer = null;
    }, duration);

    // ── PCLS notify ────────────────────────────────────────────────────────
    notifyPCLS(obj.name);
}
