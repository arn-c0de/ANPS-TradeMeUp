// Export Prediction Modal as DIN A4 PNG
// Uses html2canvas for client-side rendering and export
(function() {
    'use strict';

    // A4 dimensions at 300 DPI (portrait)
    const A4_WIDTH_PX = 2480;  // 210mm at 300 DPI
    const A4_HEIGHT_PX = 3508; // 297mm at 300 DPI

    let html2canvasLoaded = false;
    let loadingPromise = null;

    /**
     * Load html2canvas library from CDN
     */
    function loadHtml2Canvas() {
        if (html2canvasLoaded && window.html2canvas) {
            return Promise.resolve();
        }

        if (loadingPromise) {
            return loadingPromise;
        }

        loadingPromise = new Promise((resolve, reject) => {
            // Check if already loaded
            if (window.html2canvas) {
                html2canvasLoaded = true;
                resolve();
                return;
            }

            // Load from CDN
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
            script.crossOrigin = 'anonymous';
            script.onload = function() {
                html2canvasLoaded = true;
                console.log('✅ html2canvas loaded successfully');
                resolve();
            };
            script.onerror = function() {
                loadingPromise = null;
                reject(new Error('Failed to load html2canvas library'));
            };

            document.head.appendChild(script);
        });

        return loadingPromise;
    }

    /**
     * Show loading indicator on button
     */
    function setButtonLoading(button, isLoading) {
        if (isLoading) {
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.textContent = '⏳';
            button.title = 'Exporting...';
        } else {
            button.disabled = false;
            button.textContent = button.dataset.originalText || '📄';
            button.title = 'Export as DIN A4 PNG';
        }
    }

    /**
     * Get current prediction title for filename
     */
    function getPredictionTitle() {
        const titleElement = document.getElementById('prediction-modal-title');
        if (!titleElement) return 'prediction';

        // Extract text content and clean it for filename
        const titleText = titleElement.textContent || titleElement.innerText || '';
        return titleText
            .replace(/[^\w\s-]/g, '') // Remove special chars
            .replace(/\s+/g, '_')      // Replace spaces with underscores
            .substring(0, 50)          // Limit length
            .toLowerCase() || 'prediction';
    }

    /**
     * Export modal content as PNG
     */
    async function exportModalAsPNG() {
        try {
            // Find the export button
            const exportButton = document.getElementById('export-prediction-a4-png');
            if (!exportButton) {
                console.error('Export button not found');
                return;
            }

            setButtonLoading(exportButton, true);

            // Ensure html2canvas is loaded
            await loadHtml2Canvas();

            // Find the modal content to export
            const modalBody = document.getElementById('prediction-modal-body');
            if (!modalBody) {
                throw new Error('Modal content not found');
            }

            console.log('📸 Starting screenshot capture...');

            // Configure html2canvas options for high quality
            const canvas = await html2canvas(modalBody, {
                scale: 2,                    // Higher scale for better quality
                useCORS: true,              // Enable cross-origin images
                allowTaint: true,           // Allow cross-origin content
                backgroundColor: '#060606', // Dark background matching theme
                logging: false,             // Disable debug logging
                windowWidth: A4_WIDTH_PX,   // Set viewport width to A4
                windowHeight: A4_HEIGHT_PX, // Set viewport height to A4
                scrollY: -window.scrollY,   // Account for page scroll
                scrollX: -window.scrollX
            });

            console.log('✅ Screenshot captured, converting to PNG...');

            // Convert canvas to blob
            canvas.toBlob(function(blob) {
                if (!blob) {
                    throw new Error('Failed to create image blob');
                }

                // Create download link
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                const timestamp = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
                const filename = `${getPredictionTitle()}_${timestamp}.png`;

                link.href = url;
                link.download = filename;
                link.style.display = 'none';

                // Trigger download
                document.body.appendChild(link);
                link.click();

                // Cleanup
                setTimeout(() => {
                    document.body.removeChild(link);
                    URL.revokeObjectURL(url);
                    console.log('✅ Export completed:', filename);
                }, 100);

                setButtonLoading(exportButton, false);
            }, 'image/png', 1.0); // Maximum quality

        } catch (error) {
            console.error('❌ Export failed:', error);
            alert('Export failed: ' + error.message);

            const exportButton = document.getElementById('export-prediction-a4-png');
            if (exportButton) {
                setButtonLoading(exportButton, false);
            }
        }
    }

    /**
     * Setup event listeners for export button
     */
    function setupExportButton() {
        const exportButton = document.getElementById('export-prediction-a4-png');
        if (exportButton && !exportButton.exportListenerSetup) {
            exportButton.exportListenerSetup = true;

            exportButton.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                exportModalAsPNG();
            });

            console.log('✅ Export button listener setup complete');
        }
    }

    /**
     * Initialize on DOM ready
     */
    function initialize() {
        setupExportButton();

        // Preload html2canvas when modal is opened for faster export
        const modal = document.getElementById('prediction-modal');
        if (modal && !modal.preloadListenerSetup) {
            modal.preloadListenerSetup = true;

            // Watch for modal to become visible
            const observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.attributeName === 'class' || mutation.attributeName === 'style') {
                        const isOpen = modal.classList.contains('show') ||
                                     modal.style.display === 'block';

                        if (isOpen && !html2canvasLoaded) {
                            console.log('📦 Preloading html2canvas...');
                            loadHtml2Canvas().catch(err =>
                                console.warn('Preload failed:', err)
                            );
                        }
                    }
                });
            });

            observer.observe(modal, {
                attributes: true,
                attributeFilter: ['class', 'style']
            });
        }
    }

    // Run initialization
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }

    // Re-setup after DOM mutations (for Dash dynamic content)
    setTimeout(initialize, 1000);

    const observer = new MutationObserver(function(mutations) {
        let shouldReinit = false;
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) {
                    if (node.id === 'export-prediction-a4-png' ||
                        node.id === 'prediction-modal' ||
                        (node.querySelector && (
                            node.querySelector('#export-prediction-a4-png') ||
                            node.querySelector('#prediction-modal')
                        ))) {
                        shouldReinit = true;
                    }
                }
            });
        });

        if (shouldReinit) {
            setTimeout(initialize, 100);
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

})();
