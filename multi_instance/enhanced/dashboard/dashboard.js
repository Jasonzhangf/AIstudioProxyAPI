// Dashboard functionality

// Load data from API
async function loadData() {
  try {
    // Get health data
    const healthResponse = await fetch('/api/multi-instance/health');
    const healthData = await healthResponse.json();
    
    // Get instances data
    const instancesResponse = await fetch('/api/multi-instance/instances');
    const instancesData = await instancesResponse.json();
    
    // Update UI
    updateStatusCards(healthData);
    updateInstanceCards(instancesData);
  } catch (error) {
    console.error('Failed to load data:', error);
    showError('Failed to load data. Please try again.');
  }
}

// Update status cards
function updateStatusCards(data) {
  const statusGrid = document.getElementById('statusGrid');
  
  // Extract data
  const instanceManager = data.instance_manager || {};
  const requestRouter = data.request_router || {};
  const errorRecovery = data.error_recovery || {};
  
  // Create HTML
  statusGrid.innerHTML = `
    <div class="status-card">
      <h3>Total Instances</h3>
      <div class="status-value">${instanceManager.total_instances || 0}</div>
      <div class="status-label">Total configured instances</div>
    </div>
    <div class="status-card">
      <h3>Available Instances</h3>
      <div class="status-value">${instanceManager.available_instances || 0}</div>
      <div class="status-label">Instances ready to process requests</div>
    </div>
    <div class="status-card">
      <h3>Active Requests</h3>
      <div class="status-value">${requestRouter.active_requests || 0}</div>
      <div class="status-label">Currently processing requests</div>
    </div>
    <div class="status-card">
      <h3>Success Rate</h3>
      <div class="status-value">${(requestRouter.success_rate || 0).toFixed(1)}%</div>
      <div class="status-label">Request success rate</div>
    </div>
    <div class="status-card">
      <h3>Active Errors</h3>
      <div class="status-value">${errorRecovery.active_errors || 0}</div>
      <div class="status-label">Errors requiring attention</div>
    </div>
    <div class="status-card">
      <h3>System Status</h3>
      <div class="status-value">${data.status || 'unknown'}</div>
      <div class="status-label">Overall system health</div>
    </div>
  `;
}

// Update instance cards
function updateInstanceCards(data) {
  const instancesGrid = document.getElementById('instancesGrid');
  const instances = data.instances || {};
  
  // Check if there are instances
  if (Object.keys(instances).length === 0) {
    instancesGrid.innerHTML = `
      <div class="instance-card">
        <div class="instance-header">
          <span class="instance-id">No instances found</span>
        </div>
        <p>No instances are currently configured.</p>
      </div>
    `;
    return;
  }
  
  // Create HTML for each instance
  let html = '';
  for (const [instanceId, instanceData] of Object.entries(instances)) {
    const config = instanceData.config || {};
    const health = instanceData.health || {};
    
    // Determine status class
    let statusClass = 'status-warning';
    if (health.healthy) {
      statusClass = 'status-healthy';
    } else if (health.status === 'error') {
      statusClass = 'status-unhealthy';
    }
    
    html += `
      <div class="instance-card">
        <div class="instance-header">
          <span class="instance-id">${instanceId}</span>
          <span class="status-badge ${statusClass}">${health.status || 'unknown'}</span>
        </div>
        <div class="instance-info">
          <div><strong>Email:</strong> ${config.auth_profile?.email || 'unknown'}</div>
          <div><strong>Port:</strong> ${config.port || 'unknown'}</div>
          <div><strong>Launch Mode:</strong> ${config.launch_mode || 'unknown'}</div>
          <div><strong>Active Requests:</strong> ${health.active_requests || 0}/${config.max_concurrent_requests || 1}</div>
          <div><strong>Error Count:</strong> ${config.error_count || 0}</div>
        </div>
        <div class="instance-actions">
          <button class="btn btn-primary" onclick="controlInstance('${instanceId}', 'start')">Start</button>
          <button class="btn btn-danger" onclick="controlInstance('${instanceId}', 'stop')">Stop</button>
          <button class="btn btn-warning" onclick="controlInstance('${instanceId}', 'restart')">Restart</button>
        </div>
      </div>
    `;
  }
  
  instancesGrid.innerHTML = html;
}

// Control instance
async function controlInstance(instanceId, action) {
  try {
    const response = await fetch(`/api/multi-instance/instances/${instanceId}/${action}`, {
      method: 'POST'
    });
    
    const data = await response.json();
    
    if (data.success) {
      showMessage(data.message);
      loadData();
    } else {
      showError(`Failed: ${data.message || 'Unknown error'}`);
    }
  } catch (error) {
    showError(`Error: ${error.message}`);
  }
}

// Show message
function showMessage(message) {
  const messageElement = document.getElementById('message');
  messageElement.textContent = message;
  messageElement.className = 'message message-success';
  messageElement.style.display = 'block';
  
  setTimeout(() => {
    messageElement.style.display = 'none';
  }, 3000);
}

// Show error
function showError(message) {
  const messageElement = document.getElementById('message');
  messageElement.textContent = message;
  messageElement.className = 'message message-error';
  messageElement.style.display = 'block';
  
  setTimeout(() => {
    messageElement.style.display = 'none';
  }, 5000);
}

// Load data on page load
document.addEventListener('DOMContentLoaded', () => {
  loadData();
  
  // Refresh data every 30 seconds
  setInterval(loadData, 30000);
});