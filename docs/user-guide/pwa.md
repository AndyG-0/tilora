# Personal Web App (PWA)

Tilora includes native support for running as a **Progressive Web App (PWA)** / **Personal Web App**. This allows you to install Tilora directly to your home screen or desktop, running in an immersive, standalone window with instant caching and no browser address bar clutter.

---

## Why Use Tilora as a PWA?

- **Fullscreen Standalone Experience**: Removes browser URL bars, navigation tabs, and bookmarks bars, turning tablets, phones, or dedicated monitors into seamless smart displays.
- **Home Screen & App Drawer Launch**: Launch Tilora with a single tap from your iOS home screen, Android launcher, macOS Dock, or Windows Start menu.
- **Safe-Area Inset Handling**: Automatically accommodates device notches, dynamic islands, and home-indicator gestures on modern mobile devices.
- **Instant App Shell Loading**: Pre-caches static client assets, stylesheets, fonts, and icons so the application shell launches instantly.
- **Automatic Background Updates**: When a new version of Tilora is deployed, the app downloads updates in the background and offers a one-click update reload.

---

## Installing on Different Devices

### Apple iOS & iPadOS (iPhone / iPad)

1. Open **Safari** and navigate to your Tilora instance (e.g., `https://tilora.local` or `http://localhost:5173`).
2. Tap the **Share** button (the square icon with an upward arrow) in the Safari toolbar.
3. Scroll down and select **Add to Home Screen**.
4. (Optional) Customize the name and tap **Add** in the top-right corner.
5. Tilora will now appear on your home screen with its custom icon and run in fullscreen standalone mode.

> [!TIP]
> On iPad, installing as a PWA and enabling **Guided Access** creates an ideal dedicated wall mount dashboard for kitchens, entryways, or living rooms.

---

### Android & Google Chrome

1. Open **Google Chrome** (or Edge / Samsung Internet / Brave) and navigate to your Tilora instance.
2. If prompted at the bottom of the screen, tap **Install Tilora** or **Add Tilora to Home screen**.
3. Alternatively, tap the **three-dot menu** (`⋮`) in the top right and select **Install app** or **Add to Home screen**.
4. Tap **Install** to confirm. The Tilora icon will be added to your home screen and app drawer.

---

### Desktop (macOS, Windows, Linux)

1. Open your Tilora instance in **Google Chrome**, **Microsoft Edge**, or **Brave**.
2. Click the **Install Tilora** icon on the right side of the browser's address bar (or go to **Settings** in Tilora and click **Install Tilora App**).
3. Click **Install**.
4. Tilora will open in its own standalone window and appear in your operating system's application launcher and dock/taskbar.

---

## Service Worker & Caching Behavior

Tilora uses a customized service worker caching strategy optimized for smart home dashboards:

| Request Category | Caching Strategy | Description |
|---|---|---|
| **Immutable Assets** (`_app/immutable/*`) | **Cache-First** | Scripts and styles are content-hashed and served directly from cache for instant loads. |
| **Static Files & Icons** (`/icons/*`, fonts) | **Cache-First** | App icons, manifest, and web fonts load immediately. |
| **Navigation Requests** (HTML pages) | **Network-First with Shell Fallback** | Always attempts to fetch latest HTML; falls back to cached app shell if offline. |
| **Dynamic API Data** (`/api/*`) | **Network-Only** | Sensor telemetry, weather, live stats, and AI responses are never cached stale. |
| **Live Media Streams** (`.m3u8`, `.ts`, video) | **Network-Only** | TV and camera streams bypass service worker caching for low-latency playback. |

---

## Updating the PWA

When you update your Tilora backend and frontend:
1. The Service Worker automatically detects the new build in the background and caches the updated bundles.
2. An unobtrusive toast notification will appear in the bottom-right corner: **"A new version of Tilora is available. [Update]"**.
3. Clicking **Update** immediately applies the new version and refreshes the application.
