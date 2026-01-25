// Chart Timestamps Module
// Handles timestamp formatting and metadata display (center timestamp, last candle, last update)
(function() {
    'use strict';
    
    try {
        /**
         * Format timestamp in de-DE locale
         * Handles different timestamp formats (Date, string, number)
         */
        function formatTimestamp(rawTimestamp) {
        if (!rawTimestamp) return '';
        
        // Handle different timestamp formats
        let date;
        if (rawTimestamp instanceof Date) {
            date = rawTimestamp;
        } else if (typeof rawTimestamp === 'string') {
            date = new Date(rawTimestamp);
        } else if (typeof rawTimestamp === 'number') {
            // Could be Unix timestamp (seconds or milliseconds)
            date = new Date(rawTimestamp > 1e10 ? rawTimestamp : rawTimestamp * 1000);
        } else {
            date = new Date(rawTimestamp);
        }

        // Format timestamp - parse string directly to avoid timezone conversion
        if (isNaN(date.getTime())) {
            return '';
        }
        
        if (typeof rawTimestamp === 'string' && rawTimestamp.includes('T')) {
            // Parse the timestamp string manually to get the local time components
            const match = rawTimestamp.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/);
            if (match) {
                const [_, year, month, day, hour, minute, second] = match;
                // Format using the parsed local time (not converted to browser timezone)
                return `${day}.${month}.${year}, ${hour}:${minute}`;
            } else {
                // Fallback to regular formatting
                return date.toLocaleString('de-DE', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            }
        } else {
            // For Date objects or numeric timestamps, use regular formatting
            return date.toLocaleString('de-DE', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        }
    }
    
    /**
     * Get last candle/point timestamp from trace data
     * Returns formatted timestamp string
     */
    function getLastCandleTimestamp(trace) {
        if (!trace || !trace.x || trace.x.length === 0) {
            return '';
        }
        
        try {
            const lastRawTimestamp = trace.x[trace.x.length - 1];
            return formatTimestamp(lastRawTimestamp);
        } catch (e) {
            console.warn('[Chart Timestamps] Could not get last candle timestamp:', e);
            return '';
        }
    }
    
    /**
     * Get last update time from data-last-update attribute
     * Checks graphElement and parent elements for wrapped graphs
     */
    function getLastUpdateTime(graphElement) {
        if (!graphElement) return null;
        
        // Get last update time - check graphElement and its parents for data-last-update
        let lastUpdateAttr = graphElement.getAttribute('data-last-update');
        if (!lastUpdateAttr) {
            // Check parent elements (for wrapped graphs)
            let parent = graphElement.parentElement;
            let depth = 0;
            while (parent && depth < 5 && !lastUpdateAttr) {
                lastUpdateAttr = parent.getAttribute('data-last-update');
                parent = parent.parentElement;
                depth++;
            }
        }
        
        if (!lastUpdateAttr) {
            return null;
        }
        
        try {
            // Parse timestamp (ISO format or Unix timestamp)
            let date;
            if (lastUpdateAttr.includes('T') || lastUpdateAttr.includes('-')) {
                // ISO format string
                date = new Date(lastUpdateAttr);
            } else {
                // Unix timestamp (seconds or milliseconds)
                const timestamp = parseFloat(lastUpdateAttr);
                date = new Date(timestamp > 1e10 ? timestamp : timestamp * 1000);
            }

            if (!isNaN(date.getTime())) {
                return date;
            }
        } catch (e) {
            console.warn('[Chart Timestamps] Could not parse last update time:', e);
        }
        
        return null;
    }
    
    /**
     * Update center line timestamp (without Plotly relayout!)
     * Updates center timestamp label and last update label
     */
    function updateCenterLineTimestamp(graphDiv, graphElement, graphId) {
        if (!graphDiv || !graphDiv._fullLayout || !graphDiv._fullData) {
            return false;
        }

        const layout = graphDiv._fullLayout;
        const xaxis = layout.xaxis;

        // Get trace data first
        let trace = null;
        try {
            // Try to find candlestick trace first, then scatter/line trace
            trace = graphDiv._fullData.find(trace => trace.type === 'candlestick');
            if (!trace || !trace.x || trace.x.length === 0) {
                trace = graphDiv._fullData.find(trace => trace.type === 'scatter' && trace.mode && trace.mode.includes('lines'));
            }
            if (!trace || !trace.x || trace.x.length === 0) {
                // Fallback to first trace with x data
                trace = graphDiv._fullData.find(trace => trace.x && trace.x.length > 0);
            }
            
            if (!trace || !trace.x || trace.x.length === 0) {
                return false;
            }
        } catch (e) {
            return false;
        }

        const xData = trace.x;

        // Get timestamp from data at center of visible range
        let timestamp = '';
        let centerIndex = -1;

        // Check if xaxis.range is available, otherwise use fallback
        if (xaxis && xaxis.range && Array.isArray(xaxis.range) && xaxis.range.length === 2) {
            const range = xaxis.range;

            // For category-type x-axis with numeric range values (indices)
            if (typeof range[0] === 'number' && typeof range[1] === 'number') {
                // Range contains numeric indices (0, 1, 2, ...)
                centerIndex = Math.round((range[0] + range[1]) / 2);

                // Clamp to valid range
                if (centerIndex < 0) centerIndex = 0;
                if (centerIndex >= xData.length) centerIndex = xData.length - 1;
            } else {
                // Range contains category values (timestamps) - need to find index
                const centerValue = range[0] + (range[1] - range[0]) / 2;

                // Find closest index
                for (let i = 0; i < xData.length; i++) {
                    if (xData[i] === centerValue || String(xData[i]) === String(centerValue)) {
                        centerIndex = i;
                        break;
                    }
                }

                // If exact match not found, use midpoint index as fallback
                if (centerIndex === -1) {
                    centerIndex = Math.floor(xData.length / 2);
                }
            }
        } else {
            // Fallback: use midpoint of data if range is not available
            centerIndex = Math.floor(xData.length / 2);
        }

        // Get timestamp at center index
        if (centerIndex >= 0 && centerIndex < xData.length) {
            const rawTimestamp = xData[centerIndex];
            timestamp = formatTimestamp(rawTimestamp);
        }

        // Update center timestamp label (at top of line, inside chart)
        const plotContainer = graphElement.querySelector('.js-plotly-plot');
        const centerLabel = plotContainer ? plotContainer.querySelector('.chart-center-timestamp') : null;
        if (centerLabel) {
            let labelText = timestamp || '';
            
            // Get last candle timestamp
            const lastCandleTimestamp = getLastCandleTimestamp(trace);
            
            // Add last candle timestamp if available
            if (lastCandleTimestamp) {
                // Determine chart type for label
                const chartType = graphDiv._fullData.find(trace => trace.type === 'candlestick') ? 'candle' : 'point';
                if (labelText) {
                    labelText += ` | Last ${chartType}: ${lastCandleTimestamp}`;
                } else {
                    labelText = `Last ${chartType}: ${lastCandleTimestamp}`;
                }
            }
            
            centerLabel.textContent = labelText;
        }

        // Update last update label (at top, behind symbol)
        const lastUpdateLabel = graphElement.querySelector('.chart-last-update');
        if (lastUpdateLabel) {
            const lastUpdateDate = getLastUpdateTime(graphElement);
            
            if (lastUpdateDate) {
                // Format as "DD.MM.YYYY, HH:MM"
                const formatted = formatTimestamp(lastUpdateDate);
                lastUpdateLabel.textContent = `Last update: ${formatted}`;
            } else {
                lastUpdateLabel.textContent = '';
            }
        }

            return timestamp !== '';
        }
        
        // Export functions immediately
        window.ChartTimestamps = {
            formatTimestamp: formatTimestamp,
            getLastCandleTimestamp: getLastCandleTimestamp,
            getLastUpdateTime: getLastUpdateTime,
            updateCenterLineTimestamp: updateCenterLineTimestamp
        };
        
        // Log successful initialization
        if (console && console.log) {
            console.log('[Chart Timestamps] Module loaded successfully');
        }
    } catch (error) {
        // Log error but still export a minimal fallback
        console.error('[Chart Timestamps] Error initializing module:', error);
        window.ChartTimestamps = {
            formatTimestamp: function(rawTimestamp) { return ''; },
            getLastCandleTimestamp: function(trace) { return ''; },
            getLastUpdateTime: function(graphElement) { return null; },
            updateCenterLineTimestamp: function(graphDiv, graphElement, graphId) {
                console.warn('[Chart Timestamps] Using fallback - module initialization failed');
                return false;
            }
        };
    }
    
})();
