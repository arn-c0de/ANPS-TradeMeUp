// Infinite scroll detection for entity lists
(function() {
    function setupScrollListeners() {
        // Setup positive entities scroll listener
        const positiveContainer = document.getElementById('top-positive-entities');
        if (positiveContainer && !positiveContainer.scrollListenerSetup) {
            positiveContainer.scrollListenerSetup = true;
            let isLoading = false;
            
            positiveContainer.addEventListener('scroll', function() {
                if (isLoading) return;
                
                const scrollTop = positiveContainer.scrollTop;
                const scrollHeight = positiveContainer.scrollHeight;
                const clientHeight = positiveContainer.clientHeight;
                
                // Check if scrolled to bottom (within 100px)
                if (scrollTop + clientHeight >= scrollHeight - 100) {
                    isLoading = true;
                    
                    // Update the scroll trigger input to trigger callback
                    const trigger = document.getElementById('positive-entities-scroll-trigger');
                    if (trigger) {
                        const currentValue = parseInt(trigger.value) || 0;
                        trigger.value = (currentValue + 1).toString();
                        // Trigger change event
                        const event = new Event('change', { bubbles: true });
                        trigger.dispatchEvent(event);
                    }
                    
                    // Reset loading flag after a delay
                    setTimeout(function() {
                        isLoading = false;
                    }, 1000);
                }
            }, { passive: true });
        }
        
        // Setup negative entities scroll listener
        const negativeContainer = document.getElementById('top-negative-entities');
        if (negativeContainer && !negativeContainer.scrollListenerSetup) {
            negativeContainer.scrollListenerSetup = true;
            let isLoading = false;
            
            negativeContainer.addEventListener('scroll', function() {
                if (isLoading) return;
                
                const scrollTop = negativeContainer.scrollTop;
                const scrollHeight = negativeContainer.scrollHeight;
                const clientHeight = negativeContainer.clientHeight;
                
                // Check if scrolled to bottom (within 100px)
                if (scrollTop + clientHeight >= scrollHeight - 100) {
                    isLoading = true;
                    
                    // Update the scroll trigger input to trigger callback
                    const trigger = document.getElementById('negative-entities-scroll-trigger');
                    if (trigger) {
                        const currentValue = parseInt(trigger.value) || 0;
                        trigger.value = (currentValue + 1).toString();
                        // Trigger change event
                        const event = new Event('change', { bubbles: true });
                        trigger.dispatchEvent(event);
                    }
                    
                    // Reset loading flag after a delay
                    setTimeout(function() {
                        isLoading = false;
                    }, 1000);
                }
            }, { passive: true });
        }
    }
    
    // Run setup when DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setupScrollListeners);
    } else {
        setupScrollListeners();
    }
    
    // Also run setup after a delay to catch dynamically added elements
    setTimeout(setupScrollListeners, 1000);
    
    // Watch for new elements being added
    const observer = new MutationObserver(function(mutations) {
        let shouldSetup = false;
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) {
                    if (node.id === 'top-positive-entities' || 
                        node.id === 'top-negative-entities' ||
                        node.querySelector && (
                            node.querySelector('#top-positive-entities') ||
                            node.querySelector('#top-negative-entities')
                        )) {
                        shouldSetup = true;
                    }
                }
            });
        });
        if (shouldSetup) {
            setTimeout(setupScrollListeners, 100);
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
})();
