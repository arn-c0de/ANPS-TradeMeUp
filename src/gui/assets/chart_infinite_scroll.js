// Infinite scroll detection for chart time axis
// Uses Plotly's native pan mode for horizontal wheel scrolling (smooth and performant)
// For Shift+Wheel, uses RequestAnimationFrame batching with Plotly.relayout() for smooth panning
// Threshold detection handled by Python callback via relayoutData events
(function() {
    'use strict';
    
    // Track scroll state per chart (minimal state needed)
    const chartScrollState = new Map();
    
    /**
     * Get module references (check dynamically to handle async loading)
     * Includes error handling and debugging
     */
    function getCenterLineOverlay() {
        try {
            const module = window.ChartCenterLineOverlay;
            if (!module) {
                if (console && console.debug) {
                    console.debug('[Chart Scroll] ChartCenterLineOverlay module not available');
                }
            } else if (console && console.debug) {
                console.debug('[Chart Scroll] ChartCenterLineOverlay module found');
            }
            return module;
        } catch (error) {
            console.error('[Chart Scroll] Error getting ChartCenterLineOverlay:', error);
            return null;
        }
    }
    
    function getChartTimestamps() {
        try {
            const module = window.ChartTimestamps;
            if (!module) {
                if (console && console.debug) {
                    console.debug('[Chart Scroll] ChartTimestamps module not available');
                }
            } else if (console && console.debug) {
                console.debug('[Chart Scroll] ChartTimestamps module found');
            }
            return module;
        } catch (error) {
            console.error('[Chart Scroll] Error getting ChartTimestamps:', error);
            return null;
        }
    }
    
    /**
     * Check if modules are available with more aggressive checking
     * Returns object with availability status
     */
    function checkModuleAvailability() {
        const CenterLineOverlay = getCenterLineOverlay();
        const ChartTimestamps = getChartTimestamps();
        
        const bothAvailable = CenterLineOverlay && ChartTimestamps;
        const overlayAvailable = CenterLineOverlay && CenterLineOverlay.create;
        const timestampsAvailable = ChartTimestamps && ChartTimestamps.updateCenterLineTimestamp;
        
        return {
            both: bothAvailable,
            overlay: overlayAvailable,
            timestamps: timestampsAvailable,
            overlayModule: CenterLineOverlay,
            timestampsModule: ChartTimestamps
        };
    }
    
    /**
     * Fallback overlay creation if module not available
     * Provides basic functionality even if modules fail to load
     */
    function createOverlayFallback(graphElement, graphId) {
        try {
            // Check if overlay already exists
            let overlay = graphElement.querySelector('.chart-center-line-overlay');
            if (overlay) {
                return overlay;
            }

            // Find the Plotly plot container
            const plotContainer = graphElement.querySelector('.js-plotly-plot');
            if (!plotContainer) {
                return null;
            }

            const svgElement = plotContainer.querySelector('svg');
            
            // Ensure plot container has relative positioning
            const computedStyle = window.getComputedStyle(plotContainer);
            if (computedStyle.position === 'static' || computedStyle.position === '') {
                plotContainer.style.position = 'relative';
            }

            // Ensure graphElement has relative positioning
            if (window.getComputedStyle(graphElement).position === 'static') {
                graphElement.style.position = 'relative';
            }

            // Get plot container height
            let plotHeight = plotContainer.offsetHeight || plotContainer.clientHeight;
            if (plotHeight === 0) {
                if (svgElement) {
                    plotHeight = svgElement.clientHeight || svgElement.getBoundingClientRect().height || 400;
                } else {
                    plotHeight = 400;
                }
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
                min-height: ${plotHeight}px;
                height: ${plotHeight}px;
                background-color: rgba(255, 255, 255, 0.3);
                pointer-events: none;
                z-index: 1000;
            `;

            // Update overlay height dynamically
            const updateOverlayHeight = () => {
                let currentHeight = plotContainer.offsetHeight || plotContainer.clientHeight;
                if (currentHeight === 0 && svgElement) {
                    currentHeight = svgElement.clientHeight || svgElement.getBoundingClientRect().height || 400;
                }
                if (currentHeight > 0 && overlay) {
                    overlay.style.height = currentHeight + 'px';
                    overlay.style.minHeight = currentHeight + 'px';
                    overlay.style.background = 'linear-gradient(to bottom, rgba(255,255,255,0.3) 0%, rgba(255,255,255,0.3) 50%, transparent 50%, transparent 52%, rgba(255,255,255,0.3) 52%)';
                    overlay.style.backgroundSize = '1px 8px';
                }
            };
            
            if (window.ResizeObserver) {
                const resizeObserver = new ResizeObserver(updateOverlayHeight);
                resizeObserver.observe(plotContainer);
                if (svgElement) {
                    resizeObserver.observe(svgElement);
                }
            } else {
                setTimeout(updateOverlayHeight, 500);
            }
            
            setTimeout(updateOverlayHeight, 100);
            setTimeout(updateOverlayHeight, 300);
            setTimeout(updateOverlayHeight, 600);

            // Create center timestamp label
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

            // Create last update label
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

            // Append elements
            if (svgElement && svgElement.parentNode) {
                svgElement.parentNode.insertBefore(overlay, svgElement.nextSibling);
                svgElement.parentNode.insertBefore(centerLabel, svgElement.nextSibling);
            } else {
                plotContainer.appendChild(overlay);
                plotContainer.appendChild(centerLabel);
            }
            
            graphElement.appendChild(lastUpdateLabel);

            return overlay;
        } catch (error) {
            console.error('[Chart Scroll] Fallback overlay creation failed:', error);
            return null;
        }
    }
    
    /**
     * Fallback timestamp update if module not available
     */
    function updateTimestampFallback(graphDiv, graphElement, graphId) {
        try {
            if (!graphDiv || !graphDiv._fullLayout || !graphDiv._fullData) {
                return false;
            }

            const layout = graphDiv._fullLayout;
            const xaxis = layout.xaxis;

            // Get trace data
            let trace = null;
            try {
                trace = graphDiv._fullData.find(trace => trace.type === 'candlestick');
                if (!trace || !trace.x || trace.x.length === 0) {
                    trace = graphDiv._fullData.find(trace => trace.type === 'scatter' && trace.mode && trace.mode.includes('lines'));
                }
                if (!trace || !trace.x || trace.x.length === 0) {
                    trace = graphDiv._fullData.find(trace => trace.x && trace.x.length > 0);
                }
                
                if (!trace || !trace.x || trace.x.length === 0) {
                    return false;
                }
            } catch (e) {
                return false;
            }

            const xData = trace.x;
            let timestamp = '';
            let centerIndex = -1;

            if (xaxis && xaxis.range && Array.isArray(xaxis.range) && xaxis.range.length === 2) {
                const range = xaxis.range;
                if (typeof range[0] === 'number' && typeof range[1] === 'number') {
                    centerIndex = Math.round((range[0] + range[1]) / 2);
                    if (centerIndex < 0) centerIndex = 0;
                    if (centerIndex >= xData.length) centerIndex = xData.length - 1;
                } else {
                    const centerValue = range[0] + (range[1] - range[0]) / 2;
                    for (let i = 0; i < xData.length; i++) {
                        if (xData[i] === centerValue || String(xData[i]) === String(centerValue)) {
                            centerIndex = i;
                            break;
                        }
                    }
                    if (centerIndex === -1) {
                        centerIndex = Math.floor(xData.length / 2);
                    }
                }
            } else {
                centerIndex = Math.floor(xData.length / 2);
            }

            // Simple timestamp formatting fallback
            if (centerIndex >= 0 && centerIndex < xData.length) {
                const rawTimestamp = xData[centerIndex];
                try {
                    const date = new Date(rawTimestamp);
                    if (!isNaN(date.getTime())) {
                        timestamp = date.toLocaleString('de-DE', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit'
                        });
                    }
                } catch (e) {
                    // Ignore formatting errors
                }
            }

            // Update center label
            const plotContainer = graphElement.querySelector('.js-plotly-plot');
            const centerLabel = plotContainer ? plotContainer.querySelector('.chart-center-timestamp') : null;
            if (centerLabel) {
                let labelText = timestamp || '';
                
                // Get last candle timestamp
                try {
                    const lastRawTimestamp = trace.x[trace.x.length - 1];
                    const lastDate = new Date(lastRawTimestamp);
                    if (!isNaN(lastDate.getTime())) {
                        const lastCandleTimestamp = lastDate.toLocaleString('de-DE', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit'
                        });
                        const chartType = graphDiv._fullData.find(trace => trace.type === 'candlestick') ? 'candle' : 'point';
                        if (lastCandleTimestamp) {
                            if (labelText) {
                                labelText += ` | Last ${chartType}: ${lastCandleTimestamp}`;
                            } else {
                                labelText = `Last ${chartType}: ${lastCandleTimestamp}`;
                            }
                        }
                    }
                } catch (e) {
                    // Ignore errors
                }
                
                centerLabel.textContent = labelText;
            }

            // Update last update label
            const lastUpdateLabel = graphElement.querySelector('.chart-last-update');
            if (lastUpdateLabel) {
                let lastUpdateAttr = graphElement.getAttribute('data-last-update');
                if (!lastUpdateAttr) {
                    let parent = graphElement.parentElement;
                    let depth = 0;
                    while (parent && depth < 5 && !lastUpdateAttr) {
                        lastUpdateAttr = parent.getAttribute('data-last-update');
                        parent = parent.parentElement;
                        depth++;
                    }
                }
                
                if (lastUpdateAttr) {
                    try {
                        const date = new Date(lastUpdateAttr);
                        if (!isNaN(date.getTime())) {
                            const formatted = date.toLocaleString('de-DE', {
                                year: 'numeric',
                                month: '2-digit',
                                day: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit'
                            });
                            lastUpdateLabel.textContent = `Last update: ${formatted}`;
                        } else {
                            lastUpdateLabel.textContent = '';
                        }
                    } catch (e) {
                        lastUpdateLabel.textContent = '';
                    }
                } else {
                    lastUpdateLabel.textContent = '';
                }
            }

            return timestamp !== '';
        } catch (error) {
            console.error('[Chart Scroll] Fallback timestamp update failed:', error);
            return false;
        }
    }

    /**
     * Find the actual graph element (handles wrapped graphs)
     * Returns the element that contains the Plotly instance
     */
    function findActualGraphElement(element) {
        if (!element) return null;
        
        // Check if this element has the Plotly instance
        const plotContainer = element.querySelector('.js-plotly-plot');
        if (plotContainer && plotContainer._fullData) {
            return element;
        }
        
        // If element is a wrapper div, find the actual graph element inside
        // The actual graph element should have the ID and contain .js-plotly-plot
        if (element.querySelector) {
            const innerGraph = element.querySelector('[id*="chart-graph"]');
            if (innerGraph) {
                const innerPlotContainer = innerGraph.querySelector('.js-plotly-plot');
                if (innerPlotContainer) {
                    return innerGraph;
                }
            }
        }
        
        return element;
    }

    /**
     * Check if chart is ready for initialization
     */
    function isChartReady(graphElement) {
        if (!graphElement) return false;
        const actualElement = findActualGraphElement(graphElement);
        if (!actualElement) return false;
        
        const plotContainer = actualElement.querySelector('.js-plotly-plot');
        return plotContainer && plotContainer._fullData && plotContainer._fullLayout;
    }

    /**
     * Setup infinite scroll listener for a chart
     * Key principle:
     * - Horizontal wheel: Let Plotly handle scrolling natively for best performance
     * - Shift+Wheel: Use RequestAnimationFrame batching with Plotly.relayout() for smooth panning
     * - Threshold detection: Handled by Python callback via relayoutData events
     */
    function setupInfiniteScrollListener(graphId, retryCount = 0) {
        const graphElement = document.getElementById(graphId);
        if (!graphElement) {
            // Element not found - retry if we haven't tried too many times
            if (retryCount < 5) {
                setTimeout(() => setupInfiniteScrollListener(graphId, retryCount + 1), 200 * (retryCount + 1));
            }
            return;
        }
        
        if (chartScrollState.has(graphId)) {
            return; // Already setup
        }

        // Find the actual graph element (handles wrapped graphs)
        const actualGraphElement = findActualGraphElement(graphElement);
        if (!actualGraphElement) {
            // Graph element not ready - retry
            if (retryCount < 5) {
                setTimeout(() => setupInfiniteScrollListener(graphId, retryCount + 1), 200 * (retryCount + 1));
            }
            return;
        }

        chartScrollState.set(graphId, {
            isLoading: false,
            scrollAccumulator: 0,
            rafId: null,
            centerLineRafId: null
        });

        const state = chartScrollState.get(graphId);

        // Get Plotly graph instance from the actual graph element
        const graphDiv = actualGraphElement.querySelector('.js-plotly-plot');
        if (!graphDiv || !graphDiv._fullData) {
            // Wait for Plotly to initialize - retry with exponential backoff
            if (retryCount < 8) {
                setTimeout(() => setupInfiniteScrollListener(graphId, retryCount + 1), 150 + retryCount * 100);
            }
            return;
        }

        // Listen for afterplot event (fires after chart is fully rendered) - create overlay here
        graphDiv.on('plotly_afterplot', function() {
            // Wait for modules to be available with retry logic (increased retries)
            const waitForModules = (callback, retries = 30) => {
                try {
                    const availability = checkModuleAvailability();
                    
                    if (availability.both) {
                        callback(availability.overlayModule, availability.timestampsModule, false);
                    } else if (retries > 0) {
                        // More aggressive retry: check more frequently at first, then slower
                        const delay = retries > 20 ? 50 : (retries > 10 ? 100 : 200);
                        setTimeout(() => waitForModules(callback, retries - 1), delay);
                    } else {
                        // Use fallback if modules aren't available after retries
                        console.warn('[Chart Scroll] Modules not available after ' + (30 - retries) + ' retries, using fallback');
                        console.warn('[Chart Scroll] Overlay available:', availability.overlay, 'Timestamps available:', availability.timestamps);
                        callback(null, null, true);
                    }
                } catch (error) {
                    console.error('[Chart Scroll] Error waiting for modules:', error);
                    callback(null, null, true);
                }
            };
            
            waitForModules((CenterLineOverlay, ChartTimestamps, useFallback) => {
                try {
                    if (useFallback) {
                        // Use fallback functions
                        if (!actualGraphElement.querySelector('.chart-center-line-overlay')) {
                            createOverlayFallback(actualGraphElement, graphId);
                        }
                        updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                    } else {
                        // Use module functions
                        if (CenterLineOverlay && !actualGraphElement.querySelector('.chart-center-line-overlay')) {
                            try {
                                CenterLineOverlay.create(actualGraphElement, graphId);
                            } catch (error) {
                                console.error('[Chart Scroll] Error creating overlay:', error);
                                createOverlayFallback(actualGraphElement, graphId);
                            }
                        }
                        if (ChartTimestamps) {
                            try {
                                ChartTimestamps.updateCenterLineTimestamp(graphDiv, actualGraphElement, graphId);
                            } catch (error) {
                                console.error('[Chart Scroll] Error updating timestamp:', error);
                                updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                            }
                        } else {
                            updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                        }
                    }
                } catch (error) {
                    console.error('[Chart Scroll] Error in afterplot handler:', error);
                    // Try fallback as last resort
                    try {
                        if (!actualGraphElement.querySelector('.chart-center-line-overlay')) {
                            createOverlayFallback(actualGraphElement, graphId);
                        }
                        updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                    } catch (fallbackError) {
                        console.error('[Chart Scroll] Fallback also failed:', fallbackError);
                    }
                }
            });
        });

        // Create center line overlay immediately (will be updated by afterplot event)
        // Use actualGraphElement to handle wrapped graphs
        // Wait for modules to be available with aggressive retry logic
        const waitForModules = (callback, retries = 30) => {
            try {
                const availability = checkModuleAvailability();
                
                if (availability.both) {
                    callback(availability.overlayModule, availability.timestampsModule, false);
                } else if (retries > 0) {
                    // More aggressive retry: check more frequently at first, then slower
                    const delay = retries > 20 ? 50 : (retries > 10 ? 100 : 200);
                    setTimeout(() => waitForModules(callback, retries - 1), delay);
                } else {
                    // Use fallback if modules aren't available after retries
                    console.warn('[Chart Scroll] Modules not available after ' + (30 - retries) + ' retries, using fallback');
                    console.warn('[Chart Scroll] Overlay available:', availability.overlay, 'Timestamps available:', availability.timestamps);
                    callback(null, null, true);
                }
            } catch (error) {
                console.error('[Chart Scroll] Error waiting for modules:', error);
                callback(null, null, true);
            }
        };
        
        waitForModules((CenterLineOverlay, ChartTimestamps, useFallback) => {
            try {
                if (useFallback) {
                    // Use fallback functions
                    createOverlayFallback(actualGraphElement, graphId);
                    updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                } else {
                    // Use module functions
                    if (CenterLineOverlay) {
                        try {
                            CenterLineOverlay.create(actualGraphElement, graphId);
                        } catch (error) {
                            console.error('[Chart Scroll] Error creating overlay:', error);
                            createOverlayFallback(actualGraphElement, graphId);
                        }
                    } else {
                        createOverlayFallback(actualGraphElement, graphId);
                    }
                    
                    if (ChartTimestamps) {
                        try {
                            ChartTimestamps.updateCenterLineTimestamp(graphDiv, actualGraphElement, graphId);
                        } catch (error) {
                            console.error('[Chart Scroll] Error updating timestamp:', error);
                            updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                        }
                    } else {
                        updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                    }
                }
            } catch (error) {
                console.error('[Chart Scroll] Error in initial setup:', error);
                // Try fallback as last resort
                try {
                    createOverlayFallback(actualGraphElement, graphId);
                    updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                } catch (fallbackError) {
                    console.error('[Chart Scroll] Fallback also failed:', fallbackError);
                }
            }
        });

        // Improved initial timestamp update with retry logic (increased retries)
        function tryUpdateTimestamp(retries = 15) {
            try {
                const availability = checkModuleAvailability();
                const ChartTimestamps = availability.timestampsModule;
                
                if (!ChartTimestamps || !availability.timestamps) {
                    // Module not loaded yet, retry or use fallback
                    if (retries > 0) {
                        // More aggressive retry at first
                        const delay = retries > 10 ? 50 : (retries > 5 ? 100 : 200);
                        setTimeout(() => tryUpdateTimestamp(retries - 1), delay);
                    } else {
                        // Use fallback if module still not available
                        console.warn('[Chart Scroll] Timestamps module not available after retries, using fallback');
                        updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                    }
                    return;
                }
                
                let success = false;
                try {
                    success = ChartTimestamps.updateCenterLineTimestamp(graphDiv, actualGraphElement, graphId);
                } catch (error) {
                    console.error('[Chart Scroll] Error updating timestamp:', error);
                    updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                    return;
                }
                
                // Check if timestamp was successfully set
                const plotContainer = actualGraphElement.querySelector('.js-plotly-plot');
                const centerLabel = plotContainer ? plotContainer.querySelector('.chart-center-timestamp') : null;
                const hasTimestamp = centerLabel && centerLabel.textContent && centerLabel.textContent.trim() !== '';
                
                if (hasTimestamp || retries <= 0) {
                    if (!hasTimestamp && retries <= 0) {
                        // Try fallback as last resort
                        console.warn('[Chart Scroll] Timestamp not set after retries, using fallback');
                        updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                    }
                    return;
                }
                // Retry with increasing delays
                const delay = retries > 10 ? 50 : (retries > 5 ? 100 : 200);
                setTimeout(() => tryUpdateTimestamp(retries - 1), delay);
            } catch (error) {
                console.error('[Chart Scroll] Error in tryUpdateTimestamp:', error);
                // Try fallback
                try {
                    updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                } catch (fallbackError) {
                    console.error('[Chart Scroll] Fallback also failed:', fallbackError);
                }
            }
        }

        // Start initial update attempts with multiple retries
        setTimeout(() => tryUpdateTimestamp(), 100);
        setTimeout(() => tryUpdateTimestamp(), 300);
        setTimeout(() => tryUpdateTimestamp(), 600);
        
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
            // Ctrl+Wheel = zoom (let Plotly handle it natively)
            if (event.ctrlKey && !event.shiftKey && !event.altKey && !event.metaKey) {
                // Let Plotly handle Ctrl+Wheel for zoom - do NOT prevent default
                return;
            }

            // Check for Shift+Wheel or horizontal scroll
            const isShiftWheel = event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey;
            const isHorizontalWheel = Math.abs(event.deltaX) > Math.abs(event.deltaY);

            // Handle Shift+Wheel or horizontal wheel scroll for panning
            if (isShiftWheel || isHorizontalWheel) {
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

            // For plain vertical wheel, do nothing
        }
        
        // Register wheel event handler in CAPTURE phase to intercept before Plotly
        // All events go through handleWheelEvent which decides what to do
        // IMPORTANT: passive: false is critical to allow preventDefault()
        // Use actualGraphElement to handle wrapped graphs
        actualGraphElement.addEventListener('wheel', handleWheelEvent, {
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
            try {
                const availability = checkModuleAvailability();
                const ChartTimestamps = availability.timestampsModule;
                
                if (availability.timestamps && ChartTimestamps && !state.centerLineRafId) {
                    state.centerLineRafId = window.requestAnimationFrame(() => {
                        try {
                            ChartTimestamps.updateCenterLineTimestamp(graphDiv, actualGraphElement, graphId);
                        } catch (error) {
                            console.error('[Chart Scroll] Error updating timestamp in relayout:', error);
                            updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                        }
                        state.centerLineRafId = null;
                    });
                } else if (!availability.timestamps && !state.centerLineRafId) {
                    // Use fallback if module not available
                    state.centerLineRafId = window.requestAnimationFrame(() => {
                        updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                        state.centerLineRafId = null;
                    });
                }
            } catch (error) {
                console.error('[Chart Scroll] Error in relayout handler:', error);
                // Try fallback as last resort
                if (!state.centerLineRafId) {
                    state.centerLineRafId = window.requestAnimationFrame(() => {
                        updateTimestampFallback(graphDiv, actualGraphElement, graphId);
                        state.centerLineRafId = null;
                    });
                }
            }
        });

        // NOTE: Threshold checking is now handled by Python callback via relayoutData events
        // No need for plotly_relayouting listener - it was blocked by isScrolling flag anyway
        // The handle_infinite_scroll callback in app.py listens to relayoutData and handles thresholds
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
     * Handles both direct chart elements and wrapped graphs
     */
    function initializeScrollListeners() {
        // Find all chart graphs by ID pattern
        const chartGraphs = document.querySelectorAll('[id*="chart-graph"]');
        const processedIds = new Set();
        
        // Process direct chart elements
        chartGraphs.forEach(function(graphElement) {
            const graphId = graphElement.id;
            if (graphId && !chartScrollState.has(graphId) && !processedIds.has(graphId)) {
                processedIds.add(graphId);
                setupInfiniteScrollListener(graphId);
            }
        });
        
        // Also find charts by looking for Plotly plot containers
        // This catches charts that might be wrapped in divs or not yet have IDs set
        const plotContainers = document.querySelectorAll('.js-plotly-plot');
        plotContainers.forEach(function(plotContainer) {
            // Find parent element with chart-graph ID
            let parent = plotContainer.closest('[id*="chart-graph"]');
            
            // If no parent with ID found, walk up the tree to find it
            if (!parent) {
                parent = plotContainer.parentElement;
                let depth = 0;
                while (parent && depth < 10 && !parent.id.includes('chart-graph')) {
                    parent = parent.parentElement;
                    depth++;
                }
            }
            
            // If we found a parent with chart-graph ID, initialize it
            if (parent && parent.id && parent.id.includes('chart-graph')) {
                const graphId = parent.id;
                if (!chartScrollState.has(graphId) && !processedIds.has(graphId)) {
                    processedIds.add(graphId);
                    setupInfiniteScrollListener(graphId);
                }
            }
        });
    }
    
    // Run initialization when DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeScrollListeners);
    } else {
        initializeScrollListeners();
    }
    
    // Also run after delays to catch dynamically added charts (especially in quad view)
    setTimeout(initializeScrollListeners, 500);
    setTimeout(initializeScrollListeners, 1000);
    setTimeout(initializeScrollListeners, 2000);
    
    // Debounce function to avoid too many initialization attempts
    let initTimeout = null;
    function debouncedInitialize() {
        if (initTimeout) {
            clearTimeout(initTimeout);
        }
        initTimeout = setTimeout(initializeScrollListeners, 200);
    }
    
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
                    // Also check for Plotly plot containers being added (catches wrapped graphs)
                    if (node.classList && node.classList.contains('js-plotly-plot')) {
                        shouldInit = true;
                    } else if (node.querySelector && node.querySelector('.js-plotly-plot')) {
                        shouldInit = true;
                    }
                }
            });
        });
        if (shouldInit) {
            debouncedInitialize();
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Export reset function for use in callbacks
    window.resetChartScrollLoading = resetLoadingState;
    
})();
