/**
 * poll_settings.js — Quản lý tần suất polling, lưu vào localStorage.
 *
 * Mỗi input thay đổi → lưu localStorage → gọi callback restart timer.
 */

const _STORAGE = {
    uart:   "sf-poll-uart-ms",
    detect: "sf-poll-detect-ms",
};
const _DEFAULT = {
    uart:   5000,
    detect: 1000,
};

/** Lấy giá trị ms hiện tại (localStorage → default). */
export function getPollMs(key) {
    const v = localStorage.getItem(_STORAGE[key]);
    return v ? Math.max(500, parseInt(v, 10)) : _DEFAULT[key];
}

/**
 * Kết nối input HTML với logic timer.
 * @param {{ onUart: (ms:number)=>void, onDetect: (ms:number)=>void }} callbacks
 */
export function initPollSettings({ onUart, onDetect }) {
    _wire("poll-uart-ms",   "uart",   1000,  30000, onUart);
    _wire("poll-detect-ms", "detect",  500,  10000, onDetect);
}

function _wire(id, key, min, max, callback) {
    const el = document.getElementById(id);
    if (!el) return;
    // Khôi phục giá trị đã lưu
    el.value = getPollMs(key);
    el.addEventListener("change", () => {
        const ms = Math.min(max, Math.max(min, parseInt(el.value, 10) || _DEFAULT[key]));
        el.value = ms;
        localStorage.setItem(_STORAGE[key], ms);
        callback(ms);
    });
}
