/**
 * Drag-to-resize functionality for chart splitters.
 * Load after Plotly (e.g. after {%scripts%}).
 */
document.addEventListener('DOMContentLoaded', function() {
    let isDragging = false;
    let currentSplitter = null;
    let startPos = 0;
    let resizeRaf = null;
    let windowResizeRaf = null;
    let cachedGraphs = null;
    let lastResizeTime = 0;
    let resizeTimeout = null;
    let lastResizeObserverTime = 0;

    function updateOverlaysAfterResize(graphElement) {
        // Recreate/update center line overlay after resize
        if (window.ChartCenterLineOverlay && window.ChartCenterLineOverlay.create) {
            try {
                // Find the graph container (dash-graph or chart-content)
                const graphContainer = graphElement.closest('[id*="chart-content"], .dash-graph') || graphElement;
                if (graphContainer) {
                    // Recreate overlay - it will check if it exists and update if needed
                    window.ChartCenterLineOverlay.create(graphContainer, graphElement.id || '');
                }
            } catch (err) {
                console.warn('[Chart Resize] Error updating overlays:', err);
            }
        }
    }

    function resizePlotlyCharts(scope) {
        if (!window.Plotly || !Plotly.Plots || !Plotly.Plots.resize) return;
        const root = scope || document;
        
        // Cache graph elements to avoid repeated DOM queries during rapid resizes
        if (!cachedGraphs || Date.now() - lastResizeTime > 50) {
            cachedGraphs = Array.from(root.querySelectorAll('.js-plotly-plot')).filter(
                graph => graph && graph.offsetParent !== null
            );
            lastResizeTime = Date.now();
        }
        
        // Batch resize all charts - immediate resize without delays for speed
        cachedGraphs.forEach(graph => {
            try {
                if (graph.offsetParent === null) return;
                
                // Immediate resize - Plotly handles this efficiently
                Plotly.Plots.resize(graph);
                
                // Update overlays after resize (center line, etc.)
                const graphElement = graph.closest('[id*="chart-content"], .dash-graph') || graph.parentElement;
                if (graphElement) {
                    updateOverlaysAfterResize(graphElement);
                }
            } catch (err) {
                /* ignore resize errors for detached nodes */
            }
        });
        
        // Single delayed redraw for all charts after resize completes (for content rendering)
        if (resizeTimeout) {
            clearTimeout(resizeTimeout);
        }
        resizeTimeout = setTimeout(() => {
            if (cachedGraphs) {
                cachedGraphs.forEach(graph => {
                    if (graph.offsetParent !== null && Plotly.redraw) {
                        try {
                            Plotly.redraw(graph);
                        } catch (err) {
                            /* ignore redraw errors */
                        }
                    }
                });
            }
            resizeTimeout = null;
        }, 100); // Single delayed redraw after resize settles
    }

    function schedulePlotlyResize(scope) {
        if (resizeRaf) return;
        resizeRaf = window.requestAnimationFrame(() => {
            resizeRaf = null;
            cachedGraphs = null; // Invalidate cache on resize
            resizePlotlyCharts(scope);
        });
    }

    function scheduleWindowResize(scope) {
        // Aggressively throttled window resize - only resize every 100ms max
        const now = Date.now();
        if (windowResizeRaf && (now - lastResizeObserverTime) < 100) {
            return; // Skip if called too frequently
        }
        lastResizeObserverTime = now;
        
        if (windowResizeRaf) {
            cancelAnimationFrame(windowResizeRaf);
        }
        windowResizeRaf = window.requestAnimationFrame(() => {
            windowResizeRaf = null;
            cachedGraphs = null; // Invalidate cache on window resize
            resizePlotlyCharts(scope);
        });
    }

    function initSplitters() {
        const hSplitters = document.querySelectorAll('.chart-splitter-horizontal');
        hSplitters.forEach(splitter => {
            splitter.addEventListener('mousedown', function(e) {
                isDragging = true;
                currentSplitter = splitter;
                startPos = e.clientY;
                document.body.style.cursor = 'ns-resize';
                e.preventDefault();
            });
        });

        const vSplitters = document.querySelectorAll('.chart-splitter-vertical');
        vSplitters.forEach(splitter => {
            splitter.addEventListener('mousedown', function(e) {
                isDragging = true;
                currentSplitter = splitter;
                startPos = e.clientX;
                document.body.style.cursor = 'ew-resize';
                e.preventDefault();
            });
        });
    }

    document.addEventListener('mousemove', function(e) {
        if (!isDragging || !currentSplitter) return;

        const isHorizontal = currentSplitter.classList.contains('chart-splitter-horizontal');
        const parent = currentSplitter.parentElement;
        const prevElement = currentSplitter.previousElementSibling;
        const nextElement = currentSplitter.nextElementSibling;

        if (!prevElement || !nextElement) return;

        if (isHorizontal) {
            const delta = e.clientY - startPos;
            const parentHeight = parent.offsetHeight;
            const prevHeight = prevElement.offsetHeight;
            const nextHeight = nextElement.offsetHeight;
            const newPrevHeight = prevHeight + delta;
            const newNextHeight = nextHeight - delta;
            if (newPrevHeight > 100 && newNextHeight > 100) {
                const prevPercent = (newPrevHeight / parentHeight) * 100;
                const nextPercent = (newNextHeight / parentHeight) * 100;
                prevElement.style.height = `calc(${prevPercent}% - 4px)`;
                nextElement.style.height = `calc(${nextPercent}% - 4px)`;
                startPos = e.clientY;
            }
        } else {
            const delta = e.clientX - startPos;
            const parentWidth = parent.offsetWidth;
            const prevWidth = prevElement.offsetWidth;
            const nextWidth = nextElement.offsetWidth;
            const newPrevWidth = prevWidth + delta;
            const newNextWidth = nextWidth - delta;
            if (newPrevWidth > 200 && newNextWidth > 200) {
                const prevPercent = (newPrevWidth / parentWidth) * 100;
                const nextPercent = (newNextWidth / parentWidth) * 100;
                prevElement.style.width = `${prevPercent}%`;
                nextElement.style.width = `${nextPercent}%`;
                startPos = e.clientX;
            }
        }
    });

    document.addEventListener('mouseup', function() {
        if (isDragging) {
            isDragging = false;
            currentSplitter = null;
            document.body.style.cursor = '';
        }
    });

    initSplitters();

    const observer = new MutationObserver(function() {
        initSplitters();
        schedulePlotlyResize(chartArea);
    });

    const chartArea = document.getElementById('chart-display-area');
    if (chartArea) {
        observer.observe(chartArea, { childList: true, subtree: true });
        
        // ResizeObserver with aggressive throttling for container size changes
        if (window.ResizeObserver) {
            let resizeObserverTimeout = null;
            const resizeObserver = new ResizeObserver(() => {
                const now = Date.now();
                // Throttle ResizeObserver events - only process every 100ms
                if (resizeObserverTimeout) {
                    clearTimeout(resizeObserverTimeout);
                }
                resizeObserverTimeout = setTimeout(() => {
                    cachedGraphs = null; // Invalidate cache when container resizes
                    schedulePlotlyResize(chartArea);
                    resizeObserverTimeout = null;
                }, 100);
            });
            resizeObserver.observe(chartArea);
        }
        
        // Initial resize on load
        schedulePlotlyResize(chartArea);
    }

    // Observe tabs container for tab changes
    const tabsContainer = document.getElementById('tabs');
    if (tabsContainer && chartArea) {
        const tabsObserver = new MutationObserver(function(mutations) {
            // Check if active tab changed (class changes on tab buttons)
            mutations.forEach(function(mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    // Tab was activated, schedule resize with small delay for content render
                    cachedGraphs = null; // Invalidate cache on tab change
                    setTimeout(() => schedulePlotlyResize(chartArea), 50);
                }
            });
        });
        tabsObserver.observe(tabsContainer, { 
            attributes: true, 
            attributeFilter: ['class'],
            subtree: true,
            childList: true
        });
    }

    // Listen for tab clicks (Bootstrap tabs)
    if (chartArea) {
        document.addEventListener('click', function(e) {
            // Check if clicked element is a tab button
            const tabButton = e.target.closest('[role="tab"], .nav-link, [data-bs-toggle="tab"]');
            if (tabButton) {
                cachedGraphs = null; // Invalidate cache on tab click
                // Small delay to allow tab content to render
                setTimeout(() => schedulePlotlyResize(chartArea), 50);
            }
        }, true);
    }

    // Optimized window resize handler - throttled via requestAnimationFrame
    window.addEventListener('resize', function() {
        scheduleWindowResize(chartArea);
    }, { passive: true });
});
