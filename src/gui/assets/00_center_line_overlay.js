// Center Line Overlay Module
// Creates and manages the vertical center line overlay with labels for chart displays
(function() {
    'use strict';
    
    try {
        /**
         * Create HTML overlay for center line (no Plotly relayout needed!)
         * Creates vertical line, center timestamp label, and last update label
         */
        function createCenterLineOverlay(graphElement, graphId) {
        // Check if overlay already exists - if so, update it instead of recreating
        let overlay = graphElement.querySelector('.chart-center-line-overlay');
        let needsUpdate = false;
        if (overlay) {
            needsUpdate = true;
        }

        // Find the Plotly plot container (the actual chart area)
        const plotContainer = graphElement.querySelector('.js-plotly-plot');
        if (!plotContainer) {
            return null;
        }

        // Find the SVG element (Plotly's main chart area)
        const svgElement = plotContainer.querySelector('svg');
        
        // Ensure plot container has relative positioning
        const computedStyle = window.getComputedStyle(plotContainer);
        if (computedStyle.position === 'static' || computedStyle.position === '') {
            plotContainer.style.position = 'relative';
        }

        // Ensure graphElement has relative positioning for last update label
        if (window.getComputedStyle(graphElement).position === 'static') {
            graphElement.style.position = 'relative';
        }

        // Update overlay height function - shared for both new and existing overlays
        const updateOverlayHeight = () => {
            if (!overlay) return;
            let currentHeight = plotContainer.offsetHeight || plotContainer.clientHeight;
            if (currentHeight === 0 && svgElement) {
                currentHeight = svgElement.clientHeight || svgElement.getBoundingClientRect().height || 400;
            }
            if (currentHeight > 0) {
                overlay.style.height = currentHeight + 'px';
                overlay.style.minHeight = currentHeight + 'px';
                // Apply gradient background after height is set
                overlay.style.background = 'linear-gradient(to bottom, rgba(255,255,255,0.3) 0%, rgba(255,255,255,0.3) 50%, transparent 50%, transparent 52%, rgba(255,255,255,0.3) 52%)';
                overlay.style.backgroundSize = '1px 8px';
            }
        };
        
        // If overlay exists, update it immediately and return
        if (needsUpdate && overlay) {
            updateOverlayHeight();
            // Use ResizeObserver to keep it updated
            if (window.ResizeObserver) {
                // Check if observer already exists (avoid duplicates)
                if (!overlay.__resizeObserver) {
                    const resizeObserver = new ResizeObserver(updateOverlayHeight);
                    resizeObserver.observe(plotContainer);
                    if (svgElement) {
                        resizeObserver.observe(svgElement);
                    }
                    overlay.__resizeObserver = resizeObserver;
                }
            }
            // Immediate update
            requestAnimationFrame(updateOverlayHeight);
            return overlay;
        }
        
        // Create new overlay only if it doesn't exist
        // Get plot container height for overlay - wait a bit if height is 0
        let plotHeight = plotContainer.offsetHeight || plotContainer.clientHeight;
        if (plotHeight === 0) {
            // Try to get height from SVG if available
            if (svgElement) {
                plotHeight = svgElement.clientHeight || svgElement.getBoundingClientRect().height || 400;
            } else {
                plotHeight = 400; // Fallback
            }
        }

        // Create overlay container (centered vertical line)
        overlay = document.createElement('div');
        overlay.className = 'chart-center-line-overlay';
        // Use a simpler, more visible background first
        overlay.style.cssText = `
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 1px;
            min-height: ${plotHeight}px;
            height: ${plotHeight}px;
            background-color: rgba(255, 255, 255, 0.3);
            pointer-events: none;
            z-index: 1000;
        `;
        
        // Use ResizeObserver to update height dynamically for new overlays
        if (window.ResizeObserver) {
            const resizeObserver = new ResizeObserver(updateOverlayHeight);
            resizeObserver.observe(plotContainer);
            if (svgElement) {
                resizeObserver.observe(svgElement);
            }
            overlay.__resizeObserver = resizeObserver;
        } else {
            // Fallback: update after a delay
            setTimeout(updateOverlayHeight, 500);
        }
        
        // Also update immediately if height is available
        requestAnimationFrame(updateOverlayHeight);
        setTimeout(updateOverlayHeight, 50);

        // Create center timestamp label (at top of line, inside chart)
        const centerLabel = document.createElement('div');
        centerLabel.className = 'chart-center-timestamp';
        centerLabel.style.cssText = `
            position: absolute;
            top: 5px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.7);
            color: rgba(255, 255, 255, 0.8);
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-family: monospace;
            white-space: nowrap;
            pointer-events: none;
            z-index: 1001;
        `;

        // Create last update label (at top, behind symbol abbreviation)
        const lastUpdateLabel = document.createElement('div');
        lastUpdateLabel.className = 'chart-last-update';
        lastUpdateLabel.style.cssText = `
            position: absolute;
            top: 5px;
            right: 10px;
            background: rgba(0, 0, 0, 0.7);
            color: rgba(200, 200, 200, 0.7);
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 10px;
            font-family: monospace;
            white-space: nowrap;
            pointer-events: none;
            z-index: 1002;
        `;

        // Append to plot container (for center label and overlay)
        // Insert after SVG to ensure it's on top
        if (svgElement && svgElement.parentNode) {
            // Insert after SVG
            svgElement.parentNode.insertBefore(overlay, svgElement.nextSibling);
            svgElement.parentNode.insertBefore(centerLabel, svgElement.nextSibling);
        } else {
            // Fallback: append to plot container
            plotContainer.appendChild(overlay);
            plotContainer.appendChild(centerLabel);
        }
        
        // Append to graphElement (for last update label - outside chart area)
        graphElement.appendChild(lastUpdateLabel);

            return overlay;
        }
        
        // Export functions immediately
        window.ChartCenterLineOverlay = {
            create: createCenterLineOverlay
        };
        
        // Log successful initialization
        if (console && console.log) {
            console.log('[Chart Center Line Overlay] Module loaded successfully');
        }
    } catch (error) {
        // Log error but still export a minimal fallback
        console.error('[Chart Center Line Overlay] Error initializing module:', error);
        window.ChartCenterLineOverlay = {
            create: function(graphElement, graphId) {
                console.warn('[Chart Center Line Overlay] Using fallback - module initialization failed');
                return null;
            }
        };
    }
    
})();
