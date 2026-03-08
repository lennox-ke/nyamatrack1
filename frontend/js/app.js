/**
 * NyamaTrack - Main Application JavaScript
 * Shared utilities and API configuration
 */

// API Configuration - Change this to your Render backend URL after deployment
const API_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:8000/api' 
    : 'https://nyamatrack-api.onrender.com/api';

// Authentication Utilities
const Auth = {
    getToken() {
        return localStorage.getItem('access_token');
    },
    
    getRefreshToken() {
        return localStorage.getItem('refresh_token');
    },
    
    setTokens(access, refresh) {
        localStorage.setItem('access_token', access);
        localStorage.setItem('refresh_token', refresh);
    },
    
    clearTokens() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('username');
    },
    
    isAuthenticated() {
        return !!this.getToken();
    },
    
    async refreshAccessToken() {
        const refresh = this.getRefreshToken();
        if (!refresh) {
            this.logout();
            return false;
        }
        
        try {
            const response = await fetch(`${API_URL}/token/refresh/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh })
            });
            
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('access_token', data.access);
                return true;
            } else {
                this.logout();
                return false;
            }
        } catch (error) {
            this.logout();
            return false;
        }
    },
    
    logout() {
        this.clearTokens();
        window.location.href = 'login.html';
    },
    
    getAuthHeaders() {
        return {
            'Authorization': `Bearer ${this.getToken()}`,
            'Content-Type': 'application/json'
        };
    }
};

// API Request Wrapper with automatic token refresh
async function apiRequest(endpoint, options = {}) {
    const url = `${API_URL}${endpoint}`;
    
    // Add auth header if not provided
    if (!options.headers) {
        options.headers = Auth.getAuthHeaders();
    }
    
    try {
        let response = await fetch(url, options);
        
        // If token expired, try to refresh
        if (response.status === 401) {
            const refreshed = await Auth.refreshAccessToken();
            if (refreshed) {
                // Retry with new token
                options.headers = Auth.getAuthHeaders();
                response = await fetch(url, options);
            } else {
                throw new Error('Authentication failed');
            }
        }
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || error.error || 'Request failed');
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// Toast Notification System
const Toast = {
    container: null,
    
    init() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            this.container.id = 'toastContainer';
            document.body.appendChild(this.container);
        }
    },
    
    show(message, type = 'success', duration = 3000) {
        this.init();
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = type === 'success' ? 'check-circle' : 
                    type === 'error' ? 'exclamation-circle' : 
                    type === 'warning' ? 'exclamation-triangle' : 'info-circle';
        
        toast.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <span>${message}</span>
        `;
        
        this.container.appendChild(toast);
        
        // Animate in
        requestAnimationFrame(() => {
            toast.style.animation = 'slideInRight 0.3s ease-out';
        });
        
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },
    
    success(message) {
        this.show(message, 'success');
    },
    
    error(message) {
        this.show(message, 'error');
    },
    
    warning(message) {
        this.show(message, 'warning');
    },
    
    info(message) {
        this.show(message, 'info');
    }
};

// Form Validation Utilities
const Validation = {
    isEmpty(value) {
        return !value || value.trim() === '';
    },
    
    isPositiveNumber(value) {
        const num = parseFloat(value);
        return !isNaN(num) && num > 0;
    },
    
    isEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    },
    
    validateForm(formData, rules) {
        const errors = {};
        
        for (const [field, validators] of Object.entries(rules)) {
            const value = formData.get(field) || formData[field];
            
            for (const validator of validators) {
                const result = validator(value, field);
                if (result !== true) {
                    errors[field] = result;
                    break;
                }
            }
        }
        
        return Object.keys(errors).length === 0 ? null : errors;
    }
};

// Common Validators
const Validators = {
    required(message = 'This field is required') {
        return (value) => !Validation.isEmpty(value) || message;
    },
    
    email(message = 'Please enter a valid email') {
        return (value) => Validation.isEmail(value) || message;
    },
    
    minLength(min, message) {
        return (value) => {
            if (!message) message = `Must be at least ${min} characters`;
            return (value && value.length >= min) || message;
        };
    },
    
    positiveNumber(message = 'Must be a positive number') {
        return (value) => Validation.isPositiveNumber(value) || message;
    }
};

// Date Utilities
const DateUtils = {
    formatDate(dateString) {
        return new Date(dateString).toLocaleDateString('en-KE', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    },
    
    formatDateTime(dateString) {
        return new Date(dateString).toLocaleString('en-KE', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    getToday() {
        return new Date().toISOString().split('T')[0];
    },
    
    getNow() {
        return new Date().toISOString().slice(0, 16);
    },
    
    daysBetween(date1, date2) {
        const d1 = new Date(date1);
        const d2 = new Date(date2);
        return Math.floor((d2 - d1) / (1000 * 60 * 60 * 24));
    }
};

// Number Formatting (Kenyan Shilling)
const Currency = {
    format(amount) {
        return `KES ${parseFloat(amount).toFixed(2)}`;
    },
    
    formatWeight(kg) {
        return `${parseFloat(kg).toFixed(2)} kg`;
    }
};

// Loading State Management
const Loading = {
    show(element, message = 'Loading...') {
        element.disabled = true;
        element.dataset.originalText = element.innerHTML;
        element.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${message}`;
    },
    
    hide(element) {
        element.disabled = false;
        element.innerHTML = element.dataset.originalText || element.innerHTML;
    }
};
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const hamburger = document.getElementById('hamburgerBtn');
    
    sidebar.classList.toggle('open');
    overlay.classList.toggle('show');
    hamburger.classList.toggle('active');
}

function setActiveNav(element) {
    document.querySelectorAll('.mobile-nav-item').forEach(item => {
        item.classList.remove('active');
    });
    element.classList.add('active');
}

// Set active based on current page
document.addEventListener('DOMContentLoaded', () => {
    const currentPage = window.location.pathname.split('/').pop();
    document.querySelectorAll('.mobile-nav-item').forEach(item => {
        if (item.getAttribute('href') === currentPage) {
            item.classList.add('active');
        }
    });
});
// Sidebar Navigation Active State
function setActiveNavItem() {
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        const href = item.getAttribute('href');
        if (href === currentPage) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

// Mobile Sidebar Toggle
function initMobileSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const toggleBtn = document.createElement('button');
    toggleBtn.className = 'mobile-toggle';
    toggleBtn.innerHTML = '<i class="fas fa-bars"></i>';
    toggleBtn.style.cssText = `
        position: fixed;
        top: 20px;
        left: 20px;
        z-index: 1000;
        background: var(--primary);
        color: white;
        border: none;
        padding: 12px;
        border-radius: 8px;
        cursor: pointer;
        display: none;
    `;
    
    document.body.appendChild(toggleBtn);
    
    toggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('open');
    });
    
    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 1024 && 
            !sidebar.contains(e.target) && 
            !toggleBtn.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    });
    
    // Show toggle on mobile
    const mediaQuery = window.matchMedia('(max-width: 1024px)');
    const handleMediaChange = (e) => {
        toggleBtn.style.display = e.matches ? 'block' : 'none';
    };
    mediaQuery.addListener(handleMediaChange);
    handleMediaChange(mediaQuery);
}

// Initialize Common Features
document.addEventListener('DOMContentLoaded', () => {
    setActiveNavItem();
    initMobileSidebar();
    
    // Check authentication on protected pages
    const protectedPages = ['dashboard.html', 'stock-entry.html', 'sales.html', 'reports.html', 'users.html'];
    const currentPage = window.location.pathname.split('/').pop();
    
    if (protectedPages.includes(currentPage) && !Auth.isAuthenticated()) {
        window.location.href = 'login.html';
    }
    
    // Redirect to dashboard if already logged in on login page
    if (currentPage === 'login.html' && Auth.isAuthenticated()) {
        window.location.href = 'dashboard.html';
    }
});

// Export for use in other scripts
window.NyamaTrack = {
    API_URL,
    Auth,
    apiRequest,
    Toast,
    Validation,
    Validators,
    DateUtils,
    Currency,
    Loading
};