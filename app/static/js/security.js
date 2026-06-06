(() => {
    const token = document.querySelector('meta[name="csrf-token"]')?.content || "";
    if (!token) return;

    const originalFetch = window.fetch;
    window.fetch = (input, init = {}) => {
        const method = (init.method || "GET").toUpperCase();
        if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
            const headers = new Headers(init.headers || {});
            headers.set("X-CSRF-Token", token);
            init.headers = headers;
        }
        return originalFetch(input, init);
    };
})();
