import { sendMQTT, pollMQTTMessages } from "./mqtt.js";
import { buildFeedTopic, CMD_FEED, STATUS_FEED } from "./helpers.js";

const pingIntervals = {};

export async function pingConveyor(user) {
    setConveyorStatus(user, "PING...");

    await sendMQTT(buildFeedTopic(user, CMD_FEED), JSON.stringify({ action: "PING" }));

    let timeout = false;
    const timeoutId = setTimeout(() => {
        timeout = true;
        setConveyorStatus(user, "TIMEOUT");
        clearInterval(pingIntervals[user]);
    }, 5000);

    pingIntervals[user] = setInterval(async () => {
        if (timeout) return;

        const msg = await pollMQTTMessages(buildFeedTopic(user, STATUS_FEED));
        if (!msg) return;

        // convert msg thành string trước khi xử lý
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

export function setConveyorStatus(user, status) {
    const el = document.getElementById(`status-${user}`);
    el.textContent = status;
    el.classList.remove("conv-ready", "conv-timeout");

    if (status === "READY") el.classList.add("conv-ready");
    if (status === "TIMEOUT") el.classList.add("conv-timeout");
}
