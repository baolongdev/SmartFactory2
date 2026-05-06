// ======================== IMPORT MODULES ===========================
import { switchCameraType, initFullscreenButton, initEmergencyStop, loadUSBCameras } from "./ui_camera.js";
import { startCamera, stopCamera } from "./camera_control.js";
import { pollUARTStatus, emergencyStop } from "./uart.js";
import { initCycleControls } from "./conveyor_cycle.js";
import { pollDetections } from "./detection.js";
import {
    renderColorTable,
    saveColorConfig,
    addNewColorRow,
    getColorHex,
} from "./colors.js";
import { applyI18n, setLang, t } from "./i18n.js";

// Expose t() so the inline theme toggle script can resolve i18n titles
window.__sf_i18n_t = t;

// (Color hex map lives in colors.js — imported as getColorHex above)

// ======================== TOAST ===========================
// Exposed on window so colors.js can call showToast()
window.showToast = function (message, type = "success") {
    const existing = document.getElementById("sf-toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.id = "sf-toast";
    const ok = type === "success";
    toast.style.cssText = `
        position: fixed; bottom: 24px; right: 24px; z-index: 9999;
        display: flex; align-items: center; gap: 10px;
        padding: 11px 16px; border-radius: 6px;
        font-size: 0.8rem; font-weight: 600;
        background: ${ok ? "var(--success-muted)" : "var(--destructive-muted)"};
        color: ${ok ? "var(--success)" : "var(--destructive)"};
        border: 1px solid ${ok ? "var(--success)" : "var(--destructive)"};
        animation: sf-slide-in 0.2s ease;
    `;
    toast.innerHTML = `<i class="fas ${ok ? "fa-circle-check" : "fa-circle-xmark"}"></i> ${message}`;
    document.body.appendChild(toast);
    setTimeout(() => { if (toast.parentNode) toast.remove(); }, 3000);
};

// ======================== INITIALIZE WHEN PAGE LOADS ===========================
document.addEventListener("DOMContentLoaded", async () => {

    // --- UI Setup ---
    initFullscreenButton();
    initEmergencyStop(emergencyStop);
    initCycleControls();

    // ── Event listeners — không dùng onclick/onchange inline ──────────────

    // Camera source
    document.getElementById('camera-type')
        ?.addEventListener('change', switchCameraType);
    document.getElementById('btn-start-camera')
        ?.addEventListener('click', startCamera);
    document.getElementById('btn-stop-camera')
        ?.addEventListener('click', stopCamera);

    // Color config
    document.getElementById('btn-add-color')
        ?.addEventListener('click', addNewColorRow);
    document.getElementById('btn-save-color')
        ?.addEventListener('click', saveColorConfig);

    // Color table: event delegation — covers cả static lẫn dynamic rows
    document.getElementById('color-table-body')
        ?.addEventListener('change', e => {
            if (e.target.classList.contains('color-name')) {
                const dot = e.target.closest('tr')?.querySelector('.color-dot');
                if (dot) dot.style.background = getColorHex(e.target.value);
            }
        });

    // UART log clear
    document.getElementById('btn-clear-uart')
        ?.addEventListener('click', () => {
            const box = document.getElementById("uart-log");
            if (box) box.innerHTML = `<div class="sf-empty">${t('uart.empty')}</div>`;
        });

    // Language switcher
    document.getElementById('lang-select')
        ?.addEventListener('change', e => setLang(e.target.value));

    // When language changes: re-render all i18n elements + dynamic JS-injected text
    window.addEventListener('sf-lang-change', () => {
        applyI18n();
        // Camera placeholder (managed by MutationObserver — only update if visible)
        const ph = document.getElementById('no-camera-placeholder');
        if (ph && ph.style.display !== 'none') {
            const ptitle = ph.querySelector('[data-i18n="cam.ph.title"]');
            const psub   = ph.querySelector('[data-i18n="cam.ph.sub"]');
            if (ptitle) ptitle.textContent = t('cam.ph.title');
            if (psub)   psub.textContent   = t('cam.ph.sub');
        }
        // UART log empty state (only if it shows the empty message)
        const uartLog = document.getElementById('uart-log');
        const emptyDiv = uartLog?.querySelector('.sf-empty');
        if (emptyDiv) emptyDiv.textContent = t('uart.empty');
        // Detection empty state
        const detList = document.getElementById('detected-list');
        const detEmpty = detList?.querySelector('.sf-placeholder');
        if (detEmpty) detEmpty.textContent = t('det.empty');
        // Re-render color table (loading/empty text)
        renderColorTable();
    });

    // Apply translations immediately on load
    applyI18n();

    // ── Secondary systems — always init regardless of camera state ───────
    // Running these first means USB list, colors and MQTT are ready even
    // if the camera fails to start, so the user doesn't need a full reload.
    await loadUSBCameras();
    pollUARTStatus();
    await renderColorTable();
    setInterval(pollUARTStatus, 5000);

    // ── Camera auto-start ─────────────────────────────────────────────────
    switchCameraType();

    const ok = await startCamera();
    if (!ok) {
        console.warn("Camera failed → detection polling disabled");
        return;
    }

    setInterval(pollDetections, 1000);
});
