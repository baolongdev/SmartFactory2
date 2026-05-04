import { sendMQTT, pollMQTTMessages } from "./mqtt.js";
import { buildFeedTopic, CMD_FEED, STATUS_FEED } from "./helpers.js";

const pingIntervals = {};

/**
 * Ping conveyor to check status
 * Updates workflow step 4 (Conveyor Control)
 * @param {string} user - Conveyor user (e.g., "0_SmartConvey2025")
 */
export async function pingConveyor(user) {
    setConveyorStatus(user, "PING...");

    // Update workflow: Step 4 active
    if (window.updateWorkflowStep) {
        window.updateWorkflowStep(4);
    }

    await sendMQTT(buildFeedTopic(user, CMD_FEED), JSON.stringify({ action: "PING" }));

    let timeout = false;
    const timeoutId = setTimeout(() => {
        timeout = true;
        setConveyorStatus(user, "TIMEOUT");
        clearInterval(pingIntervals[user]);

        // Update workflow: Step 4 failed
        if (window.updateWorkflowStep) {
            window.updateWorkflowStep(4, false);
        }
    }, 5000);

    pingIntervals[user] = setInterval(async () => {
        if (timeout) return;

        const msg = await pollMQTTMessages(buildFeedTopic(user, STATUS_FEED));
        if (!msg) return;

        // Convert msg to string for processing
        const text = typeof msg === "string" ? msg : JSON.stringify(msg);

        if (text.includes("READY")) {
            clearTimeout(timeoutId);
            clearInterval(pingIntervals[user]);
            setConveyorStatus(user, "READY");

            // Update workflow: Step 4 completed
            if (window.updateWorkflowStep) {
                window.updateWorkflowStep(4, true);
            }
        }

        if (text.includes("DONE")) {
            setConveyorStatus(user, "DONE");
        }
    }, 500);
}

/**
 * Update conveyor status display
 * @param {string} user - Conveyor user
 * @param {string} status - Status text
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
