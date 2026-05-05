import { CAMERA_API_BASE, PCLS_API_BASE, PCLS_COLOR_CODES } from "./helpers.js";
import { sendUART } from "./uart.js";
import { cameraRunning } from "./camera_control.js";
import { t } from "./i18n.js";

// ── Conveyor state ─────────────────────────────────────────────────────────
// Chỉ gửi UART khi trạng thái thay đổi (tránh spam 0/1 liên tục).
let conveyorRunning = false;   // băng tải đang chạy?
let stopTimer       = null;    // timer gửi "0" sau duration_ms

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

    // ── Điều khiển băng tải ────────────────────────────────────────────────
    // Dùng object đầu tiên (max_objects=1 nên chỉ có 1)
    const obj      = data.detections[0];
    const duration = obj.duration_ms;

    // Gửi 1 nếu băng tải chưa chạy
    if (!conveyorRunning) {
        await sendUART(1);
        conveyorRunning = true;
    }

    // Reset timer dừng — mỗi lần detect thành công kéo dài thêm duration_ms
    if (stopTimer) clearTimeout(stopTimer);
    stopTimer = setTimeout(async () => {
        await sendUART(0);
        conveyorRunning = false;
        stopTimer = null;
    }, duration);

    // ── PCLS notify ────────────────────────────────────────────────────────
    notifyPCLS(obj.name);
}
