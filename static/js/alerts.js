// alert.js

let lastChargerStatus = null;   // Track last plugged/unplugged state
let lowBatteryAlerted = false;  // Track low battery alert state
let lastBatteryPercent = null;  // Track last battery percentage to avoid duplicate alerts

// Connect to backend
const socket = io("/");

socket.on("connect", () => {
    console.log("✅ Connected to backend for alerts");
});

// Listen to battery/system updates from backend
socket.on("scheduling_update", (data) => {
    if (!data) return;

    const battery = data.battery;
    const plugged = data.plugged !== undefined ? data.plugged : null;

    // --- Charger plug/unplug alerts ---
    if (plugged !== null && plugged !== lastChargerStatus) {
        if (plugged) {
            showNotification("🔌 Charger Connected", "Your laptop is now charging.");
            playSound("charger_in.mp3");
        } else {
            showNotification("⚡ Charger Disconnected", "Laptop is now on battery.");
            playSound("charger_out.mp3");
        }
        lastChargerStatus = plugged;
    }

    // --- Low battery alerts ---
    if (battery !== null) {
        if (battery <= 20 && (!plugged || plugged === false) && !lowBatteryAlerted) {
            showNotification("🔋 Low Battery", `Battery at ${battery}%. Please connect charger.`);
            playSound("low_battery.mp3");
            lowBatteryAlerted = true;
        } else if (battery > 20 && lowBatteryAlerted) {
            lowBatteryAlerted = false; // Reset alert state
        }

        // Avoid duplicate notifications if battery hasn't changed
        if (lastBatteryPercent !== battery) {
            lastBatteryPercent = battery;
        }
    }
});

// --- Desktop notification helper ---
function showNotification(title, message) {
    if (Notification.permission === "granted") {
        new Notification(title, { body: message });
    } else if (Notification.permission !== "denied") {
        Notification.requestPermission().then(permission => {
            if (permission === "granted") {
                new Notification(title, { body: message });
            }
        });
    }
}

// --- Play custom sound ---
function playSound(fileName) {
    const audio = new Audio(`/static/sounds/${fileName}`);
    audio.play().catch(err => console.warn("⚠️ Audio play blocked:", err));
}

// Ask for notification permission once on load
if (Notification.permission !== "granted") {
    Notification.requestPermission();
}
