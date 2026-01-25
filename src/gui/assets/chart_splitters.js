/**
 * Drag-to-resize functionality for chart splitters.
 * Load after Plotly (e.g. after {%scripts%}).
 */
document.addEventListener('DOMContentLoaded', function() {
    let isDragging = false;
    let currentSplitter = null;
    let startPos = 0;
    let resizeRaf = null;

    function resizePlotlyCharts(scope) {
        if (!window.Plotly || !Plotly.Plots || !Plotly.Plots.resize) return;
        const root = scope || document;
        const graphs = root.querySelectorAll('.js-plotly-plot');
        graphs.forEach(graph => {
            if (!graph || graph.offsetParent === null) return;
            try {
                Plotly.Plots.resize(graph);
            } catch (err) {
                /* ignore resize errors for detached nodes */
            }
        });
    }

    function schedulePlotlyResize(scope) {
        if (resizeRaf) return;
        resizeRaf = window.requestAnimationFrame(() => {
            resizeRaf = null;
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
        if (window.ResizeObserver) {
            const resizeObserver = new ResizeObserver(() => schedulePlotlyResize(chartArea));
            resizeObserver.observe(chartArea);
        }
        schedulePlotlyResize(chartArea);
        setTimeout(() => schedulePlotlyResize(chartArea), 50);
        setTimeout(() => schedulePlotlyResize(chartArea), 250);
    }

    // Observe tabs container for tab changes
    const tabsContainer = document.getElementById('tabs');
    if (tabsContainer && chartArea) {
        const tabsObserver = new MutationObserver(function(mutations) {
            // Check if active tab changed (class changes on tab buttons)
            mutations.forEach(function(mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    // Tab was activated, schedule resize
                    schedulePlotlyResize(chartArea);
                    // Additional delayed resizes for reliable behavior
                    setTimeout(() => schedulePlotlyResize(chartArea), 50);
                    setTimeout(() => schedulePlotlyResize(chartArea), 250);
                    setTimeout(() => schedulePlotlyResize(chartArea), 500);
                    setTimeout(() => schedulePlotlyResize(chartArea), 1000);
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
                // Small delay to allow tab content to render
                setTimeout(() => {
                    schedulePlotlyResize(chartArea);
                }, 100);
                // Additional delayed resizes
                setTimeout(() => schedulePlotlyResize(chartArea), 250);
                setTimeout(() => schedulePlotlyResize(chartArea), 500);
                setTimeout(() => schedulePlotlyResize(chartArea), 1000);
            }
        }, true);
    }

    window.addEventListener('resize', function() {
        schedulePlotlyResize(chartArea);
    });
});
