(() => {
    const LABEL_CLASS = "overlay-drag-label";
    const ATTACHED_KEY = "__overlayDragAttached";

    function formatPrice(value) {
        const num = typeof value === "number" ? value : parseFloat(value);
        if (!Number.isFinite(num)) {
            return null;
        }
        return `$${num.toFixed(2)}`;
    }

    function extractShapeValue(eventData) {
        if (!eventData) {
            return null;
        }
        const keys = Object.keys(eventData);
        for (const key of keys) {
            if (key.startsWith("shapes[") && (key.endsWith(".y0") || key.endsWith(".y1"))) {
                return eventData[key];
            }
        }
        return null;
    }

    function attachOverlayDragLabel(graph) {
        if (!graph || graph[ATTACHED_KEY]) {
            return;
        }
        if (typeof graph.on !== "function") {
            setTimeout(() => attachOverlayDragLabel(graph), 200);
            return;
        }

        graph[ATTACHED_KEY] = true;
        console.log("[Overlay Drag] Attached to graph:", graph.id);

        const label = document.createElement("div");
        label.className = LABEL_CLASS;
        label.style.display = "none";
        label.style.pointerEvents = "none";
        graph.appendChild(label);

        let lastPos = { x: 0, y: 0 };
        let hideTimer = null;

        function positionLabel() {
            label.style.transform = `translate(${lastPos.x + 12}px, ${lastPos.y + 12}px)`;
        }

        function showLabel(text) {
            clearTimeout(hideTimer);
            label.textContent = text;
            label.style.display = "block";
            positionLabel();
        }

        function scheduleHide() {
            clearTimeout(hideTimer);
            hideTimer = setTimeout(() => {
                label.style.display = "none";
            }, 500);
        }

        graph.addEventListener("mousemove", (event) => {
            const rect = graph.getBoundingClientRect();
            lastPos = {
                x: event.clientX - rect.left,
                y: event.clientY - rect.top
            };
            if (label.style.display === "block") {
                positionLabel();
            }
        });

        graph.addEventListener("mouseleave", scheduleHide);

        graph.on("plotly_relayouting", (eventData) => {
            console.log("[Overlay Drag] plotly_relayouting event:", eventData);
            const value = extractShapeValue(eventData);
            console.log("[Overlay Drag] Extracted value:", value);
            const text = formatPrice(value);
            if (text) {
                console.log("[Overlay Drag] Showing label:", text);
                showLabel(text);
            }
        });

        graph.on("plotly_relayout", (eventData) => {
            console.log("[Overlay Drag] plotly_relayout event (hiding label)");
            scheduleHide();
        });
    }

    function scanGraphs() {
        document.querySelectorAll(".js-plotly-plot").forEach(attachOverlayDragLabel);
    }

    // Debounce helper to prevent excessive scanning
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    function init() {
        scanGraphs();

        // Debounced version - only scan after DOM changes settle (300ms delay)
        const debouncedScan = debounce(scanGraphs, 300);

        const observer = new MutationObserver((mutations) => {
            // Only react if plotly-related elements are added
            const hasRelevantChanges = mutations.some(mutation => {
                return Array.from(mutation.addedNodes).some(node => {
                    return node.nodeType === 1 && (
                        node.classList?.contains('js-plotly-plot') ||
                        node.querySelector?.('.js-plotly-plot')
                    );
                });
            });

            if (hasRelevantChanges) {
                debouncedScan();
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
