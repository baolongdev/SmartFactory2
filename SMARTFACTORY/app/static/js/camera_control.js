import { CAMERA_API_BASE } from "./helpers.js";
import { t } from "./i18n.js";

export let cameraRunning = false;

/**
 * Update camera-related UI elements based on running state
 * @param {boolean} running - Whether camera is running
 */
export function setCameraUI(running) {
    const btnStart = document.getElementById("btn-start-camera");
    const btnStop = document.getElementById("btn-stop-camera");

    if (running) {
        btnStart.disabled = true;
        btnStop.disabled = false;
    } else {
        btnStart.disabled = false;
        btnStop.disabled = true;
    }
}

/**
 * Start camera with selected source
 * Updates workflow step 1 (Camera Setup)
 * @returns {boolean} - Whether camera started successfully
 */
export async function startCamera() {
    const videoEl = document.getElementById('video-stream');
    const camStatusEl = document.getElementById('camera-status');

    cameraRunning = false;
    setCameraUI(false);

    // Always clear the img element before a new connection attempt.
    // If the previous attempt left src pointing to a failed URL, the
    // browser may cache the error and refuse to reload the same URL
    // without this explicit reset.
    videoEl.src = "";
    videoEl.style.display = "none";

    const camType = document.getElementById('camera-type').value;
    const usbIndex = parseInt(document.getElementById('usb-camera').value, 10);
    const rtspUrl = document.getElementById('rtsp-url').value.trim();

    let source = camType === "rtsp" ? rtspUrl : usbIndex;

    if (camType === 'rtsp' && !rtspUrl) {
        alert("Vui lòng nhập URL RTSP!");
        return false;
    }

    let res;
    try {
        res = await fetch(`${CAMERA_API_BASE}/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ src: source })
        });
    } catch (err) {
        console.error("[Camera] Fetch error:", err);
        updateCameraStatus(false, "Camera Error");
        return false;
    }

    if (!res) return false;

    let data;
    try {
        data = await res.json();
    } catch (err) {
        console.error("[Camera] Invalid JSON:", err);
        return false;
    }

    if (res.ok && data.status === "success") {
        cameraRunning = true;
        setCameraUI(true);

        videoEl.src = `${CAMERA_API_BASE}/stream`;
        videoEl.style.display = "block";

        updateCameraStatus(true, t('status.running'));
        return true;
    }

    cameraRunning = false;
    setCameraUI(false);

    videoEl.src = "";
    videoEl.style.display = "none";

    updateCameraStatus(false, t('status.error'));
    return false;
}

/**
 * Stop camera
 * Updates workflow steps accordingly
 */
export async function stopCamera() {
    const videoEl = document.getElementById('video-stream');
    const camStatusEl = document.getElementById('camera-status');
    const list = document.getElementById('detected-list');

    try {
        await fetch(`${CAMERA_API_BASE}/stop`, { method: "POST" });
    } catch (err) {
        console.error("[Camera] Stop error:", err);
    }

    cameraRunning = false;
    setCameraUI(false);

    videoEl.src = "";
    videoEl.style.display = "none";

    list.innerHTML = `<li class="sf-placeholder sf-empty">No objects detected</li>`;

    updateCameraStatus(false, t('status.stopped'));
}

/**
 * Update camera status indicator
 * @param {boolean} running - Camera running state
 * @param {string} text - Status text
 */
function updateCameraStatus(running, text) {
    const camStatusEl = document.getElementById('camera-status');
    if (!camStatusEl) return;

    if (running) {
        camStatusEl.className = "status-indicator status-online";
        camStatusEl.innerHTML = '<span class="dot-pulse"></span><span>' + text + '</span>';
    } else {
        camStatusEl.className = "status-indicator status-offline";
        camStatusEl.innerHTML = '<span class="dot-pulse"></span><span>' + text + '</span>';
    }
}
