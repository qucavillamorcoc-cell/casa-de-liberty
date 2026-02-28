/**
 * Global Theme Manager - Handles dark mode synchronization across all pages
 * This script should be loaded early in the <head> to prevent theme flashing
 */

(function() {
    'use strict';

    // Theme constants
    const THEME_KEY = 'casa-de-liberty-theme';
    const DARK_MODE_CLASS = 'dark-mode';
    const LIGHT_MODE_CLASS = 'light-mode';
    const DEFAULT_THEME = 'dark';
    const TOGGLE_SELECTOR = [
        'input[type="checkbox"]#theme-toggle',
        'input[type="checkbox"]#darkModeToggle',
        'input[type="checkbox"]#darkModeCheckbox',
        'input[type="checkbox"][data-theme-toggle]'
    ].join(',');
    const THEME_TEXT_SELECTOR = [
        '#theme-text',
        '#theme-text-base',
        '[data-theme-text]'
    ].join(',');

    /**
     * Get the saved theme from localStorage or use default
     */
    function getSavedTheme() {
        return localStorage.getItem(THEME_KEY) || DEFAULT_THEME;
    }

    /**
     * Apply theme to the document
     */
    function applyTheme(theme) {
        const html = document.documentElement;
        
        if (theme === 'light') {
            html.classList.remove(DARK_MODE_CLASS);
            html.classList.add(LIGHT_MODE_CLASS);
        } else {
            html.classList.remove(LIGHT_MODE_CLASS);
            html.classList.add(DARK_MODE_CLASS);
        }
    }

    /**
     * Initialize theme on page load
     * Call this as early as possible to prevent theme flashing
     */
    function initializeTheme() {
        const savedTheme = getSavedTheme();
        applyTheme(savedTheme);
    }

    /**
     * Return all theme toggle checkbox elements in the current document.
     * Uses querySelectorAll so duplicated IDs (legacy markup) are still handled.
     */
    function getToggleElements() {
        return Array.from(document.querySelectorAll(TOGGLE_SELECTOR));
    }

    /**
     * Emit a single app-wide event when theme changes.
     */
    function emitThemeChanged(theme) {
        window.dispatchEvent(new CustomEvent('casa:theme-changed', {
            detail: { theme }
        }));
    }

    /**
     * Toggle dark/light mode and save preference
     */
    function toggleTheme() {
        const currentTheme = getSavedTheme();
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        localStorage.setItem(THEME_KEY, newTheme);
        applyTheme(newTheme);
        
        // Update all toggle checkboxes on the page
        updateAllToggles(newTheme);
        emitThemeChanged(newTheme);
        
        return newTheme;
    }

    /**
     * Set theme to a specific value
     */
    function setTheme(theme) {
        if (theme !== 'dark' && theme !== 'light') {
            console.warn('Invalid theme:', theme);
            return false;
        }
        
        localStorage.setItem(THEME_KEY, theme);
        applyTheme(theme);
        updateAllToggles(theme);
        emitThemeChanged(theme);
        
        return true;
    }

    /**
     * Get current theme
     */
    function getCurrentTheme() {
        return getSavedTheme();
    }

    /**
     * Update all toggle switches to match current theme
     */
    function updateAllToggles(theme) {
        // For checkboxes in this app: checked = light mode
        getToggleElements().forEach(toggle => {
            toggle.checked = (theme === 'light');
        });

        const labelText = theme === 'light' ? 'Light' : 'Dark';
        document.querySelectorAll(THEME_TEXT_SELECTOR).forEach(textElement => {
            textElement.textContent = labelText;
        });
    }

    /**
     * Setup event listeners for theme toggles
     * Call this after DOM is ready
     */
    function setupThemeListeners() {
        getToggleElements().forEach(toggle => {
            if (toggle.dataset.themeBound === '1') {
                return;
            }
            toggle.addEventListener('change', handleToggleChange);
            toggle.dataset.themeBound = '1';
        });
    }

    /**
     * Handle theme toggle change event
     */
    function handleToggleChange(e) {
        const isChecked = e.target.checked;
        const newTheme = isChecked ? 'light' : 'dark';
        setTheme(newTheme);
    }

    /**
     * Listen for storage changes (from other tabs/windows)
     */
    function setupStorageListener() {
        window.addEventListener('storage', function(e) {
            if (e.key === THEME_KEY) {
                const newTheme = e.newValue || DEFAULT_THEME;
                applyTheme(newTheme);
                updateAllToggles(newTheme);
            }
        });
    }

    // Initialize theme immediately (before page renders)
    initializeTheme();

    // Expose theme functions globally
    window.ThemeManager = {
        toggle: toggleTheme,
        set: setTheme,
        get: getCurrentTheme,
        updateToggles: updateAllToggles
    };

    // Setup listeners when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            updateAllToggles(getCurrentTheme());
            setupThemeListeners();
            setupStorageListener();
        });
    } else {
        updateAllToggles(getCurrentTheme());
        setupThemeListeners();
        setupStorageListener();
    }
})();
