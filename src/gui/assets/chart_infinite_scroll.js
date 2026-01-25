// Infinite scroll detection for chart time axis
// Uses Plotly's native pan mode for horizontal wheel scrolling (smooth and performant)
// For Shift+Wheel, uses RequestAnimationFrame batching with Plotly.relayout() for smooth panning
// Threshold detection handled by Python callback via relayoutData events
(function() {
    'use strict';
    
    // Track scroll state per chart (minimal state needed)
    const chartScrollState = new Map();
    
    /**
     * Create HTML overlay for center line (no Plotly relayout needed!)
     */
    function createCenterLineOverlay(graphElement, graphId) {
        // Check if overlay already exists
        let overlay = graphElement.querySelector('.chart-center-line-overlay');
        if (overlay) {
            return overlay;
        }

        // Create overlay container
        overlay = document.createElement('div');
        overlay.className = 'chart-center-line-overlay';
        overlay.style.cssText = `
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 1px;
            height: 100%;
            background: linear-gradient(to bottom, rgba(255,255,255,0.3) 0%, rgba(255,255,255,0.3) 50%, transparent 50%, transparent 52%, rgba(255,255,255,0.3) 52%);
            background-size: 1px 8px;
            pointer-events: none;
            z-index: 10;
        `;

        // Create timestamp label
        const label = document.createElement('div');
        label.className = 'chart-center-timestamp';
        label.style.cssText = `
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
            z-index: 11;
        `;

        graphElement.style.position = 'relative';
        graphElement.appendChild(overlay);
        graphElement.appendChild(label);

        return overlay;
    }

    /**
     * Update center line timestamp (without Plotly relayout!)
     */
    function updateCenterLineTimestamp(graphDiv, graphElement, graphId) {
        if (!graphDiv || !graphDiv._fullLayout || !graphDiv._fullData) {
            return;
        }

        const layout = graphDiv._fullLayout;
        const xaxis = layout.xaxis;

        if (!xaxis || !xaxis.range) {
            return;
        }

        // Calculate center index of visible range
        const centerIndex = Math.round((xaxis.range[0] + xaxis.range[1]) / 2);

        // Get timestamp from data at center index
        let timestamp = '';
        try {
            const candlestickTrace = graphDiv._fullData.find(trace => trace.type === 'candlestick');
            if (candlestickTrace && candlestickTrace.x && centerIndex >= 0 && centerIndex < candlestickTrace.x.length) {
                const rawTimestamp = candlestickTrace.x[centerIndex];
                // Format timestamp nicely
                const date = new Date(rawTimestamp);
                timestamp = date.toLocaleString('de-DE', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            }
        } catch (e) {
            console.warn('[Center Line] Could not get timestamp:', e);
        }

        // Update timestamp label (direct DOM update, no Plotly involved!)
        const label = graphElement.querySelector('.chart-center-timestamp');
        if (label && timestamp) {
            label.textContent = timestamp;
        }
    }

    /**
     * Setup infinite scroll listener for a chart
     * Key principle:
     * - Horizontal wheel: Let Plotly handle scrolling natively for best performance
     * - Shift+Wheel: Use RequestAnimationFrame batching with Plotly.relayout() for smooth panning
     * - Threshold detection: Handled by Python callback via relayoutData events
     */
    function setupInfiniteScrollListener(graphId) {
        const graphElement = document.getElementById(graphId);
        if (!graphElement || chartScrollState.has(graphId)) {
            return; // Already setup or element not found
        }

        chartScrollState.set(graphId, {
            isLoading: false,
            scrollAccumulator: 0,
            rafId: null,
            centerLineRafId: null
        });

        const state = chartScrollState.get(graphId);

        // Get Plotly graph instance
        const graphDiv = graphElement.querySelector('.js-plotly-plot');
        if (!graphDiv || !graphDiv._fullData) {
            // Wait for Plotly to initialize
            setTimeout(() => setupInfiniteScrollListener(graphId), 500);
            return;
        }

        // Create center line overlay (HTML, not Plotly)
        createCenterLineOverlay(graphElement, graphId);
        
        /**
         * Apply accumulated scroll delta using RequestAnimationFrame for smooth panning
         * Only called once per frame, much more efficient than calling on every wheel event
         */
        function applyScroll(delta) {
            if (!delta || Math.abs(delta) < 0.001) {
                return;
            }
            
            const layout = graphDiv._fullLayout;
            if (!layout || !layout.xaxis || !layout.xaxis.range) {
                return;
            }
            
            const currentRange = layout.xaxis.range;
            const rangeSize = currentRange[1] - currentRange[0];
            
            // Calculate scroll amount (smooth, accumulated)
            // Use smaller multiplier for smoother scrolling
            const scrollAmount = delta * rangeSize * 0.0005;
            const newRange = [
                currentRange[0] - scrollAmount,
                currentRange[1] - scrollAmount
            ];
            
            // Update Plotly chart - this will trigger relayoutData event
            if (window.Plotly && Plotly.relayout) {
                Plotly.relayout(graphDiv, {
                    'xaxis.range': newRange
                });
            }
        }
        
        /**
         * Handle wheel events
         * Shift+Wheel = horizontal pan
         * Ctrl+Wheel = zoom (Plotly default)
         * Horizontal wheel = horizontal pan
         * IMPORTANT: Must capture in capture phase to intercept before Plotly's default handler
         */
        function handleWheelEvent(event) {
            // Debug: Log what we received
            const keyState = `Ctrl:${event.ctrlKey}, Shift:${event.shiftKey}, Alt:${event.altKey}`;

            // Ctrl+Wheel = zoom (let Plotly handle it natively)
            if (event.ctrlKey && !event.shiftKey && !event.altKey && !event.metaKey) {
                console.log(`[Scroll Debug] Ctrl+Wheel detected (${keyState}) - letting Plotly handle zoom`);
                // Let Plotly handle Ctrl+Wheel for zoom - do NOT prevent default
                return;
            }

            // Check for Shift+Wheel or horizontal scroll
            const isShiftWheel = event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey;
            const isHorizontalWheel = Math.abs(event.deltaX) > Math.abs(event.deltaY);

            // Handle Shift+Wheel or horizontal wheel scroll for panning
            if (isShiftWheel || isHorizontalWheel) {
                console.log(`[Scroll Debug] Shift+Wheel/Horizontal detected (${keyState}) - horizontal pan`);

                // Prevent default behavior - CRITICAL for blocking Plotly zoom
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                if (state.isLoading) {
                    return; // Already loading, ignore
                }

                // Calculate scroll delta:
                // - For Shift+Wheel: use deltaY
                // - For horizontal wheel: use deltaX directly
                let scrollDelta;
                if (isHorizontalWheel) {
                    scrollDelta = event.deltaX;
                } else {
                    scrollDelta = event.deltaY; // Shift+Wheel
                }

                state.scrollAccumulator += scrollDelta;

                // Schedule update via RequestAnimationFrame (batches updates for smooth scrolling)
                if (!state.rafId) {
                    state.rafId = window.requestAnimationFrame(() => {
                        // Apply accumulated scroll
                        applyScroll(state.scrollAccumulator);
                        state.scrollAccumulator = 0;
                        state.rafId = null;
                    });
                }
                return;
            }

            console.log(`[Scroll Debug] Plain wheel (${keyState}) - ignoring`);
            // For plain vertical wheel, do nothing
        }
        
        // Register wheel event handler in CAPTURE phase to intercept before Plotly
        // All events go through handleWheelEvent which decides what to do
        // IMPORTANT: passive: false is critical to allow preventDefault()
        graphElement.addEventListener('wheel', handleWheelEvent, {
            passive: false,
            capture: true  // CRITICAL: Capture phase intercepts before Plotly
        });

        // Also register on graphDiv itself for redundancy
        graphDiv.addEventListener('wheel', handleWheelEvent, {
            passive: false,
            capture: true  // CRITICAL: Capture phase intercepts before Plotly
        });

        // Listen for relayout events to update center line timestamp
        graphDiv.on('plotly_relayout', function(eventData) {
            // Schedule timestamp update via RAF to avoid too many updates
            if (!state.centerLineRafId) {
                state.centerLineRafId = window.requestAnimationFrame(() => {
                    updateCenterLineTimestamp(graphDiv, graphElement, graphId);
                    state.centerLineRafId = null;
                });
            }
        });

        // Update initial timestamp
        setTimeout(() => updateCenterLineTimestamp(graphDiv, graphElement, graphId), 100);

        // NOTE: Threshold checking is now handled by Python callback via relayoutData events
        // No need for plotly_relayouting listener - it was blocked by isScrolling flag anyway
        // The handle_infinite_scroll callback in app.py listens to relayoutData and handles thresholds

        console.log(`[Infinite Scroll] Setup complete for chart: ${graphId} (Shift+Wheel=pan, Ctrl+Wheel=zoom, horizontal=pan, center-line=HTML-overlay)`);
    }
    
    /**
     * Reset loading state (called from callback)
     */
    function resetLoadingState(graphId) {
        const state = chartScrollState.get(graphId);
        if (state) {
            state.isLoading = false;
        }
    }
    
    /**
     * Initialize scroll listeners for all charts
     */
    function initializeScrollListeners() {
        // Find all chart graphs
        const chartGraphs = document.querySelectorAll('[id*="chart-graph"]');
        
        chartGraphs.forEach(function(graphElement) {
            const graphId = graphElement.id;
            if (graphId && !chartScrollState.has(graphId)) {
                setupInfiniteScrollListener(graphId);
            }
        });
    }
    
    // Run initialization when DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeScrollListeners);
    } else {
        initializeScrollListeners();
    }
    
    // Also run after a delay to catch dynamically added charts
    setTimeout(initializeScrollListeners, 1000);
    
    // Watch for new chart elements being added
    const observer = new MutationObserver(function(mutations) {
        let shouldInit = false;
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) {
                    // Check if it's a chart graph or contains one
                    if (node.id && node.id.includes('chart-graph')) {
                        shouldInit = true;
                    } else if (node.querySelector && node.querySelector('[id*="chart-graph"]')) {
                        shouldInit = true;
                    }
                }
            });
        });
        if (shouldInit) {
            setTimeout(initializeScrollListeners, 100);
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Export reset function for use in callbacks
    window.resetChartScrollLoading = resetLoadingState;
    
})();
