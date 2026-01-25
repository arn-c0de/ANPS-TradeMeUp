/**
 * Suppress React deprecation warnings in console.
 * Must run before React/Dash scripts load.
 */
(function() {
    const suppressedPatterns = [
        /Support for defaultProps will be removed/i,
        /componentWillReceiveProps has been renamed/i,
        /componentWillMount has been renamed/i,
        /findDOMNode is deprecated/i,
        /Download the React DevTools/i,
        /UNSAFE_componentWillReceiveProps/i,
        /UNSAFE_componentWillMount/i
    ];

    const originalWarn = console.warn || function(){};
    console.warn = function(...args) {
        const message = args.join(' ');
        if (suppressedPatterns.some(pattern => pattern.test(message))) {
            return;
        }
        originalWarn.apply(console, args);
    };

    const originalError = console.error || function(){};
    console.error = function(...args) {
        const message = args.join(' ');
        if (suppressedPatterns.some(pattern => pattern.test(message)) &&
            (message.includes('Warning:') || message.includes('deprecated'))) {
            return;
        }
        originalError.apply(console, args);
    };
})();
