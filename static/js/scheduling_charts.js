document.addEventListener("DOMContentLoaded", function () {
    const socket = io();

    
    const cpuCtx = document.getElementById("cpuChart")?.getContext("2d");
    const batteryCtx = document.getElementById("batteryChart")?.getContext("2d");
    const forecastCtx = document.getElementById("forecastChart")?.getContext("2d");

    window.cpuChart = cpuCtx && new Chart(cpuCtx, {
        type: 'doughnut',
        data: {
            labels: ["Used", "Idle"],
            datasets: [{ data: [0, 100], backgroundColor: ["#FF6384", "#E0E0E0"] }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "70%",
            plugins: { legend: { position: "bottom" } }
        }
    });

    window.batteryChart = batteryCtx && new Chart(batteryCtx, {
        type: 'doughnut',
        data: {
            labels: ["Battery", "Remaining"],
            datasets: [{ data: [0, 100], backgroundColor: ["#36A2EB", "#E0E0E0"] }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "70%",
            plugins: { legend: { position: "bottom" } }
        }
    });

    
    window.forecastChart = forecastCtx && new Chart(forecastCtx, {
        type: "doughnut",
        data: {
            labels: ["Forecast", "Remaining"],
            datasets: [{
                data: [0, 100], // start at 0% forecast
                backgroundColor: ["#FFCE56", "#E0E0E0"]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "75%",
            plugins: {
                legend: { display: false },
                title: { display: true, text: "Forecast: 0%" }
            }
        }
    });


    
    const tasksProgressDiv = document.getElementById("tasksProgress");
    const taskCharts = {}; 

    function createTaskCanvas(taskName) {
        const wrapper = document.createElement("div");
        wrapper.style.width = "110px";
        wrapper.style.height = "130px";
        wrapper.style.display = "flex";
        wrapper.style.flexDirection = "column";
        wrapper.style.alignItems = "center";
        wrapper.style.justifyContent = "center";
        wrapper.style.margin = "8px";

        const title = document.createElement("div");
        title.innerText = taskName;
        title.style.fontSize = "13px";
        title.style.marginBottom = "6px";
        title.style.fontWeight = "500";

        const canvas = document.createElement("canvas");
        canvas.id = `task_${taskName}`;
        canvas.width = 80;
        canvas.height = 80;

        wrapper.appendChild(title);
        wrapper.appendChild(canvas);
        tasksProgressDiv.appendChild(wrapper);

        return canvas;
    }

    
    document.getElementById("startSimulation")?.addEventListener("click", () => {
        const algo = document.getElementById("algorithm")?.value || "FCFS";
        console.log("✅ Start Simulation clicked with algorithm:", algo);
        socket.emit("start_scheduling", { algo });
    });

    
    socket.on("scheduling_update", (data) => {
        console.log("🔄 scheduling_update:", data);
    
        // Running & queue
        document.getElementById("running").innerText = data.running || "Idle";
        document.getElementById("queue").innerText = (data.queue || []).join(", ") || "-";
    
        
        if (data.cpu !== undefined && window.cpuChart) {
            const cpuVal = Number(data.cpu) || 0;
            window.cpuChart.data.datasets[0].data = [cpuVal, 100 - cpuVal];
            window.cpuChart.update();
        }
    
        
        if (data.battery !== undefined && window.batteryChart) {
            const battVal = Number(data.battery) || 0;
            window.batteryChart.data.datasets[0].data = [battVal, 100 - battVal];
            window.batteryChart.update();
        }
    
        
        if (window.forecastChart) {
            if (data.forecastPercent !== undefined) {
                const p = Math.max(0, Math.min(100, Number(data.forecastPercent)));
                window.forecastChart.data.datasets[0].data = [p, 100 - p];
            }
            if (data.forecastText !== undefined) {
                window.forecastChart.options.plugins.title.text = "Forecast: " + data.forecastText;
            }
            window.forecastChart.update();
        }


    
        
        if (data.currentAlgo) {
            document.getElementById("currentAlgo").innerText = data.currentAlgo;
        }
        if (data.batteryMode) {
            const bmEl = document.getElementById("batteryMode");
            bmEl.innerText = data.batteryMode;
            bmEl.classList.remove("text-success", "text-warning", "text-danger");
            if (data.batteryMode === "Normal") bmEl.classList.add("text-success");
            else if (data.batteryMode === "Low Power") bmEl.classList.add("text-warning");
            else if (data.batteryMode === "Critical") bmEl.classList.add("text-danger");
        }
        if (data.algoReason) {
            document.getElementById("algoReason").innerText = data.algoReason;
        }
    
        
        if (data.progress && typeof data.progress === "object") {
            Object.entries(data.progress).forEach(([taskName, percent]) => {
                const progress = Math.max(0, Math.min(100, Number(percent) || 0));
    
                if (!taskCharts[taskName]) {
                    const canvas = createTaskCanvas(taskName);
                    taskCharts[taskName] = new Chart(canvas.getContext("2d"), {
                        type: "doughnut",
                        data: {
                            labels: ["Completed", "Remaining"],
                            datasets: [{
                                data: [progress, 100 - progress],
                                backgroundColor: ["#4BC0C0", "#E0E0E0"]
                            }]
                        },
                        options: {
                            responsive: false,
                            maintainAspectRatio: false,
                            cutout: "75%",
                            animation: { duration: 400 },
                            plugins: { legend: { display: false } }
                        }
                    });
                } else {
                    const ch = taskCharts[taskName];
                    ch.data.datasets[0].data = [progress, 100 - progress];
                    ch.update();
    
                    if (progress >= 100) {
                        const canvas = document.getElementById(`task_${taskName}`);
                        if (canvas?.parentNode) canvas.parentNode.remove();
                        ch.destroy();
                        delete taskCharts[taskName];
                    }
                }
            });
        }
    });
    

    
    socket.on("connect", () => console.log("🔗 Socket connected:", socket.id));
    socket.on("disconnect", () => console.log("❌ Socket disconnected"));
});
