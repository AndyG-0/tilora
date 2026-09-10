import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('$env/dynamic/public', () => ({ env: { PUBLIC_API_BASE_URL: 'http://api.test' } }));

const { api, apiUrl, describeFetchError } = await import('./api');

describe('api', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it('listWidgets fetches from the configured base URL', async () => {
		const widgets = [
			{ id: 'weather', type: 'weather', layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 }, tab: 'default' },
		];
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => widgets }));

		const result = await api.listWidgets('wide');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/widgets?breakpoint=wide', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual(widgets);
	});

	it('widgetSummary fetches the widget-specific summary endpoint', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ temp: 72 }) }));

		const result = await api.widgetSummary('weather');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/widgets/weather/summary', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual({ temp: 72 });
	});

	it('widgetDetail fetches the widget-specific detail endpoint', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ detail: true }) }));

		await api.widgetDetail('ai-insights');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/widgets/ai-insights/detail', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
	});

	it('themes fetches the theme endpoint', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue({ ok: true, json: async () => ({ themes: [], default: 'dark' }) }),
		);

		const result = await api.themes();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/theme', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual({ themes: [], default: 'dark' });
	});

	it('tabs fetches the tabs endpoint', async () => {
		const tabs = [{ id: 'default', name: 'Dashboard' }];
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => tabs }));

		const result = await api.tabs();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/tabs', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual(tabs);
	});

	it('searchCities fetches the weather search endpoint with the query encoded', async () => {
		const results = [
			{ name: 'Fort Worth', admin1: 'Texas', country: 'United States', latitude: 32.7555, longitude: -97.3308 },
		];
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => results }));

		const result = await api.searchCities('Fort Worth');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/weather/search?q=Fort%20Worth', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual(results);
	});

	it('updateWidgetSettings PATCHes the widget settings endpoint with a JSON body', async () => {
		const updated = { latitude: 32.7555, longitude: -97.3308, location_name: 'Fort Worth, Texas' };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => updated }));

		const result = await api.updateWidgetSettings('weather', updated);

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/widgets/weather/settings', {
			signal: expect.any(AbortSignal),
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(updated),
			credentials: 'include',
		});
		expect(result).toEqual(updated);
	});

	it('runAiWidget POSTs to the widget run endpoint', async () => {
		const result = { text: 'Fresh briefing' };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => result }));

		const response = await api.runAiWidget('ai-insights');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/widgets/ai-insights/run', {
			signal: expect.any(AbortSignal),
			method: 'POST',
			credentials: 'include',
		});
		expect(response).toEqual(result);
	});

	it('settings fetches the settings endpoint', async () => {
		const settings = {
			ai_model: 'anthropic/claude-sonnet-5',
			timezone: 'UTC',
			has_anthropic_api_key: true,
			has_openai_api_key: false,
			has_gemini_api_key: false,
		};
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => settings }));

		const result = await api.settings();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/settings', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual(settings);
	});

	it('updateSettings PATCHes the settings endpoint with a JSON body', async () => {
		const partial = { timezone: 'America/Chicago' };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => partial }));

		await api.updateSettings(partial);

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/settings', {
			signal: expect.any(AbortSignal),
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(partial),
			credentials: 'include',
		});
	});

	it('version fetches the version endpoint', async () => {
		const info = {
			current_version: '0.1.0',
			latest_version: '0.2.0',
			update_available: true,
			release_url: 'https://github.com/AndyG-0/tilora/releases/tag/v0.2.0',
		};
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => info }));

		const result = await api.version();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/version', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual(info);
	});

	it('throws a descriptive error when the response is not ok', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }));

		await expect(api.widgetSummary('weather')).rejects.toThrow('Request to /api/widgets/weather/summary failed: 500');
	});

	it('registerDevice POSTs to the device register endpoint', async () => {
		const result = { id: 'dev1', name: 'New Device', is_new: true };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => result }));

		const response = await api.registerDevice();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/devices/register', {
			signal: expect.any(AbortSignal),
			method: 'POST',
			credentials: 'include',
		});
		expect(response).toEqual(result);
	});

	it('currentDevice fetches the current device endpoint', async () => {
		const device = { id: 'dev1', name: 'Kitchen Tablet' };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => device }));

		const result = await api.currentDevice();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/devices/me', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual(device);
	});

	it('renameDevice PATCHes the current device endpoint with the new name', async () => {
		const device = { id: 'dev1', name: 'Kitchen Tablet' };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => device }));

		const result = await api.renameDevice('Kitchen Tablet');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/devices/me', {
			signal: expect.any(AbortSignal),
			method: 'PATCH',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'Kitchen Tablet' }),
		});
		expect(result).toEqual(device);
	});

	it('listDevices fetches the devices endpoint', async () => {
		const devices = [{ id: 'dev1', name: 'Kitchen Tablet', last_seen_at: '2026-01-01T00:00:00Z' }];
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => devices }));

		const result = await api.listDevices();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/devices', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual(devices);
	});

	it('deleteDevice DELETEs the given device endpoint', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }));

		await api.deleteDevice('dev1');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/devices/dev1', {
			signal: expect.any(AbortSignal),
			method: 'DELETE',
			credentials: 'include',
		});
	});

	it('updateWidgetsLayout PUTs the widgets and breakpoint to the layout endpoint', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }));
		const widgets = [{ id: 'weather', layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 } }];

		await api.updateWidgetsLayout(widgets, 'narrow');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/widgets/layout', {
			signal: expect.any(AbortSignal),
			method: 'PUT',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ widgets, breakpoint: 'narrow' }),
		});
	});

	it('listUsers fetches the users endpoint', async () => {
		const profiles = [{ id: 'default', name: 'Default', avatar: null, has_pin: false }];
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => profiles }));

		const result = await api.listUsers();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/users', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual(profiles);
	});

	it('createUser POSTs the name, and omits avatar/pin when not provided', async () => {
		const me = { id: 'u1', name: 'Alice', avatar: null };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => me }));

		const result = await api.createUser('Alice');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/users', {
			signal: expect.any(AbortSignal),
			method: 'POST',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'Alice' }),
		});
		expect(result).toEqual(me);
	});

	it('createUser includes avatar and pin when provided', async () => {
		const me = { id: 'u1', name: 'Alice', avatar: '🐱' };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => me }));

		await api.createUser('Alice', '🐱', '1234');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/users', {
			signal: expect.any(AbortSignal),
			method: 'POST',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'Alice', avatar: '🐱', pin: '1234' }),
		});
	});

	it('loginUser POSTs a JSON body even when no PIN is given, since the backend requires one', async () => {
		const me = { id: 'u1', name: 'Alice', avatar: null };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => me }));

		const result = await api.loginUser('u1');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/users/u1/login', {
			signal: expect.any(AbortSignal),
			method: 'POST',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({}),
		});
		expect(result).toEqual(me);
	});

	it('loginUser sends the PIN when provided', async () => {
		const me = { id: 'u1', name: 'Alice', avatar: null };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => me }));

		await api.loginUser('u1', '1234');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/users/u1/login', {
			signal: expect.any(AbortSignal),
			method: 'POST',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ pin: '1234' }),
		});
	});

	it('logoutUser POSTs to the logout endpoint', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }));

		await api.logoutUser();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/users/logout', {
			signal: expect.any(AbortSignal),
			method: 'POST',
			credentials: 'include',
		});
	});

	it('currentUser fetches the current user endpoint', async () => {
		const me = { id: 'u1', name: 'Alice', avatar: null };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => me }));

		const result = await api.currentUser();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/users/me', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual(me);
	});

	it('updateUser PATCHes the current user endpoint', async () => {
		const me = { id: 'u1', name: 'Alicia', avatar: null };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => me }));

		const result = await api.updateUser({ name: 'Alicia' });

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/users/me', {
			signal: expect.any(AbortSignal),
			method: 'PATCH',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'Alicia' }),
		});
		expect(result).toEqual(me);
	});

	it('deleteUser DELETEs the current user endpoint', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }));

		await api.deleteUser();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/users/me', {
			signal: expect.any(AbortSignal),
			method: 'DELETE',
			credentials: 'include',
		});
	});

	it('getPreferences fetches the current user preferences endpoint', async () => {
		const prefs = { theme: 'sepia' };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => prefs }));

		const result = await api.getPreferences();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/users/me/preferences', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual(prefs);
	});

	it('updatePreferences PATCHes the current user preferences endpoint', async () => {
		const prefs = { theme: 'sepia' };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => prefs }));

		const result = await api.updatePreferences({ theme: 'sepia' });

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/users/me/preferences', {
			signal: expect.any(AbortSignal),
			method: 'PATCH',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ theme: 'sepia' }),
		});
		expect(result).toEqual(prefs);
	});

	it('ttsVoices fetches the tts voices endpoint', async () => {
		const voices = [{ id: 'nova', label: 'Nova', provider: 'openai' }];
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => voices }));

		const result = await api.ttsVoices();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/tts/voices', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual(voices);
	});

	it('synthesizeSpeech POSTs the provider, voice id, and text and returns a blob', async () => {
		const blob = new Blob(['audio-bytes']);
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, blob: async () => blob }));

		const result = await api.synthesizeSpeech('openai', 'nova', 'hello there');

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/tts/synthesize', {
			signal: expect.any(AbortSignal),
			method: 'POST',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ provider: 'openai', voice_id: 'nova', text: 'hello there' }),
		});
		expect(result).toBe(blob);
	});

	it('synthesizeSpeech throws a descriptive error when the response is not ok', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 400 }));

		await expect(api.synthesizeSpeech('piper', 'en_US-amy-medium', 'hi')).rejects.toThrow(
			'Request to /api/tts/synthesize failed: 400',
		);
	});

	it('updateSettings surfaces detail message on patch error', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue({
				ok: false,
				status: 422,
				json: async () => ({ detail: [{ msg: 'Value error, SearXNG URL must start with http:// or https://' }] }),
			}),
		);

		await expect(api.updateSettings({ searxng_url: 'searxng.local:8080' })).rejects.toThrow(
			'SearXNG URL must start with http:// or https://',
		);
	});

	it('assistantConfig GETs /api/assistant/config and returns the config', async () => {
		const config = { agent_name: 'Friday' };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => config }));

		const result = await api.assistantConfig();

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/assistant/config', {
			signal: expect.any(AbortSignal),
			credentials: 'include',
		});
		expect(result).toEqual(config);
	});

	it('createSetupAdmin POSTs to /api/setup/admin including include_starter_tiles', async () => {
		const user = { id: 'u1', name: 'Alice', role: 'admin' };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => user }));

		const result = await api.createSetupAdmin('Alice', 'cat.png', '1234', false);

		expect(fetch).toHaveBeenCalledWith('http://api.test/api/setup/admin', {
			signal: expect.any(AbortSignal),
			method: 'POST',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'Alice', avatar: 'cat.png', pin: '1234', include_starter_tiles: false }),
		});
		expect(result).toEqual(user);
	});

	it('apiUrl prepends configured base URL or falls back to relative path', () => {
		expect(apiUrl('/api/widgets')).toBe('http://api.test/api/widgets');
	});
});

describe('describeFetchError', () => {
	it('classifies a TypeError (fetch never reached the server) as network', () => {
		expect(describeFetchError(new TypeError('Failed to fetch'))).toBe('network');
	});

	it('classifies an AbortSignal.timeout() rejection (TimeoutError) as network', () => {
		expect(describeFetchError(new DOMException('signal timed out', 'TimeoutError'))).toBe('network');
	});

	it('classifies a manual AbortController abort (AbortError) as network', () => {
		expect(describeFetchError(new DOMException('The user aborted a request.', 'AbortError'))).toBe('network');
	});

	it('classifies any other DOMException as server', () => {
		expect(describeFetchError(new DOMException('not allowed', 'NotAllowedError'))).toBe('server');
	});

	it('classifies a plain Error as server', () => {
		expect(describeFetchError(new Error('boom'))).toBe('server');
	});
});
