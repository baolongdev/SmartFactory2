import { sendUART, readUART } from "./uart.js";

/**
 * Test băng tải: gửi 1 (chạy) → chờ phản hồi READY → gửi 0 (dừng sau 3s).
 * @param {string} user - conveyor identifier (dùng cho UI element IDs)
 */
export async function pingConveyor(user) {
    setConveyorStatus(user, "PING...");

    // Gửi 1 để kiểm tra kết nối
    await sendUART(1);

    let timeout = false;
    const timeoutId = setTimeout(async () => {
        timeout = true;
        await sendUART(0);   // dừng nếu timeout
        setConveyorStatus(user, "TIMEOUT");
        clearInterval(pollId);
    }, 5000);

    // Poll readUART() mỗi 500ms chờ phản hồi từ thiết bị
    const pollId = setInterval(async () => {
        if (timeout) return;
        const msg = await readUART();
        if (!msg) return;
        const text = typeof msg === "string" ? msg : JSON.stringify(msg);
        if (text.includes("READY")) {
            clearTimeout(timeoutId);
            clearInterval(pollId);
            setConveyorStatus(user, "READY");
            // Dừng băng tải sau 3s
            setTimeout(() => sendUART(0), 3000);
        }
        if (text.includes("DONE")) {
            setConveyorStatus(user, "DONE");
        }
    }, 500);
}

/**
 * Cập nhật ô trạng thái băng tải.
 * @param {string} user
 * @param {string} status - "READY" | "TIMEOUT" | "PING..." | "DONE"
 */
export function setConveyorStatus(user, status) {
    const el = document.getElementById(`status-${user}`);
    if (!el) return;
    el.textContent = status;
    el.classList.remove("bg-green-500", "bg-red-500", "bg-yellow-500", "text-white");
    if (status === "READY") {
        el.classList.add("bg-green-600", "text-white");
    } else if (status === "TIMEOUT") {
        el.classList.add("bg-red-500", "text-white");
    } else if (status === "PING...") {
        el.classList.add("bg-yellow-500", "text-white");
    } else {
        el.classList.add("border-2", "border-gray-900");
    }
}
