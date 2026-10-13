// Pass-through service worker: exists only so Android (Samsung Internet/Chrome) installs the site
// as a real app instead of a browser shortcut with the browser badge. No caching on purpose.
self.addEventListener("fetch", () => {});
