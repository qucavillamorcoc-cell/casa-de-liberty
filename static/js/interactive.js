/**
 * Interactive.js - Handles common interactive elements across the application
 * Includes: dark mode toggling, hover effects, form interactions
 * Note: Dark mode is now handled by global ThemeManager (theme.js)
 */

// ================================
// Dark Mode Toggle Functionality (Legacy - uses global ThemeManager)
// ================================

function initializeDarkModeToggle() {
    const darkModeCheckbox = document.getElementById('darkModeCheckbox');
    
    if (!darkModeCheckbox) return; // Exit if element not found
    
    // Use global ThemeManager if available, otherwise set up manually
    if (typeof window.ThemeManager !== 'undefined') {
        // Global theme manager is active, just ensure toggle is synced
        const currentTheme = window.ThemeManager.get();
        darkModeCheckbox.checked = (currentTheme === 'light');
        
        // Add change listener that uses global theme manager
        darkModeCheckbox.addEventListener('change', function() {
            const newTheme = this.checked ? 'light' : 'dark';
            window.ThemeManager.set(newTheme);
        });
    }
}

// ================================
// Hover Effects for Buttons & Cards
// ================================

function initializeHoverEffects() {
    // Stat cards with transform effect
    const statCards = document.querySelectorAll('[data-hover-effect="card"]');
    statCards.forEach(card => {
        const transformY = card.dataset.transformY || '-6px';
        const shadowColor = card.dataset.shadowColor || 'rgba(59, 130, 246, 0.2)';
        const borderColor = card.dataset.borderColor || '#3b82f6';
        
        card.addEventListener('mouseenter', function() {
            // Special slide effect for calendar event items
            if (shadowColor === 'none') {
                this.style.transform = 'translateX(8px)';
                const bgMatch = this.style.backgroundColor.match(/rgba?\([\d,.\s]+\)/);
                if (bgMatch) {
                    const bgColor = bgMatch[0];
                    const newBg = bgColor.replace('0.15)', '0.25)');
                    this.style.backgroundColor = newBg;
                }
            } else {
                this.style.transform = `translateY(${transformY})`;
                this.style.boxShadow = `0 16px 32px ${shadowColor}`;
                if (this.style.border) {
                    this.style.borderColor = borderColor;
                }
            }
        });
        
        card.addEventListener('mouseleave', function() {
            // Reset calendar event items
            if (shadowColor === 'none') {
                this.style.transform = 'translateX(0)';
                const bgMatch = this.style.backgroundColor.match(/rgba?\([\d,.\s]+\)/);
                if (bgMatch) {
                    const bgColor = bgMatch[0];
                    const newBg = bgColor.replace('0.25)', '0.15)');
                    this.style.backgroundColor = newBg;
                }
            } else {
                this.style.transform = 'translateY(0)';
                this.style.boxShadow = '';
                if (this.style.border) {
                    this.style.borderColor = 'transparent';
                }
            }
        });
    });
    
    // Buttons with hover effects
    const hoverButtons = document.querySelectorAll('[data-hover-effect="button"]');
    hoverButtons.forEach(button => {
        const shadowColor = button.dataset.shadowColor || 'rgba(16, 185, 129, 0.3)';
        const transform = button.dataset.transform || 'translateY(-2px)';
        
        button.addEventListener('mouseenter', function() {
            this.style.boxShadow = `0 8px 24px ${shadowColor}`;
            this.style.transform = transform;
        });
        
        button.addEventListener('mouseleave', function() {
            this.style.boxShadow = 'none';
            this.style.transform = 'translateY(0)';
        });
    });
}

// ================================
// Initialize on DOM Ready
// ================================

document.addEventListener('DOMContentLoaded', function() {
    initializeDarkModeToggle();
    initializeHoverEffects();
});
