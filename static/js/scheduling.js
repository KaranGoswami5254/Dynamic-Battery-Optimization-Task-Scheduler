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

    // Battery Impact Chart - Dynamic Doughnut
    const batteryCtx = document.getElementById("batteryImpactChart")?.getContext("2d");
    let batteryImpactChart = null;

    // Algorithm colors (no borders)
    const algorithmColors = {
        "FCFS": { normal: "rgba(54, 162, 235, 0.8)", highlight: "rgba(255, 99, 132, 0.9)" },
        "Round Robin": { normal: "rgba(255, 206, 86, 0.8)", highlight: "rgba(255, 99, 132, 0.9)" },
        "SJF": { normal: "rgba(75, 192, 192, 0.8)", highlight: "rgba(255, 99, 132, 0.9)" },
        "SRTF": { normal: "rgba(153, 102, 255, 0.8)", highlight: "rgba(255, 99, 132, 0.9)" },
        "Priority Scheduling": { normal: "rgba(255, 159, 64, 0.8)", highlight: "rgba(255, 99, 132, 0.9)" }
    };

    // Initialize battery chart as doughnut
    if (batteryCtx) {
        batteryImpactChart = new Chart(batteryCtx, {
            type: 'doughnut',
            data: {
                labels: ["FCFS", "Round Robin", "SJF", "SRTF", "Priority Scheduling"],
                datasets: [{
                    label: 'Battery Impact',
                    data: [25, 30, 20, 35, 40],
                    backgroundColor: [
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 206, 86, 0.8)', 
                        'rgba(75, 192, 192, 0.8)',
                        'rgba(153, 102, 255, 0.8)',
                        'rgba(255, 159, 64, 0.8)'
                    ],
                    borderWidth: 0, // No borders
                    hoverOffset: 20,
                    borderRadius: 5,
                    spacing: 2
                }]
            },
            options: {
                responsive: true,
                cutout: '65%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#ffffff',
                            font: {
                                size: 12
                            },
                            padding: 20,
                            usePointStyle: true,
                            pointStyle: 'circle'
                        }
                    },
                    tooltip: {
                        enabled: true,
                        callbacks: {
                            label: function(context) {
                                return `${context.label}: ${context.parsed}% battery impact`;
                            }
                        }
                    },
                    title: {
                        display: true,
                        text: 'Algorithm Battery Impact Comparison',
                        color: '#ffffff',
                        font: {
                            size: 16,
                            weight: 'bold'
                        },
                        padding: {
                            bottom: 20
                        }
                    }
                },
                animation: {
                    animateScale: true,
                    animateRotate: true,
                    duration: 1000,
                    easing: 'easeOutQuart'
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
    }

    // Track current algorithm and animation state
    let currentAlgorithm = "None";
    let isAnimating = false;

    // Dynamic update function with smooth transitions
    function updateAlgorithmsBatteryImpact(algorithmData, currentAlgo) {
        if (!batteryImpactChart || !algorithmData || isAnimating) return;
        
        isAnimating = true;
        currentAlgorithm = currentAlgo;
        
        // Get current data for smooth transition
        const currentData = batteryImpactChart.data.datasets[0].data;
        const labels = batteryImpactChart.data.labels;
        const newData = [];
        const newBackgroundColors = [];
        
        // Prepare new data with smooth transitions
        labels.forEach((label, index) => {
            const targetImpact = algorithmData[label] || 0;
            const currentImpact = currentData[index] || 0;
            
            // Store target value
            newData.push(targetImpact);
            
            // Highlight current algorithm
            if (label === currentAlgo) {
                newBackgroundColors.push(algorithmColors[label]?.highlight || 'rgba(255, 99, 132, 0.9)');
            } else {
                newBackgroundColors.push(algorithmColors[label]?.normal || 'rgba(54, 162, 235, 0.8)');
            }
        });
        
        // Update chart data
        batteryImpactChart.data.datasets[0].data = newData;
        batteryImpactChart.data.datasets[0].backgroundColor = newBackgroundColors;
        
        // Update title dynamically
        if (currentAlgo && currentAlgo !== "None") {
            batteryImpactChart.options.plugins.title.text = `Running: ${currentAlgo}`;
        } else {
            batteryImpactChart.options.plugins.title.text = 'Select Algorithm to Start';
        }
        
        // Smooth update
        batteryImpactChart.update('active');
        
        // Reset animation flag after update completes
        setTimeout(() => {
            isAnimating = false;
        }, 1000);
    }

    // Function to simulate dynamic battery impact changes
    function simulateDynamicBatteryChanges() {
        if (!batteryImpactChart || currentAlgorithm === "None") return;
        
        const labels = batteryImpactChart.data.labels;
        const currentData = {...batteryImpactChart.data.datasets[0].data};
        const updatedData = {};
        
        labels.forEach(label => {
            const currentValue = batteryImpactChart.data.datasets[0].data[labels.indexOf(label)];
            let newValue = currentValue;
            
            // Add some random variation (±2-8%)
            const variation = Math.random() * 6 + 2;
            const direction = Math.random() > 0.5 ? 1 : -1;
            
            newValue += direction * variation;
            
            // Keep within reasonable bounds
            newValue = Math.max(10, Math.min(90, newValue));
            
            updatedData[label] = Math.round(newValue);
        });
        
        updateAlgorithmsBatteryImpact(updatedData, currentAlgorithm);
    }

    // Simulation function with dynamic updates
    function simulateScheduling(algorithm) {
        let time = 0;
        let timeline = [];
        const processes = [
            { pid: 1, burst: 5, priority: 2 },
            { pid: 2, burst: 3, priority: 1 },
            { pid: 3, burst: 8, priority: 3 },
        ];
        let queue = [...processes];

        // Dynamic algorithm battery impacts
        const baseImpacts = {
            "fcfs": { 
                "FCFS": 45, 
                "Round Robin": 60, 
                "SJF": 35, 
                "SRTF": 70, 
                "Priority Scheduling": 80 
            },
            "round_robin": { 
                "FCFS": 35, 
                "Round Robin": 75, 
                "SJF": 30, 
                "SRTF": 55, 
                "Priority Scheduling": 65 
            },
            "priority": { 
                "FCFS": 30, 
                "Round Robin": 50, 
                "SJF": 25, 
                "SRTF": 60, 
                "Priority Scheduling": 85 
            }
        };

        // Get current algorithm name for display
        const algoNames = {
            "fcfs": "FCFS",
            "round_robin": "Round Robin", 
            "priority": "Priority Scheduling"
        };

        const currentAlgoName = algoNames[algorithm] || algorithm;

        // Start dynamic updates interval
        const dynamicInterval = setInterval(simulateDynamicBatteryChanges, 2000);

        if (algorithm === "fcfs") {
            queue.forEach(p => { 
                for (let i = 0; i < p.burst; i++) timeline.push({ time: time++, pid: p.pid }); 
            });
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
            queue.forEach(p => { 
                for (let i = 0; i < p.burst; i++) timeline.push({ time: time++, pid: p.pid }); 
            });
        }

        // Update process chart
        processChart.data.labels = timeline.map(e => e.time);
        processChart.data.datasets[0].data = timeline.map(e => e.pid);
        processChart.update();

        // Update battery impact for simulation
        updateAlgorithmsBatteryImpact(baseImpacts[algorithm], currentAlgoName);

        let index = 0;
        const interval = setInterval(() => {
            if (index >= timeline.length) {
                runningProcess.textContent = "None";
                readyQueue.textContent = "[]";
                runningTaskSpan.textContent = "None";
                clearInterval(interval);
                clearInterval(dynamicInterval); // Stop dynamic updates
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

    // Start simulation
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
            
            // Color code by algorithm
            if (data.algorithm.includes("Round Robin")) algoBox.className = "text-warning fw-bold";
            else if (data.algorithm.includes("Priority")) algoBox.className = "text-danger fw-bold";
            else if (data.algorithm.includes("SRTF")) algoBox.className = "text-info fw-bold";
            else algoBox.className = "text-primary fw-bold";
        }
    });

    socket.on("battery_algo_impact", (data) => {
        if (!data || !data.battery_used) return;
        
        // Update all algorithms' battery impact and highlight current one
        updateAlgorithmsBatteryImpact(data.battery_used, currentAlgorithm);
    });

    socket.on("battery_algo_impact_init", (data) => {
        if (data && data.battery_used) {
            updateAlgorithmsBatteryImpact(data.battery_used, data.algorithm);
        }
    });

    socket.on("update_running", (data) => { 
        runningProcess.textContent = data.running || "Idle"; 
    });
    
    socket.on("update_queue", (data) => { 
        readyQueue.textContent = data.queue?.length > 0 ? data.queue.join(", ") : "-"; 
    });

    // Request initial algorithm
    socket.emit("request_algorithm");
});