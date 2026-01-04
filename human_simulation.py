"""
Simplified human behavior simulation for a single consistent user profile.
Simulates one user from United States (US East) with consistent fingerprint.
"""
import math
import random
import time
from typing import Tuple, List

from playwright.sync_api import Page, BrowserContext



class HumanBehaviorSimulator:
    """Simulates realistic human behavior patterns to evade bot detection."""

    def __init__(self):
        self.last_action_time = time.time()
        self.action_count = 0

    def get_realistic_delay(self, base_min: float = 0.5, base_max: float = 2.0) -> float:
        """
        Generate realistic delay based on fatigue simulation and natural variance.
        Humans slow down slightly after many actions (fatigue).
        """
        # Simulate fatigue - delays increase slightly with action count
        fatigue_factor = 1.0 + (self.action_count * 0.02)

        # Use log-normal distribution for more realistic human timing
        mean = (base_min + base_max) / 2
        sigma = (base_max - base_min) / 4
        delay = random.lognormvariate(math.log(mean), sigma / mean) * fatigue_factor

        # Clamp to reasonable bounds
        return max(base_min, min(delay, base_max * 2))

    def sleep_like_human(self, min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """Sleep with realistic human timing patterns."""
        delay = self.get_realistic_delay(min_seconds, max_seconds)
        time.sleep(delay)
        self.last_action_time = time.time()
        self.action_count += 1

    def get_bezier_curve_points(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        control_points: int = 2
    ) -> List[Tuple[float, float]]:
        """
        Generate realistic mouse movement path using Bezier curves.
        Humans don't move mouse in straight lines.
        """
        points = []

        # Generate random control points for natural curve
        controls = []
        for _ in range(control_points):
            # Control points deviate from straight line
            t = random.random()
            deviation = random.uniform(20, 100)
            angle = random.uniform(0, 2 * math.pi)

            x = start[0] + t * (end[0] - start[0]) + deviation * math.cos(angle)
            y = start[1] + t * (end[1] - start[1]) + deviation * math.sin(angle)
            controls.append((x, y))

        # Build Bezier curve with all points
        all_points = [start] + controls + [end]

        # Sample points along the curve
        steps = random.randint(15, 30)  # Vary number of steps
        for i in range(steps + 1):
            t = i / steps
            point = self._bezier_point(all_points, t)
            points.append(point)

        return points

    def _bezier_point(self, points: List[Tuple[float, float]], t: float) -> Tuple[float, float]:
        """Calculate point on Bezier curve at parameter t."""
        n = len(points) - 1
        x = sum(
            self._binomial(n, i) * (1 - t) ** (n - i) * t ** i * points[i][0]
            for i in range(n + 1)
        )
        y = sum(
            self._binomial(n, i) * (1 - t) ** (n - i) * t ** i * points[i][1]
            for i in range(n + 1)
        )
        return (x, y)

    def _binomial(self, n: int, k: int) -> int:
        """Calculate binomial coefficient."""
        if k < 0 or k > n:
            return 0
        if k == 0 or k == n:
            return 1
        k = min(k, n - k)
        c = 1
        for i in range(k):
            c = c * (n - i) // (i + 1)
        return c

    def move_mouse_realistically(
        self,
        page: Page,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float
    ) -> None:
        """Move mouse along realistic Bezier curve path with varying speed."""
        points = self.get_bezier_curve_points((start_x, start_y), (end_x, end_y))

        for i, (x, y) in enumerate(points):
            # Vary speed - humans accelerate and decelerate
            if i < len(points) * 0.3:  # Accelerate
                delay = random.uniform(0.01, 0.03)
            elif i > len(points) * 0.7:  # Decelerate near target
                delay = random.uniform(0.02, 0.05)
            else:  # Cruise speed
                delay = random.uniform(0.005, 0.02)

            # Add micro-jitter (human hand tremor)
            jitter_x = x + random.uniform(-1, 1)
            jitter_y = y + random.uniform(-1, 1)

            page.mouse.move(jitter_x, jitter_y)
            time.sleep(delay)

        # Small pause at destination (humans don't click instantly)
        time.sleep(random.uniform(0.05, 0.15))

    def realistic_scroll(self, page: Page, direction: str = "down", distance: int = 300) -> None:
        """Scroll with realistic human patterns - not smooth, has pauses."""
        actual_distance = distance * random.uniform(0.8, 1.2)  # Vary distance
        chunks = random.randint(3, 7)  # Scroll in chunks
        chunk_size = actual_distance / chunks

        for i in range(chunks):
            scroll_amount = chunk_size * random.uniform(0.7, 1.3)
            if direction == "down":
                page.mouse.wheel(0, scroll_amount)
            else:
                page.mouse.wheel(0, -scroll_amount)

            # Variable pauses between scroll chunks
            if i < chunks - 1:
                time.sleep(random.uniform(0.1, 0.4))

        # Pause after scrolling (reading content)
        time.sleep(random.uniform(0.5, 1.5))

    def random_mouse_movement(self, page: Page) -> None:
        """Perform random mouse movement (humans don't keep mouse still)."""
        viewport = page.viewport_size
        if not viewport:
            return

        current_pos = (
            random.randint(0, viewport["width"]),
            random.randint(0, viewport["height"])
        )

        # Random nearby position
        new_x = current_pos[0] + random.randint(-200, 200)
        new_y = current_pos[1] + random.randint(-200, 200)

        # Keep in viewport
        new_x = max(0, min(new_x, viewport["width"]))
        new_y = max(0, min(new_y, viewport["height"]))

        self.move_mouse_realistically(page, current_pos[0], current_pos[1], new_x, new_y)


class SingleUserProfile:
    """
    Consistent browser fingerprint for a single user.
    All values are fixed to simulate the same person using the same device.
    Supports multiple locales: Poland (default) and US East.
    """

    # Locale configurations
    LOCALES = {
        "poland": {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "languages": ["pl-PL", "pl", "en"],
            "timezone": "Europe/Warsaw",
        },
        "us_east": {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "languages": ["en-US", "en"],
            "timezone": "America/New_York",
        }
    }

    VIEWPORT = {"width": 1920, "height": 1080}
    HARDWARE_CONCURRENCY = 8  # 8-core CPU
    DEVICE_MEMORY = 16  # 16 GB RAM

    def __init__(self, locale: str = "poland"):
        """Initialize profile with specified locale."""
        if locale not in self.LOCALES:
            raise ValueError(f"Unsupported locale: {locale}. Available: {list(self.LOCALES.keys())}")
        self.locale = locale
        self.config = self.LOCALES[locale]

    def get_user_agent(self) -> str:
        """Get consistent user agent."""
        return self.config["user_agent"]

    def get_viewport(self) -> dict:
        """Get consistent viewport size."""
        return self.VIEWPORT

    def get_languages(self) -> list:
        """Get consistent language preferences."""
        return self.config["languages"]

    def get_timezone(self) -> str:
        """Get consistent timezone for selected locale."""
        return self.config["timezone"]

    @classmethod
    def get_canvas_noise_script(cls) -> str:
        """Inject subtle noise into canvas to prevent fingerprinting."""
        return """
        // Canvas fingerprinting protection
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        const originalToBlob = HTMLCanvasElement.prototype.toBlob;
        const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
        
        const noise = () => {
            return Math.random() * 0.0001;
        };
        
        HTMLCanvasElement.prototype.toDataURL = function(type) {
            const context = this.getContext('2d');
            const imageData = context.getImageData(0, 0, this.width, this.height);
            for (let i = 0; i < imageData.data.length; i += 4) {
                imageData.data[i] += noise();
                imageData.data[i + 1] += noise();
                imageData.data[i + 2] += noise();
            }
            context.putImageData(imageData, 0, 0);
            return originalToDataURL.apply(this, arguments);
        };
        
        CanvasRenderingContext2D.prototype.getImageData = function() {
            const imageData = originalGetImageData.apply(this, arguments);
            for (let i = 0; i < imageData.data.length; i += 4) {
                imageData.data[i] += noise();
                imageData.data[i + 1] += noise();
                imageData.data[i + 2] += noise();
            }
            return imageData;
        };
        """

    @classmethod
    def get_webgl_noise_script(cls) -> str:
        """Inject noise into WebGL to prevent fingerprinting."""
        return """
        // WebGL fingerprinting protection
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) {
                return 'Intel Inc.';
            }
            if (parameter === 37446) {
                return 'Intel Iris OpenGL Engine';
            }
            return getParameter.apply(this, arguments);
        };
        
        const getSupportedExtensions = WebGLRenderingContext.prototype.getSupportedExtensions;
        WebGLRenderingContext.prototype.getSupportedExtensions = function() {
            const extensions = getSupportedExtensions.apply(this, arguments);
            return extensions.filter(ext => !ext.includes('WEBGL_debug'));
        };
        """

    @classmethod
    def get_comprehensive_stealth_script(cls) -> str:
        """Get comprehensive stealth script to mask all automation markers."""
        return """
        // Override navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Mock plugins with realistic data
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    {name: 'Chrome PDF Plugin', description: 'Portable Document Format', filename: 'internal-pdf-viewer'},
                    {name: 'Chrome PDF Viewer', description: '', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                    {name: 'Native Client', description: '', filename: 'internal-nacl-plugin'}
                ];
                Object.setPrototypeOf(plugins, PluginArray.prototype);
                return plugins;
            }
        });
        
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Mock chrome object
        window.chrome = {
            runtime: {
                connect: () => {},
                sendMessage: () => {},
                onMessage: {
                    addListener: () => {},
                    removeListener: () => {}
                }
            },
            loadTimes: function() {},
            csi: function() {}
        };
        
        // Mock connection type
        Object.defineProperty(navigator, 'connection', {
            get: () => ({
                effectiveType: '4g',
                downlink: 10,
                rtt: 50
            })
        });
        
        // Mock hardware concurrency with consistent value
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => """ + str(cls.HARDWARE_CONCURRENCY) + """
        });
        
        // Mock device memory with consistent value
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => """ + str(cls.DEVICE_MEMORY) + """
        });
        
        // Override toString to hide modifications
        const originalToString = Function.prototype.toString;
        Function.prototype.toString = function() {
            if (this === navigator.webdriver || 
                this === navigator.plugins || 
                this === navigator.languages) {
                return 'function get() { [native code] }';
            }
            return originalToString.apply(this, arguments);
        };
        
        // Battery API with consistent values
        navigator.getBattery = async () => ({
            charging: true,
            chargingTime: 0,
            dischargingTime: Infinity,
            level: 0.85,
            addEventListener: () => {},
            removeEventListener: () => {}
        });
        
        // Media devices
        navigator.mediaDevices.enumerateDevices = async () => [
            {deviceId: 'default', kind: 'audioinput', label: 'Default - Microphone', groupId: '1'},
            {deviceId: 'default', kind: 'audiooutput', label: 'Default - Speaker', groupId: '1'},
            {deviceId: 'default', kind: 'videoinput', label: 'Default - Camera', groupId: '2'}
        ];
        """


def inject_stealth_scripts(context: BrowserContext, locale: str = "poland") -> None:
    """Inject all stealth scripts into browser context."""
    profile = SingleUserProfile(locale=locale)

    # Comprehensive stealth script
    context.add_init_script(profile.get_comprehensive_stealth_script())

    # Canvas noise
    context.add_init_script(profile.get_canvas_noise_script())

    # WebGL noise
    context.add_init_script(profile.get_webgl_noise_script())

