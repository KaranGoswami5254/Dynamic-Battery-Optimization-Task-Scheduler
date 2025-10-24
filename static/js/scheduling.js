document.addEventListener("DOMContentLoaded", () => {
    console.log("Scheduling.js loaded ✅");

    const socket = io("/");

    const startBtn = document.getElementById("startSimulation");
    const runningProcess = document.getElementById("running");
    const readyQueue = document.getElementById("queue");
    const algoBox = document.getElementById("currentAlgorithm");
    const runningTaskSpan = document.getElementById("runningTask");

    // Process Chart
    const processCtx = document.getElementById("processChart")?.getContext("2d");
    const processChart = new Chart(processCtx, {
        type: "line",
        data: { 
            labels: [], 
            datasets: [{ 
                label: "CPU Execution Timeline", 
                data: [], 
                borderColor: "#00c8ff", 
                backgroundColor: "rgba(0,200,255,0.2)", 
                tension: 0.3, 
                fill: true 
            }] 
        },
        options: { 
            responsive: true, 
            scales: { 
                x: { title: { display: true, text: "Time (s)" } }, 
                y: { 
                    title: { display: true, text: "Process ID" }, 
                    min: 0 
                } 
            } 
        }
    });

    // --- Battery Impact Chart (Simplified Doughnut) ---
    const batteryCtx = document.getElementById("batteryImpactChart")?.getContext("2d");
    let batteryImpactChart = null;

    if (batteryCtx) {
        batteryImpactChart = new Chart(batteryCtx, {
            type: 'doughnut',
            data: {
                labels: ["FCFS", "Round Robin", "SJF", "SRTF", "Priority Scheduling"],
                datasets: [{
                    label: 'Battery Impact (%)',
                    data: [25, 30, 20, 35, 40],
                    backgroundColor: [
                        '#36A2EB',
                        '#FFCE56',
                        '#4BC0C0',
                        '#9966FF',
                        '#FF9F40'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                cutout: '70%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { font: { size: 12 } }
                    },
                    title: {
                        display: true,
                        text: 'Algorithm Battery Impact',
                        font: { size: 16, weight: 'bold' }
                    }
                }
            }
        });
    }

    // Track current algorithm
    let currentAlgorithm = "None";

    // Dynamic update function
    function updateAlgorithmsBatteryImpact(algorithmData, currentAlgo) {
        if (!batteryImpactChart || !algorithmData) return;

        const labels = batteryImpactChart.data.labels;
        const newData = labels.map(label => algorithmData[label] || 0);
        const newColors = labels.map(label => label === currentAlgo ? '#FF6384' : batteryImpactChart.data.datasets[0].backgroundColor[labels.indexOf(label)]);

        batteryImpactChart.data.datasets[0].data = newData;
        batteryImpactChart.data.datasets[0].backgroundColor = newColors;

        batteryImpactChart.options.plugins.title.text = currentAlgo ? `Running: ${currentAlgo}` : 'Algorithm Battery Impact';
        batteryImpactChart.update();
    }

    // Function to simulate dynamic battery changes
    function simulateDynamicBatteryChanges() {
        if (!batteryImpactChart || currentAlgorithm === "None") return;

        const labels = batteryImpactChart.data.labels;
        const updatedData = {};

        labels.forEach(label => {
            const currentValue = batteryImpactChart.data.datasets[0].data[labels.indexOf(label)];
            let newValue = currentValue + (Math.random() > 0.5 ? 1 : -1) * (Math.random() * 5 + 2);
            updatedData[label] = Math.max(10, Math.min(90, Math.round(newValue)));
        });

        updateAlgorithmsBatteryImpact(updatedData, currentAlgorithm);
    }

    // Scheduling Simulation Function
    function simulateScheduling(algorithm) {
        let time = 0;
        let timeline = [];
        const processes = [
            { pid: 1, burst: 5, priority: 2 },
            { pid: 2, burst: 3, priority: 1 },
            { pid: 3, burst: 8, priority: 3 }
        ];
        let queue = [...processes];

        const baseImpacts = {
            "fcfs": { "FCFS": 45, "Round Robin": 60, "SJF": 35, "SRTF": 70, "Priority Scheduling": 80 },
            "round_robin": { "FCFS": 35, "Round Robin": 75, "SJF": 30, "SRTF": 55, "Priority Scheduling": 65 },
            "priority": { "FCFS": 30, "Round Robin": 50, "SJF": 25, "SRTF": 60, "Priority Scheduling": 85 }
        };

        const algoNames = { "fcfs": "FCFS", "round_robin": "Round Robin", "priority": "Priority Scheduling" };
        const currentAlgoName = algoNames[algorithm] || algorithm;

        const dynamicInterval = setInterval(simulateDynamicBatteryChanges, 2000);

        if (algorithm === "fcfs") {
            queue.forEach(p => { for (let i = 0; i < p.burst; i++) timeline.push({ time: time++, pid: p.pid }); });
        } else if (algorithm === "round_robin") {
            const quantum = 2;
            while (queue.length > 0) {
                let p = queue.shift();
                let runTime = Math.min(quantum, p.burst);
                for (let i = 0; i < runTime; i++) timeline.push({ time: time++, pid: p.pid });
                p.burst -= runTime;
                if (p.burst > 0) queue.push(p);
            }
        } else if (algorithm === "priority") {
            queue.sort((a, b) => a.priority - b.priority);
            queue.forEach(p => { for (let i = 0; i < p.burst; i++) timeline.push({ time: time++, pid: p.pid }); });
        }

        processChart.data.labels = timeline.map(e => e.time);
        processChart.data.datasets[0].data = timeline.map(e => e.pid);
        processChart.update();

        updateAlgorithmsBatteryImpact(baseImpacts[algorithm], currentAlgoName);

        let index = 0;
        const interval = setInterval(() => {
            if (index >= timeline.length) {
                runningProcess.textContent = "None";
                readyQueue.textContent = "[]";
                runningTaskSpan.textContent = "None";
                clearInterval(interval);
                clearInterval(dynamicInterval);
                return;
            }

            const current = timeline[index];
            runningProcess.textContent = `P${current.pid}`;
            const upcoming = timeline.slice(index + 1, index + 4).map(e => "P" + e.pid);
            readyQueue.textContent = `[${upcoming.join(", ")}]`;
            runningTaskSpan.textContent = `Task ${current.pid}`;

            index++;
        }, 1000);
    }

    // Start Simulation
    startBtn?.addEventListener("click", () => {
        const algo = document.getElementById("algorithmSelect")?.value || "fcfs";
        simulateScheduling(algo);
        socket.emit("start_simulation", { algorithm: algo });
    });

    // Socket event handlers
    socket.on("update_algorithm", (data) => {
        if (!data) return;
        if (data.algorithm) {
            algoBox.textContent = data.algorithm;
            currentAlgorithm = data.algorithm;
            algoBox.className = "fw-bold " + (data.algorithm.includes("Round Robin") ? "text-warning" : 
                                             data.algorithm.includes("Priority") ? "text-danger" : 
                                             data.algorithm.includes("SRTF") ? "text-info" : "text-primary");
        }
    });

    socket.on("battery_algo_impact", (data) => {
        if (!data || !data.battery_used) return;
        updateAlgorithmsBatteryImpact(data.battery_used, currentAlgorithm);
    });

    socket.on("battery_algo_impact_init", (data) => {
        if (data && data.battery_used) {
            updateAlgorithmsBatteryImpact(data.battery_used, data.algorithm);
        }
    });

    socket.on("update_running", (data) => { runningProcess.textContent = data.running || "Idle"; });
    socket.on("update_queue", (data) => { readyQueue.textContent = data.queue?.length > 0 ? data.queue.join(", ") : "-"; });

    socket.emit("request_algorithm");
});
