// AXILEX Electrician Management System - Frontend Interactions

// Auto-hide alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            const bsAlert = new bootstrap.Alert(alert);
            setTimeout(() => bsAlert.close(), 3000);
        });
    }, 3000);
});

// Job status update function
function updateJobStatus(jobId, status) {
    fetch(`/update_job_status/${jobId}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({status: status})
    })
    .then(response => response.json())
    .then(data => {
        if(data.success) location.reload();
    });
}

// Task progress update function
function updateTaskProgress(taskId, progress) {
    fetch(`/update_task_progress/${taskId}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({progress: progress})
    })
    .then(response => response.json())
    .then(data => {
        if(data.success) location.reload();
    });
}

// Format date for display
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
}