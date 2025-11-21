/* ================= UI Camera Switch ================= */
export function switchCameraType() {
    const typeSelect = document.getElementById('camera-type');
    const camType = typeSelect.value;

    const usbGroup = document.getElementById('usb-group');
    const rtspGroup = document.getElementById('rtsp-group');
    const usbSelect = document.getElementById('usb-camera');
    const rtspInput = document.getElementById('rtsp-url');

    if (camType === 'rtsp') {
        usbGroup.style.display = 'none';
        rtspGroup.style.display = 'block';
        usbSelect.disabled = true;
        rtspInput.disabled = false;
    } else {
        usbGroup.style.display = 'block';
        rtspGroup.style.display = 'none';
        usbSelect.disabled = false;
        rtspInput.disabled = true;
    }
}

export function initFullscreenButton() {
    window.toggleFullscreen = function () {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    };
}

export function initEmergencyStop(sendMQTT) {
    window.emergencyStop = async function () {
        alert("🚨 Emergency Stop Triggered!");
        await sendMQTT("emergency", "STOP");
    };
}

export async function loadUSBCameras() {
    const usbSelect = document.getElementById("usb-camera");

    usbSelect.innerHTML = `<option>Loading...</option>`;

    try {
        const res = await fetch("/api/camera/list");
        const data = await res.json();

        if (!Array.isArray(data.cameras) || data.cameras.length === 0) {
            usbSelect.innerHTML = `<option value="">No Camera Found</option>`;
            return;
        }

        usbSelect.innerHTML = data.cameras.map(cam =>
            `<option value="${cam.index}">${cam.name}</option>`
        ).join("");

    } catch (err) {
        console.error("Failed to load USB cameras", err);
        usbSelect.innerHTML = `<option value="">Error</option>`;
    }
}
