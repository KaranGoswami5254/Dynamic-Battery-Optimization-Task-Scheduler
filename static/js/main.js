
var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);


var batteryCtx = document.getElementById('batteryChart').getContext('2d');
var cpuCtx = document.getElementById('cpuChart').getContext('2d');
var tempCtx = document.getElementById('tempChart').getContext('2d');

var batteryChart = new Chart(batteryCtx, {
    type: 'doughnut',
    data: { labels: ['Battery', 'Empty'], datasets: [{ data: [0, 100], backgroundColor: ['#28a745', '#e9ecef'] }] },
    options: { responsive: true, plugins: { legend: { display: false } }, cutout: "70%" }
});

var cpuChart = new Chart(cpuCtx, {
    type: 'doughnut',
    data: { labels: ['CPU', 'Idle'], datasets: [{ data: [0, 100], backgroundColor: ['#ffc107', '#e9ecef'] }] },
    options: { responsive: true, plugins: { legend: { display: false } }, cutout: "70%" }
});

var tempChart = new Chart(tempCtx, {
    type: 'doughnut',
    data: { labels: ['Temp', 'Safe'], datasets: [{ data: [0, 100], backgroundColor: ['#dc3545', '#e9ecef'] }] },
    options: { responsive: true, plugins: { legend: { display: false } }, cutout: "70%" }
});


socket.on('connect', function() {
    console.log('Connected to server');
});


socket.on('scheduling_update', function(data) {
    updateSystemMetrics(data);
});


socket.on('temperature_update', function(data) {
    if (data && data.temperature !== undefined) {
        updateTemperature(data.temperature);
    }
});


socket.on('task_update', function(task) {
    updateTaskTable(task);
});


socket.on('log_update', function(log) {
    updateLogTable(log);
});


function updateSystemMetrics(data) {
    if (!data) return;

    
    if (data.battery !== undefined) {
        batteryChart.data.datasets[0].data[0] = data.battery;
        batteryChart.data.datasets[0].data[1] = 100 - data.battery;
        batteryChart.update();
        let batteryProgress = document.getElementById('batteryProgress');
        if (batteryProgress) {
            batteryProgress.style.width = data.battery + '%';
            batteryProgress.className = 'progress-bar ' + (data.battery < 20 ? 'bg-danger' : 'bg-success');
        }
        let batteryStatus = document.getElementById('batteryStatus');
        if (batteryStatus) batteryStatus.innerText = `Battery: ${data.battery}%`;
    }

    
    if (data.cpu !== undefined) {
        cpuChart.data.datasets[0].data[0] = data.cpu;
        cpuChart.data.datasets[0].data[1] = 100 - data.cpu;
        cpuChart.update();
        let cpuProgress = document.getElementById('cpuProgress');
        if (cpuProgress) {
            cpuProgress.style.width = data.cpu + '%';
            cpuProgress.className = 'progress-bar ' + (data.cpu > 80 ? 'bg-danger' : 'bg-warning');
        }
        let cpuStatus = document.getElementById('cpuStatus');
        if (cpuStatus) cpuStatus.innerText = `CPU Usage: ${data.cpu}%`;
    }

    
    if (data.temperature !== undefined) {
        updateTemperature(data.temperature);
    }
}

function updateTemperature(temperature) {
    if (temperature === undefined || temperature === null) return;

    const tempValue = Math.min(temperature, 100);
    tempChart.data.datasets[0].data[0] = tempValue;
    tempChart.data.datasets[0].data[1] = 100 - tempValue;
    tempChart.update();

    let tempProgress = document.getElementById('tempProgress');
    if (tempProgress) {
        tempProgress.style.width = tempValue + '%';
        tempProgress.className = 'progress-bar ' + (temperature > 70 ? 'bg-danger' : 'bg-info');
    }

    let tempStatus = document.getElementById('tempStatus');
    if (tempStatus) tempStatus.innerText = `Temp: ${temperature}°C`;
}


function populateInitialTasks(tasks) {
    const taskTableBody = document.querySelector('#taskTable tbody');
    if (!taskTableBody) return;
    taskTableBody.innerHTML = '';
    tasks.forEach(task => {
        const row = document.createElement('tr');
        row.setAttribute('id', `task-${task.id}`);
        row.innerHTML = `<td>${task.name}</td><td>${task.priority}</td><td>${task.status}</td>`;
        taskTableBody.appendChild(row);
    });
}

function populateInitialLogs(logs) {
    const logsTableBody = document.querySelector('#logsTable tbody');
    if (!logsTableBody) return;
    logsTableBody.innerHTML = '';
    logs.forEach(log => {
        const row = document.createElement('tr');
        row.setAttribute('id', `log-${log.id}`);
        row.innerHTML = `<td>${log.timestamp}</td><td>${log.decision || log.outcome || log.message}</td>`;
        logsTableBody.appendChild(row);
    });
}

function updateTaskTable(task) {
    const taskTableBody = document.querySelector('#taskTable tbody');
    if (!taskTableBody) return;
    let row = document.getElementById(`task-${task.id}`);
    if (!row) {
        row = document.createElement('tr');
        row.setAttribute('id', `task-${task.id}`);
        taskTableBody.appendChild(row);
    }
    row.innerHTML = `<td>${task.name}</td><td>${task.priority}</td><td>${task.status}</td>`;
}

function updateLogTable(log) {
    const logsTableBody = document.querySelector('#logsTable tbody');
    if (!logsTableBody) return;

    const row = document.createElement('tr');
    row.innerHTML = `
        <td>${log.timestamp || ''}</td>
        <td>
            Task ${log.task_id || ''}: ${log.decision || ''} |
            CPU: ${log.cpu || 0}% |
            Battery: ${log.battery || 0}% |
            Outcome: ${log.outcome || log.message || ''}
        </td>
    `;
    logsTableBody.prepend(row); // newest on top
}



document.addEventListener('DOMContentLoaded', function() {
    console.log('System monitor initialized');

    if (window.initialTasks) populateInitialTasks(window.initialTasks);
    if (window.initialLogs) populateInitialLogs(window.initialLogs);
});
