// Add word-break opportunities after periods in module paths
document.addEventListener('DOMContentLoaded', function() {
    // Target module path titles in headings, navigation, and sidebars
    const selectors = [
        'h1 code.xref.py.py-mod span.pre',
        'h2 code.xref.py.py-mod span.pre',
        'h3 code.xref.py.py-mod span.pre',
        '.prev-next-title code.xref.py.py-mod span.pre',
        '.sidebar code.xref.py.py-mod span.pre',
        '.toctree code.xref.py.py-mod span.pre',
        'nav code.xref.py.py-mod span.pre'
    ];

    selectors.forEach(function(selector) {
        document.querySelectorAll(selector).forEach(function(element) {
            // Replace periods with period + word break opportunity for better breaking
            element.innerHTML = element.textContent.replace(/\./g, '.<wbr>');
        });
    });

    // Add class to long module name links for targeted styling
    // This handles the case where .current links have href="#" instead of the module path
    document.querySelectorAll('.bd-links .toctree-l4 > a').forEach(function(link) {
        const codeElement = link.querySelector('code.xref.py.py-mod span.pre');
        if (codeElement && (codeElement.textContent.includes('xml_serialization') ||
                            codeElement.textContent.includes('nexusLIMS.harvesters.reservation_event'))) {
            link.classList.add('long-text-link');
        }
    });
});
