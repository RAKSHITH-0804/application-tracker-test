// global states
let allApplications = [];
let activeFilter = 'all';
let searchQuery = '';

// API Fetch Helper with automatic token refresh on 401
async function apiFetch(url, options = {}) {
    let response = await fetch(url, options);
    
    if (response.status === 401) {
        // Access token might be expired. Try to refresh.
        try {
            const refreshResponse = await fetch('/auth/refresh', { method: 'POST' });
            if (refreshResponse.ok) {
                // Retry the original request
                response = await fetch(url, options);
            } else {
                // Refresh token expired or invalid, redirect to login
                window.location.href = '/login';
                return null;
            }
        } catch (err) {
            window.location.href = '/login';
            return null;
        }
    }
    return response;
}

// Initial setup on page load
document.addEventListener('DOMContentLoaded', () => {
    // Check if on login or signup pages
    const path = window.location.pathname;
    if (path === '/login' || path === '/signup') return;
    
    // Auth & Load data
    loadUserInfo();
    loadApplications();
    
    // Set up form submission
    document.getElementById('application-form').addEventListener('submit', handleFormSubmit);
    
    // Cancel Edit Button
    document.getElementById('cancel-edit-btn').addEventListener('click', abortEdit);
    
    // Search Box Listener
    document.getElementById('search-input').addEventListener('input', (e) => {
        searchQuery = e.target.value.toLowerCase().trim();
        renderApplications();
    });
    
    // Filter Chips Listeners
    const chips = document.querySelectorAll('.chip');
    chips.forEach(chip => {
        chip.addEventListener('click', (e) => {
            chips.forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            activeFilter = chip.getAttribute('data-filter');
            renderApplications();
        });
    });
    
    // Logout Button
    document.getElementById('logout-btn').addEventListener('click', handleLogout);
});

// Load authenticated User Info
async function loadUserInfo() {
    try {
        const response = await apiFetch('/auth/me');
        if (response && response.ok) {
            const data = await response.json();
            document.getElementById('user-display').innerText = `USER: ${data.email}`;
        } else {
            document.getElementById('user-display').innerText = 'USER: ACTIVE';
        }
    } catch (err) {
        document.getElementById('user-display').innerText = 'USER: ACTIVE';
    }
}

// Fetch all applications
async function loadApplications() {
    try {
        const response = await apiFetch('/applications');
        if (!response) return;
        
        if (response.ok) {
            allApplications = await response.json();
            updateStats();
            renderApplications();
        } else {
            console.error('Failed to load applications');
        }
    } catch (err) {
        console.error('Network error loading applications:', err);
    }
}

// Update stats board counters
function updateStats() {
    const counts = { wishlist: 0, applied: 0, interview: 0, offer: 0, rejected: 0 };
    allApplications.forEach(app => {
        if (counts[app.status] !== undefined) {
            counts[app.status]++;
        }
    });
    
    document.getElementById('stat-wishlist').innerText = counts.wishlist;
    document.getElementById('stat-applied').innerText = counts.applied;
    document.getElementById('stat-interview').innerText = counts.interview;
    document.getElementById('stat-offer').innerText = counts.offer;
    document.getElementById('stat-rejected').innerText = counts.rejected;
}

// Render filtered applications in the list container
function renderApplications() {
    const container = document.getElementById('cases-container');
    container.innerHTML = '';
    
    // Apply filters
    const filtered = allApplications.filter(app => {
        const matchesFilter = activeFilter === 'all' || app.status === activeFilter;
        const matchesSearch = searchQuery === '' || 
            app.company.toLowerCase().includes(searchQuery) || 
            (app.role && app.role.toLowerCase().includes(searchQuery)) ||
            (app.notes && app.notes.toLowerCase().includes(searchQuery));
        return matchesFilter && matchesSearch;
    });
    
    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="dossier-card empty-card">
                <p>No job applications matching search criteria.</p>
            </div>
        `;
        return;
    }
    
    filtered.forEach(app => {
        const card = document.createElement('div');
        card.className = 'dossier-card case-item';
        card.setAttribute('data-status', app.status);
        
        const dateString = app.date_applied ? app.date_applied : 'N/A';
        const linkHtml = app.link ? `<a href="${app.link}" target="_blank" class="dossier-link">Open Link &gt;&gt;</a>` : 'N/A';
        
        card.innerHTML = `
            <div class="case-header-row">
                <div class="case-title-area">
                    <h3>${app.company}</h3>
                    <span class="case-role">${app.role || 'ROLE: UNSPECIFIED'}</span>
                </div>
                <div class="stamp-badge">${app.status}</div>
            </div>
            
            <div class="case-details-row">
                <div class="case-meta">DATE APPLIED: <span>${dateString}</span></div>
                <div class="case-meta">REFERENCE LINK: <span>${linkHtml}</span></div>
                ${app.notes ? `<div class="case-notes-block">${app.notes}</div>` : ''}
            </div>
            
            <div class="case-actions">
                <button class="action-btn" onclick="startEdit(${app.id})">EDIT RECORD</button>
                <button class="action-btn delete" onclick="deleteCase(${app.id})">DELETE</button>
            </div>
        `;
        
        container.appendChild(card);
    });
}

// Handle Form Submit: Create or Update Application
async function handleFormSubmit(e) {
    e.preventDefault();
    
    const id = document.getElementById('app-id').value;
    const company = document.getElementById('company').value;
    const role = document.getElementById('role').value;
    const status = document.getElementById('status').value;
    const dateApplied = document.getElementById('date_applied').value || null;
    const link = document.getElementById('link').value || null;
    const notes = document.getElementById('notes').value || null;
    
    const payload = {
        company,
        role,
        status,
        date_applied: dateApplied,
        link,
        notes
    };
    
    const isEdit = !!id;
    const url = isEdit ? `/applications/${id}` : '/applications';
    const method = isEdit ? 'PUT' : 'POST';
    
    try {
        const response = await apiFetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (response && response.ok) {
            abortEdit(); // reset form
            loadApplications(); // reload list
        } else {
            alert('Failed to save record.');
        }
    } catch (err) {
        console.error('Error saving record:', err);
    }
}

// Start Edit Mode: Load data into form
window.startEdit = function(id) {
    const app = allApplications.find(a => a.id === id);
    if (!app) return;
    
    document.getElementById('app-id').value = app.id;
    document.getElementById('company').value = app.company;
    document.getElementById('role').value = app.role || '';
    document.getElementById('status').value = app.status;
    document.getElementById('date_applied').value = app.date_applied || '';
    document.getElementById('link').value = app.link || '';
    document.getElementById('notes').value = app.notes || '';
    
    // Update labels and buttons
    document.getElementById('form-tab-title').innerText = 'EDIT APPLICATION';
    document.getElementById('form-header').innerText = `RECORD #${app.id}`;
    document.getElementById('submit-btn').innerText = 'UPDATE RECORD';
    document.getElementById('cancel-edit-btn').classList.remove('hidden');
    
    // Scroll form into view
    document.getElementById('application-form').scrollIntoView({ behavior: 'smooth' });
}

// Abort/Reset Edit Mode
window.abortEdit = function() {
    document.getElementById('app-id').value = '';
    document.getElementById('application-form').reset();
    
    document.getElementById('form-tab-title').innerText = 'ADD APPLICATION';
    document.getElementById('form-header').innerText = 'NEW RECORD';
    document.getElementById('submit-btn').innerText = 'SAVE RECORD';
    document.getElementById('cancel-edit-btn').classList.add('hidden');
}

// Delete application entry
window.deleteCase = async function(id) {
    if (!confirm('Are you sure you want to delete this job record?')) return;
    
    try {
        const response = await apiFetch(`/applications/${id}`, {
            method: 'DELETE'
        });
        
        if (response && response.ok) {
            loadApplications();
        } else {
            alert('Failed to delete application.');
        }
    } catch (err) {
        console.error('Error deleting application:', err);
    }
}

// Handle secure logout
async function handleLogout() {
    try {
        const response = await fetch('/auth/logout', { method: 'POST' });
        if (response.ok) {
            window.location.href = '/login';
        } else {
            alert('Logout failed.');
        }
    } catch (err) {
        console.error('Error logging out:', err);
    }
}
