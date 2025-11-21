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


// ======================== EXPOSE GLOBAL (HTML BUTTONS) ===========================
window.startCamera = startCamera;
window.stopCamera = stopCamera;

window.saveColorConfig = saveColorConfig;
window.addNewColorRow = addNewColorRow;
window.pingConveyor = pingConveyor;

window.clearMQTTLog = function () {
    const box = document.getElementById("mqtt-log");
    if (box) {
        box.innerHTML = `<div class="placeholder">No log yet...</div>`;
    }
};

window.updateRowColor = function (select) {
    const row = select.closest("tr");
    const color = select.value;

    // Remove old color classes
    row.className = "color-row";
    row.classList.add(`color-${color}`);
};




// ======================== INITIALIZE WHEN PAGE LOADS ===========================
document.addEventListener("DOMContentLoaded", async () => {

    // --- UI Setup ---
    initFullscreenButton();
    initEmergencyStop();

    // --- Camera ---
    switchCameraType();
    const ok = await startCamera();
    if (!ok) {
        console.warn("Camera failed → disable detection polling");
        return; // ⛔ DỪNG không chạy pollDetect
    }

    await loadUSBCameras();   // <-- 🔥 AUTO LOAD CAMERA LIST
    console.log("Camera list loaded.");

    // --- MQTT Initial Status ---
    pollMQTTStatus();

    // --- Load Colors Config from Server ---
    await renderColorTable();

    // --- Auto Poll ---
    setInterval(pollMQTTStatus, 5000);
    setInterval(pollDetections, 1000);
});
