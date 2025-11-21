import { CAMERA_API_BASE } from "./helpers.js";

export let cameraRunning = false;

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

export async function startCamera() {
    const videoEl = document.getElementById('video-stream');
    const camStatusEl = document.getElementById('camera-status');

    const camType = document.getElementById('camera-type').value;
    const usbIndex = parseInt(document.getElementById('usb-camera').value, 10);
    const rtspUrl = document.getElementById('rtsp-url').value.trim();

    cameraRunning = false;
    setCameraUI(false);

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

        camStatusEl.innerHTML =
            '<i class="fas fa-circle" style="color:green;"></i> Camera Running';

        return true;
    }

    cameraRunning = false;
    setCameraUI(false);

    videoEl.src = "";
    videoEl.style.display = "none";

    camStatusEl.innerHTML =
        '<i class="fas fa-circle" style="color:red;"></i> Camera Error';

    return false;
}

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

    list.innerHTML = `<li style="color:#888;">No objects detected</li>`;
    camStatusEl.innerHTML =
        '<i class="fas fa-circle" style="color:gray;"></i> Camera Stopped';
}
