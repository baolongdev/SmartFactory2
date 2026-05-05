import { sendUART, readUART } from "./uart.js";

const pingIntervals = {};

/**
 * Ping conveyor over UART to check status.
 * Sends {"action":"PING"} and polls readUART() for a READY response.
 * @param {string} user - conveyor identifier (used only for UI element IDs)
 */
export async function pingConveyor(user) {
    setConveyorStatus(user, "PING...");

    await sendUART({ action: "PING" });

    let timeout = false;
    const timeoutId = setTimeout(() => {
        timeout = true;
        setConveyorStatus(user, "TIMEOUT");
        clearInterval(pingIntervals[user]);
    }, 5000);

    pingIntervals[user] = setInterval(async () => {
        if (timeout) return;

        const msg = await readUART();
        if (!msg) return;

        const text = typeof msg === "string" ? msg : JSON.stringify(msg);

        if (text.includes("READY")) {
            clearTimeout(timeoutId);
            clearInterval(pingIntervals[user]);
            setConveyorStatus(user, "READY");
        }

        if (text.includes("DONE")) {
            setConveyorStatus(user, "DONE");
        }
    }, 500);
}

/**
 * Update conveyor status display.
 * @param {string} user - conveyor identifier
 * @param {string} status - "READY" | "TIMEOUT" | "PING..." | "DONE" | "--"
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
