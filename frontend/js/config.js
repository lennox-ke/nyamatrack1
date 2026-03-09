/**
 * NyamaTrack Configuration
 * Update these values after deployment
 */

const CONFIG = {
    // Development
    DEV_API_URL: 'http://localhost:8000/api',
    
    // Production - Update this after deploying to Render
    PROD_API_URL: 'https://nyamatrack1.onrender.com/api',
    
    // Get current API URL based on environment
    get API_URL() {
        return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
            ? this.DEV_API_URL
            : this.PROD_API_URL;
    },
    
    // App Info
    APP_NAME: 'NyamaTrack',
    APP_VERSION: '1.0.0',
    DEFAULT_LANGUAGE: 'en',
    
    // Features
    ENABLE_OFFLINE_MODE: true,
    ENABLE_NOTIFICATIONS: true,
    
    // Stock Thresholds
    DEFAULT_LOW_STOCK_THRESHOLD: 5.0,
    DEFAULT_SPOILAGE_DAYS: 3,
    
    // Pagination
    ITEMS_PER_PAGE: 20
};

// Make globally available
window.CONFIG = CONFIG;