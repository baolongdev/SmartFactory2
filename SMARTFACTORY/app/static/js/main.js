/* ================== Fullscreen ================== */
function toggleFullscreen() {
    if (!document.fullscreenElement)
        document.documentElement.requestFullscreen().catch(console.error);
    else
        document.exitFullscreen();
}

/* ================== Emergency Stop ================== */
function emergencyStop() {
    alert("🚨 Emergency Stop triggered!");
    sendMQTT("emergency", "STOP");
}

/* ================== Camera Control ================== */
let cameraRunning = false;

async function startCamera() {
    const videoEl = document.getElementById('video-stream');
    try {
        const res = await fetch('/api/camera/start', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
            videoEl.src = "/api/camera/stream";
            videoEl.style.display = 'block';
            cameraRunning = true;
        } else {
            videoEl.style.display = 'none';
            console.warn('Start camera failed:', data);
        }
    } catch (e) {
        videoEl.style.display = 'none';
        console.error(e);
    }
}

async function stopCamera() {
    const videoEl = document.getElementById('video-stream');
    try {
        await fetch('/api/camera/stop', { method: 'POST' });
        videoEl.src = "";
        videoEl.style.display = 'none';
        cameraRunning = false;
    } catch (e) {
        console.error(e);
    }
}

/* ================== MQTT ================== */
async function sendMQTT(topic, message) {
    const timestamp = new Date().toLocaleTimeString();
    try {
        console.log(`[${timestamp}] MQTT → Sending to '${topic}':`, message);
        const res = await fetch('/api/mqtt/publish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic, message })
        });
        const data = await res.json();
        if (data.status === 'success') {
            console.log(`[${timestamp}] MQTT → ✅ Published to '${topic}'`);
        } else {
            console.warn(`[${timestamp}] MQTT → ⚠️ Publish failed:`, data.message);
        }
    } catch (e) {
        console.error(`[${timestamp}] MQTT → ❌ Error publishing:`, e);
    }
}

async function pollMQTTMessages(topic) {
    try {
        const res = await fetch(`/api/mqtt/messages?topic=${encodeURIComponent(topic)}`);
        const data = await res.json();
        let msg = data.message;
        if (typeof msg === "object") msg = JSON.stringify(msg);
        if (msg) console.log(`[${new Date().toLocaleTimeString()}] MQTT ← ${topic}:`, msg);
        return msg;
    } catch (e) {
        console.error(e);
        return null;
    }
}

async function pollMQTTStatus() {
    try {
        const res = await fetch('/api/mqtt/status');
        const data = await res.json();
        const statusEl = document.querySelector('header .status');
        if (!statusEl) return;
        statusEl.innerHTML = data.data.connected
            ? '<i class="fas fa-circle" style="color:green;"></i> MQTT Online'
            : '<i class="fas fa-circle" style="color:red;"></i> MQTT Offline';
    } catch (e) {
        console.error(e);
    }
}

/* ================== Conveyor Ping ================== */
const pingIntervals = {};

async function pingConveyor(user) {
    const statusEl = document.getElementById(`status-${user}`);
    if (statusEl) statusEl.innerText = "PING...";

    try {
        const pingPayload = JSON.stringify({ action: "PING" });
        await sendMQTT(`/${user}/feeds/V1`, pingPayload);

        let timeout = false;
        const timeoutId = setTimeout(() => {
            timeout = true;
            if (statusEl) statusEl.innerText = "TIMEOUT";
            if (pingIntervals[user]) clearInterval(pingIntervals[user]);
        }, 5000);

        pingIntervals[user] = setInterval(async () => {
            if (timeout) return;
            const msg = await pollMQTTMessages(`/${user}/feeds/V2`);
            if (!msg) return;

            if (msg.includes("READY")) {
                clearTimeout(timeoutId);
                clearInterval(pingIntervals[user]);
                if (statusEl) statusEl.innerText = "READY";
            } else if (msg.includes("DONE")) {
                if (statusEl) statusEl.innerText = "DONE";
            }
        }, 500);

    } catch (e) {
        console.error(e);
        if (statusEl) statusEl.innerText = "ERROR";
    }
}

/* ================== Detections ================== */
let lastActionsSent = {};

async function pollDetections() {
    if (!cameraRunning) return;
    try {
        const res = await fetch('/api/camera/detections');
        const data = await res.json();
        const list = document.getElementById('detected-list');
        if (!list) return;

        // 1️⃣ Hiển thị danh sách object detect
        if (data.status === 'success' && Array.isArray(data.detections)) {
            list.innerHTML = data.detections.map(obj => {
                const color = obj.bgr ? `rgb(${obj.bgr[2]},${obj.bgr[1]},${obj.bgr[0]})` : '#888';
                const name = obj.name || 'unknown';
                const x = obj.x ?? 0, y = obj.y ?? 0, w = obj.w ?? 0, h = obj.h ?? 0;
                return `<li>
                    <span style="display:inline-block;width:12px;height:12px;margin-right:6px;border:1px solid #000;background:${color};"></span>
                    <b>${name}</b><br>
                    <small>(${x},${y}) ${w}×${h}</small>
                </li>`;
            }).join('');
        } else {
            list.innerHTML = `<li style="color:#888;">No objects detected</li>`;
        }

        // 2️⃣ Gửi action MQTT theo màu (với duration riêng)
        const user = document.getElementById('conveyor-select').value;
        const now = Date.now();

        // Thời gian hoạt động của từng màu
        const durationMap = {
            blue: 4000,
            green: 6000,
            red: 8000
        };

        // Ánh xạ màu sang ID hành động
        const colorMap = {
            blue: 1,
            green: 2,
            red: 3
        };

        if (data.status === 'success' && Array.isArray(data.detections)) {
            for (const obj of data.detections) {
                const name = (obj.name || '').toLowerCase();
                const action = colorMap[name] ?? null;
                const duration_ms = durationMap[name] ?? 10000;
                const cooldown = duration_ms + 500; // thêm 0.5s buffer

                if (action !== null) {
                    const key = `${user}_${action}`;
                    if (!lastActionsSent[key] || (now - lastActionsSent[key] > cooldown)) {
                        const topic = `${user}/feeds/V1`;
                        const payload = JSON.stringify({ action, duration_ms });
                        await sendMQTT(topic, payload);
                        lastActionsSent[key] = now;
                        console.log(`[${new Date().toLocaleTimeString()}] MQTT → Sent ${name} (${action}) duration=${duration_ms}ms`);
                    }
                }
            }
        }

    } catch (e) {
        console.error("[pollDetections] Error:", e);
    }
}

/* ================== Auto Poll ================== */
let mqttInterval = null, detectionInterval = null;

function startPolling() {
    if (!mqttInterval) mqttInterval = setInterval(pollMQTTStatus, 5000);
    if (!detectionInterval) detectionInterval = setInterval(pollDetections, 1000);
}

function stopPolling() {
    if (mqttInterval) clearInterval(mqttInterval);
    if (detectionInterval) clearInterval(detectionInterval);
    mqttInterval = detectionInterval = null;
}

/* Pause polling when tab inactive */
document.addEventListener('visibilitychange', () => {
    document.hidden ? stopPolling() : startPolling();
});

/* ================== Init ================== */
document.addEventListener('DOMContentLoaded', async () => {
    await startCamera();
    pollMQTTStatus();
    startPolling();
});
