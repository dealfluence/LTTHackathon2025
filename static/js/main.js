// Main JavaScript for Legal Contract Analysis Bot

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // File upload validation
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            validateFileUpload(e.target);
        });
    });
    
    // Auto-hide alerts
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    });
});

function validateFileUpload(fileInput) {
    const file = fileInput.files[0];
    const maxSize = 50 * 1024 * 1024; // 50MB in bytes
    const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'];
    
    if (file) {
        // Check file size
        if (file.size > maxSize) {
            showAlert('File size exceeds 50MB limit. Please choose a smaller file.', 'danger');
            fileInput.value = '';
            return false;
        }
        
        // Check file type
        if (!allowedTypes.includes(file.type)) {
            showAlert('Unsupported file type. Please upload PDF, DOCX, or TXT files only.', 'danger');
            fileInput.value = '';
            return false;
        }
        
        // Show file info
        const fileInfo = `Selected: ${file.name} (${formatFileSize(file.size)})`;
        const fileInfoEl = fileInput.parentNode.querySelector('.file-info');
        if (fileInfoEl) {
            fileInfoEl.textContent = fileInfo;
        } else {
            const infoDiv = document.createElement('div');
            infoDiv.className = 'file-info text-muted mt-1';
            infoDiv.textContent = fileInfo;
            fileInput.parentNode.appendChild(infoDiv);
        }
    }
    
    return true;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alert-container') || createAlertContainer();
    
    const alertEl = document.createElement('div');
    alertEl.className = `alert alert-${type} alert-dismissible fade show`;
    alertEl.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    alertContainer.appendChild(alertEl);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        const bsAlert = new bootstrap.Alert(alertEl);
        if (bsAlert) {
            bsAlert.close();
        }
    }, 5000);
}

function createAlertContainer() {
    const container = document.createElement('div');
    container.id = 'alert-container';
    container.className = 'position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1050';
    document.body.appendChild(container);
    return container;
}

// Utility function to format dates
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

// Utility function to copy text to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showAlert('Copied to clipboard!', 'success');
    }).catch(() => {
        showAlert('Failed to copy to clipboard', 'danger');
    });
}

// Enhanced form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    let isValid = true;
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// Loading state management
function setLoadingState(element, loading = true) {
    if (loading) {
        element.classList.add('loading');
        element.disabled = true;
        
        // Add spinner if it's a button
        if (element.tagName === 'BUTTON') {
            const spinner = document.createElement('span');
            spinner.className = 'spinner-border spinner-border-sm me-2';
            spinner.id = 'loading-spinner';
            element.insertBefore(spinner, element.firstChild);
        }
    } else {
        element.classList.remove('loading');
        element.disabled = false;
        
        // Remove spinner
        const spinner = element.querySelector('#loading-spinner');
        if (spinner) {
            spinner.remove();
        }
    }
}

// Table sorting functionality
function sortTable(tableId, columnIndex, dataType = 'string') {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
        const aText = a.cells[columnIndex].textContent.trim();
        const bText = b.cells[columnIndex].textContent.trim();
        
        if (dataType === 'date') {
            return new Date(aText) - new Date(bText);
        } else if (dataType === 'number') {
            return parseFloat(aText) - parseFloat(bText);
        } else {
            return aText.localeCompare(bText);
        }
    });
    
    // Clear tbody and append sorted rows
    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
}

// Export functionality
function exportAnalysis(analysisId, format = 'json') {
    fetch(`/api/analysis/${analysisId}`)
        .then(response => response.json())
        .then(data => {
            let content, filename, mimeType;
            
            if (format === 'json') {
                content = JSON.stringify(data, null, 2);
                filename = `analysis_${analysisId}.json`;
                mimeType = 'application/json';
            } else if (format === 'txt') {
                content = `Contract Analysis Report\n\n${data.summary || 'No summary available'}`;
                filename = `analysis_${analysisId}.txt`;
                mimeType = 'text/plain';
            }
            
            const blob = new Blob([content], { type: mimeType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        })
        .catch(error => {
            showAlert('Failed to export analysis: ' + error.message, 'danger');
        });
}