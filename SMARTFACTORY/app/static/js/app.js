// ======================== IMPORT MODULES ===========================
import { switchCameraType, initFullscreenButton, initEmergencyStop, loadUSBCameras } from "./ui_camera.js";
import { startCamera, stopCamera } from "./camera_control.js";
import { pollMQTTStatus } from "./mqtt.js";
import { pollDetections } from "./detection.js";
import {
    renderColorTable,
    saveColorConfig,
    addNewColorRow
} from "./colors.js";
import { pingConveyor } from "./conveyor.js";

// ======================== WORKFLOW STEP MANAGEMENT ===========================
// Exposed on window so camera_control.js can call it
window.updateWorkflowStep = function (stepNumber, completed = null) {
    for (let i = 1; i <= 4; i++) {
        const step = document.getElementById(`step-${i}`);
        if (step) step.classList.remove("active", "completed");
    }
    if (completed === null) return;
    if (completed) {
        for (let i = 1; i < stepNumber; i++) {
            const step = document.getElementById(`step-${i}`);
            if (step) step.classList.add("completed");
        }
    }
    const currentStep = document.getElementById(`step-${stepNumber}`);
    if (currentStep) currentStep.classList.add(completed ? "completed" : "active");
};

// ======================== COLOR HEX MAP ===========================
const _colorHexMap = {
    red:    "#dc2626", green:  "#16a34a", blue:   "#2563eb",
    yellow: "#ca8a04", orange: "#ea580c", purple: "#9333ea", pink: "#db2777"
};

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
    initEmergencyStop();

    // ── Event listeners — không dùng onclick/onchange inline ──────────────

    // Camera source
    document.getElementById('camera-type')
        ?.addEventListener('change', switchCameraType);
    document.getElementById('btn-start-camera')
        ?.addEventListener('click', startCamera);
    document.getElementById('btn-stop-camera')
        ?.addEventListener('click', stopCamera);

    // Conveyor
    document.getElementById('conveyor-select')
        ?.addEventListener('change', e => pingConveyor(e.target.value));

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
                if (dot) dot.style.background = _colorHexMap[e.target.value] || '#6b7280';
            }
        });

    // MQTT log clear
    document.getElementById('btn-clear-mqtt')
        ?.addEventListener('click', () => {
            const box = document.getElementById("mqtt-log");
            if (box) box.innerHTML = `<div class="sf-empty">No messages yet...</div>`;
        });

    // ── Camera init ───────────────────────────────────────────────────────
    window.updateWorkflowStep(1);
    switchCameraType();

    const ok = await startCamera();
    if (!ok) {
        console.warn("Camera failed → skip polling");
        return;
    }

    await loadUSBCameras();

    window.updateWorkflowStep(2, true);

    // ── Services ──────────────────────────────────────────────────────────
    pollMQTTStatus();
    await renderColorTable();

    setInterval(pollMQTTStatus, 5000);
    setInterval(pollDetections, 1000);
});
