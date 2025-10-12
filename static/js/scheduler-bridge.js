// SCHEDULER DATA BRIDGE - Add this to your main project
class SchedulerDataBridge {
    constructor() {
        this.currentSimulationData = null;
        this.analyticsReady = false;
        this.init();
    }

    init() {
        // Listen for analytics page load
        window.addEventListener('schedulerAnalyticsReady', () => {
            this.analyticsReady = true;
            if (this.currentSimulationData) {
                this.sendToAnalytics(this.currentSimulationData);
            }
        });
    }

    // Call this when simulation completes
    updateFromSimulation(simulationResults) {
        console.log('📊 Simulation completed, processing data...', simulationResults);
        
        const analyticsData = this.formatForAnalytics(simulationResults);
        this.currentSimulationData = analyticsData;
        
        if (this.analyticsReady) {
            this.sendToAnalytics(analyticsData);
        } else {
            console.log('Analytics not ready, data stored for later');
        }
        
        return analyticsData;
    }

    // Call this for real-time OS data
    updateFromRealSystem(realTimeMetrics) {
        const analyticsData = {
            baseline: realTimeMetrics.baseline || this.getDefaultBaseline(),
            optimized: realTimeMetrics.current,
            metadata: {
                simulationDate: new Date().toISOString(),
                workloadType: 'Real System',
                dataType: 'real-time'
            }
        };
        
        this.sendToAnalytics(analyticsData);
    }

    formatForAnalytics(simResults) {
        // Adjust these property names to match your simulation output
        return {
            baseline: {
                throughput: simResults.baseline?.throughput || simResults.baseline?.tasksPerSecond || 0,
                responseTime: simResults.baseline?.avgResponseTime || simResults.baseline?.responseTime || 0,
                waitTime: simResults.baseline?.avgWaitTime || simResults.baseline?.waitingTime || 0,
                cpuUtilization: simResults.baseline?.cpuUsage || simResults.baseline?.cpuUtilization || 0,
                contextSwitches: simResults.baseline?.contextSwitches || simResults.baseline?.switches || 0,
                turnaroundTime: simResults.baseline?.avgTurnaroundTime || simResults.baseline?.turnaroundTime || 0,
                tasksCompleted: simResults.baseline?.tasksCompleted || simResults.baseline?.completedTasks || 0
            },
            optimized: {
                throughput: simResults.optimized?.throughput || simResults.optimized?.tasksPerSecond || 0,
                responseTime: simResults.optimized?.avgResponseTime || simResults.optimized?.responseTime || 0,
                waitTime: simResults.optimized?.avgWaitTime || simResults.optimized?.waitingTime || 0,
                cpuUtilization: simResults.optimized?.cpuUsage || simResults.optimized?.cpuUtilization || 0,
                contextSwitches: simResults.optimized?.contextSwitches || simResults.optimized?.switches || 0,
                turnaroundTime: simResults.optimized?.avgTurnaroundTime || simResults.optimized?.turnaroundTime || 0,
                tasksCompleted: simResults.optimized?.tasksCompleted || simResults.optimized?.completedTasks || 0
            },
            metadata: {
                simulationDate: new Date().toISOString(),
                workloadType: simResults.workloadType || 'Custom Workload',
                totalTasks: simResults.totalTasks || 1000,
                schedulerType: simResults.schedulerType || 'Optimized Scheduler'
            }
        };
    }

    sendToAnalytics(data) {
        if (window.schedulerAnalytics && window.schedulerAnalytics.loadReportData) {
            window.schedulerAnalytics.loadReportData(data);
            console.log('✅ Data sent to analytics page', data);
        } else {
            console.warn('❌ Analytics component not available');
        }
    }

    getDefaultBaseline() {
        return {
            throughput: 85,
            responseTime: 45,
            waitTime: 30,
            cpuUtilization: 78,
            contextSwitches: 1200,
            turnaroundTime: 75,
            tasksCompleted: 1000
        };
    }
}

// Initialize global instance
window.schedulerBridge = new SchedulerDataBridge();