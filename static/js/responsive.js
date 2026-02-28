/**
 * RESPONSIVE DESIGN - Mobile & Tablet Enhancements
 * Handles hamburger menu, touch events, and screen adaptation
 */

document.addEventListener('DOMContentLoaded', function() {
    // ============================================
    // MOBILE SIDEBAR TOGGLE
    // ============================================
    const mobileToggle = document.querySelector('.mobile-toggle');
    const sidebar = document.querySelector('.sidebar');
    const sidebarOverlay = document.querySelector('.sidebar-overlay');
    
    if (mobileToggle && sidebar) {
        // Toggle sidebar on hamburger click
        mobileToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            sidebar.classList.toggle('mobile-open');
            if (sidebarOverlay) {
                sidebarOverlay.classList.toggle('open');
            }
        });
        
        // Close sidebar when clicking overlay
        if (sidebarOverlay) {
            sidebarOverlay.addEventListener('click', function() {
                sidebar.classList.remove('mobile-open');
                sidebarOverlay.classList.remove('open');
            });
        }
        
        // Close sidebar when clicking on a link
        const sidebarLinks = sidebar.querySelectorAll('a');
        sidebarLinks.forEach(link => {
            link.addEventListener('click', function() {
                sidebar.classList.remove('mobile-open');
                if (sidebarOverlay) {
                    sidebarOverlay.classList.remove('open');
                }
            });
        });
        
        // Close sidebar on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                sidebar.classList.remove('mobile-open');
                if (sidebarOverlay) {
                    sidebarOverlay.classList.remove('open');
                }
            }
        });
    }
    
    // ============================================
    // DETECT DEVICE TYPE
    // ============================================
    function getDeviceType() {
        const width = window.innerWidth;
        if (width <= 480) return 'mobile';
        if (width <= 768) return 'tablet';
        if (width <= 1024) return 'desktop';
        return 'large-desktop';
    }
    
    // Add device class to body for CSS targeting
    function updateDeviceClass() {
        document.body.classList.remove('device-mobile', 'device-tablet', 'device-desktop', 'device-large-desktop');
        document.body.classList.add('device-' + getDeviceType());
    }
    
    // Update on load and window resize
    updateDeviceClass();
    window.addEventListener('resize', updateDeviceClass);
    
    // ============================================
    // TOUCH EVENT HANDLING
    // ============================================
    let touchStartX = 0;
    let touchEndX = 0;
    
    // Detect swipe gestures for mobile sidebar
    const mainContent = document.querySelector('.main-content') || document.body;
    
    mainContent.addEventListener('touchstart', function(e) {
        touchStartX = e.changedTouches[0].screenX;
    }, false);
    
    mainContent.addEventListener('touchend', function(e) {
        touchEndX = e.changedTouches[0].screenX;
        handleSwipe();
    }, false);
    
    function handleSwipe() {
        // Swipe right to open sidebar
        if (touchEndX - touchStartX > 50) {
            if (sidebar && getDeviceType() === 'mobile') {
                sidebar.classList.add('mobile-open');
                if (sidebarOverlay) {
                    sidebarOverlay.classList.add('open');
                }
            }
        }
        // Swipe left to close sidebar
        else if (touchStartX - touchEndX > 50) {
            if (sidebar) {
                sidebar.classList.remove('mobile-open');
                if (sidebarOverlay) {
                    sidebarOverlay.classList.remove('open');
                }
            }
        }
    }
    
    // ============================================
    // RESPONSIVE TABLE HANDLING
    // ============================================
    function makeTablesResponsive() {
        const tables = document.querySelectorAll('table');
        tables.forEach(table => {
            if (getDeviceType() === 'mobile') {
                // Store header text for mobile display
                const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent.trim());
                const rows = table.querySelectorAll('tbody tr');
                
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    cells.forEach((cell, index) => {
                        if (headers[index]) {
                            cell.setAttribute('data-header', headers[index]);
                        }
                    });
                });
            }
        });
    }
    
    makeTablesResponsive();
    window.addEventListener('resize', makeTablesResponsive);
    
    // ============================================
    // RESPONSIVE IMAGE LOADING
    // ============================================
    function optimizeImages() {
        const images = document.querySelectorAll('img[data-src]');
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.getAttribute('data-src');
                    img.removeAttribute('data-src');
                    observer.unobserve(img);
                }
            });
        });
        
        images.forEach(img => imageObserver.observe(img));
    }
    
    if ('IntersectionObserver' in window) {
        optimizeImages();
    }
    
    // ============================================
    // VIEWPORT HEIGHT FIX (Mobile address bar)
    // ============================================
    function setViewportHeight() {
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', vh + 'px');
    }
    
    setViewportHeight();
    window.addEventListener('resize', setViewportHeight);
    window.addEventListener('orientationchange', setViewportHeight);
    
    // ============================================
    // MOBILE KEYBOARD AWARENESS
    // ============================================
    const inputs = document.querySelectorAll('input, textarea');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            // Add small delay to ensure keyboard is visible
            setTimeout(() => {
                this.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 300);
        });
    });
    
    // ============================================
    // PRINT MEDIA PREPARATION
    // ============================================
    function preparePrint() {
        const printButton = document.querySelector('[data-print]');
        if (printButton) {
            printButton.addEventListener('click', function() {
                // Hide non-essential elements before printing
                const sidebar = document.querySelector('.sidebar');
                const navbar = document.querySelector('.navbar');
                if (sidebar) sidebar.style.display = 'none';
                if (navbar) navbar.style.display = 'none';
                
                window.print();
                
                // Restore elements after printing
                if (sidebar) sidebar.style.display = '';
                if (navbar) navbar.style.display = '';
            });
        }
    }
    
    preparePrint();
    
    // ============================================
    // RESPONSIVE MODAL HANDLING
    // ============================================
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        const closeBtn = modal.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                modal.classList.remove('open');
            });
        }
        
        // Close modal on background click
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                this.classList.remove('open');
            }
        });
    });
    
    // ============================================
    // FORM VALIDATION RESPONSIVENESS
    // ============================================
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const inputs = this.querySelectorAll('input[required], textarea[required], select[required]');
            let isValid = true;
            
            inputs.forEach(input => {
                if (!input.value.trim()) {
                    input.classList.add('error');
                    isValid = false;
                } else {
                    input.classList.remove('error');
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                // Scroll to first error
                const firstError = this.querySelector('.error');
                if (firstError) {
                    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstError.focus();
                }
            }
        });
    });
    
    // ============================================
    // ORIENTATION CHANGE HANDLER
    // ============================================
    window.addEventListener('orientationchange', function() {
        // Adjust layout for new orientation
        setTimeout(() => {
            updateDeviceClass();
            setViewportHeight();
            // Close sidebar on rotation
            if (sidebar) {
                sidebar.classList.remove('mobile-open');
            }
        }, 100);
    });
    
    // ============================================
    // RESPONSIVE PERFORMANCE MONITORING
    // ============================================
    if (window.performance && window.performance.timing) {
        window.addEventListener('load', function() {
            const perfData = window.performance.timing;
            const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
            console.log('Page load time: ' + pageLoadTime + 'ms');
        });
    }
});

// ============================================
// EXPORT FUNCTION FOR EXTERNAL USE
// ============================================
window.ResponsiveApp = {
    getDeviceType: function() {
        const width = window.innerWidth;
        if (width <= 480) return 'mobile';
        if (width <= 768) return 'tablet';
        if (width <= 1024) return 'desktop';
        return 'large-desktop';
    },
    
    isMobile: function() {
        return this.getDeviceType() === 'mobile';
    },
    
    isTablet: function() {
        return this.getDeviceType() === 'tablet';
    },
    
    isDesktop: function() {
        return ['desktop', 'large-desktop'].includes(this.getDeviceType());
    },
    
    toggleSidebar: function() {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.toggle('mobile-open');
        }
    }
};
