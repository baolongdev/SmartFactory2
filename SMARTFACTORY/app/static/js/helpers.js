/* ================= HELPERS ================= */

// API BASES
export const CAMERA_API_BASE = "/api/camera";
export const MQTT_API_BASE = "/api/mqtt";
export const COLOR_API_BASE = "/api/colors";   // <<--- THÊM MỚI

// MQTT FEEDS (phù hợp config_mqtt.json)
export const CMD_FEED = "V1";
export const STATUS_FEED = "V2";

/**
 * Build topic: user/feeds/feed
 */
export function buildFeedTopic(user, feed) {
    return `${user}/feeds/${feed}`;
}

/**
 * Lấy user (conveyor) đang chọn
 */
export function getSelectedUser() {
    const sel = document.getElementById("conveyor-select");
    return sel ? sel.value : null;
}
