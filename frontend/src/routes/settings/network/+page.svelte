<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, type NetworkIntegration, type NetworkTestConnectionResult } from '$lib/api';
	import ContainerHostRow from '$lib/components/settings/ContainerHostRow.svelte';
	import { user } from '$lib/stores/user';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	let loading = $state(true);
	let loadError = $state<string | null>(null);

	let piholeSettings = $state<Record<string, unknown>>({});
	let piholeHostInput = $state('');
	let piholePortInput = $state(80);
	let piholeUseHttpsInput = $state(false);
	let piholePasswordInput = $state('');
	let piholeSaving = $state(false);
	let piholeError = $state<string | null>(null);
	let piholeTesting = $state(false);
	let piholeTestResult = $state<NetworkTestConnectionResult | null>(null);

	let jellyfinSettings = $state<Record<string, unknown>>({});
	let jellyfinHostInput = $state('');
	let jellyfinPortInput = $state(8096);
	let jellyfinUseHttpsInput = $state(false);
	let jellyfinAuthModeInput = $state<'api_key' | 'password'>('api_key');
	let jellyfinApiKeyInput = $state('');
	let jellyfinUsernameInput = $state('');
	let jellyfinPasswordInput = $state('');
	let jellyfinSaving = $state(false);
	let jellyfinError = $state<string | null>(null);
	let jellyfinTesting = $state(false);
	let jellyfinTestResult = $state<NetworkTestConnectionResult | null>(null);

	let synologySettings = $state<Record<string, unknown>>({});
	let synologyHostInput = $state('');
	let synologyPortInput = $state(5000);
	let synologyUseHttpsInput = $state(false);
	let synologyUsernameInput = $state('');
	let synologyPasswordInput = $state('');
	let synologySaving = $state(false);
	let synologyError = $state<string | null>(null);
	let synologyTesting = $state(false);
	let synologyTestResult = $state<NetworkTestConnectionResult | null>(null);

	let asusSettings = $state<Record<string, unknown>>({});
	let asusHostInput = $state('');
	let asusSshPortInput = $state(22);
	let asusUsernameInput = $state('');
	let asusPasswordInput = $state('');
	let asusSaving = $state(false);
	let asusError = $state<string | null>(null);
	let asusTesting = $state(false);
	let asusTestResult = $state<NetworkTestConnectionResult | null>(null);

	let hdhomerunSettings = $state<Record<string, unknown>>({});
	let hdhomerunTunerHostInput = $state('');
	let hdhomerunTunerPortInput = $state(80);
	let hdhomerunDvrHostInput = $state('');
	let hdhomerunDvrPortInput = $state(59090);
	let hdhomerunEpgUrlInput = $state('');
	let hdhomerunSaving = $state(false);
	let hdhomerunError = $state<string | null>(null);
	let hdhomerunTestingTuner = $state(false);
	let hdhomerunTunerTestResult = $state<NetworkTestConnectionResult | null>(null);
	let hdhomerunTestingDvr = $state(false);
	let hdhomerunDvrTestResult = $state<NetworkTestConnectionResult | null>(null);

	let containerHosts = $state<NetworkIntegration[]>([]);
	let addHostNameInput = $state('');
	let addHostEngineInput = $state<'docker' | 'podman'>('docker');
	let addingHost = $state(false);
	let addHostError = $state<string | null>(null);

	async function loadAll() {
		loading = true;
		loadError = null;
		try {
			const rows = await api.listNetworkIntegrations();

			const pihole = rows.find((r) => r.type === 'pihole');
			piholeSettings = pihole?.settings ?? {};
			piholeHostInput = (piholeSettings.host as string) ?? '';
			piholePortInput = (piholeSettings.port as number) ?? 80;
			piholeUseHttpsInput = (piholeSettings.use_https as boolean) ?? false;

			const jellyfin = rows.find((r) => r.type === 'jellyfin');
			jellyfinSettings = jellyfin?.settings ?? {};
			jellyfinHostInput = (jellyfinSettings.host as string) ?? '';
			jellyfinPortInput = (jellyfinSettings.port as number) ?? 8096;
			jellyfinUseHttpsInput = (jellyfinSettings.use_https as boolean) ?? false;
			jellyfinAuthModeInput = (jellyfinSettings.auth_mode as 'api_key' | 'password') ?? 'api_key';
			jellyfinUsernameInput = (jellyfinSettings.username as string) ?? '';

			const synology = rows.find((r) => r.type === 'synology');
			synologySettings = synology?.settings ?? {};
			synologyHostInput = (synologySettings.host as string) ?? '';
			synologyPortInput = (synologySettings.port as number) ?? 5000;
			synologyUseHttpsInput = (synologySettings.use_https as boolean) ?? false;
			synologyUsernameInput = (synologySettings.username as string) ?? '';

			const asus = rows.find((r) => r.type === 'asus_router');
			asusSettings = asus?.settings ?? {};
			asusHostInput = (asusSettings.host as string) ?? '';
			asusSshPortInput = (asusSettings.ssh_port as number) ?? 22;
			asusUsernameInput = (asusSettings.username as string) ?? '';

			const hdhomerun = rows.find((r) => r.type === 'hdhomerun');
			hdhomerunSettings = hdhomerun?.settings ?? {};
			hdhomerunTunerHostInput = (hdhomerunSettings.tuner_host as string) ?? '';
			hdhomerunTunerPortInput = (hdhomerunSettings.tuner_port as number) ?? 80;
			hdhomerunDvrHostInput = (hdhomerunSettings.dvr_host as string) ?? '';
			hdhomerunDvrPortInput = (hdhomerunSettings.dvr_port as number) ?? 59090;
			hdhomerunEpgUrlInput = (hdhomerunSettings.epg_url as string) ?? '';

			containerHosts = rows.filter((r) => r.type === 'container');
		} catch {
			loadError = get(_)('network_settings.load_error');
		} finally {
			loading = false;
		}
	}

	let initialized = false;
	$effect(() => {
		if ($user?.role === 'admin' && !initialized) {
			initialized = true;
			loadAll();
		} else if ($user && $user.role !== 'admin') {
			loading = false;
		}
	});

	function piholeFormSettings(): Record<string, unknown> {
		const settings: Record<string, unknown> = {
			host: piholeHostInput,
			port: piholePortInput,
			use_https: piholeUseHttpsInput,
		};
		if (piholePasswordInput) settings.password = piholePasswordInput;
		return settings;
	}

	async function testPihole() {
		piholeTesting = true;
		piholeTestResult = null;
		try {
			piholeTestResult = await api.testNetworkIntegrationConnection('pihole', piholeFormSettings());
		} catch {
			piholeTestResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			piholeTesting = false;
		}
	}

	async function savePihole() {
		piholeSaving = true;
		piholeError = null;
		try {
			const updated = await api.updateNetworkIntegration('pihole', piholeFormSettings());
			piholeSettings = updated.settings;
			piholePasswordInput = '';
		} catch {
			piholeError = get(_)('network_settings.save_error');
		} finally {
			piholeSaving = false;
		}
	}

	function jellyfinFormSettings(): Record<string, unknown> {
		const settings: Record<string, unknown> = {
			host: jellyfinHostInput,
			port: jellyfinPortInput,
			use_https: jellyfinUseHttpsInput,
			auth_mode: jellyfinAuthModeInput,
			username: jellyfinUsernameInput,
		};
		if (jellyfinApiKeyInput) settings.api_key = jellyfinApiKeyInput;
		if (jellyfinPasswordInput) settings.password = jellyfinPasswordInput;
		return settings;
	}

	async function testJellyfin() {
		jellyfinTesting = true;
		jellyfinTestResult = null;
		try {
			jellyfinTestResult = await api.testNetworkIntegrationConnection('jellyfin', jellyfinFormSettings());
		} catch {
			jellyfinTestResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			jellyfinTesting = false;
		}
	}

	async function saveJellyfin() {
		jellyfinSaving = true;
		jellyfinError = null;
		try {
			const updated = await api.updateNetworkIntegration('jellyfin', jellyfinFormSettings());
			jellyfinSettings = updated.settings;
			jellyfinApiKeyInput = '';
			jellyfinPasswordInput = '';
		} catch {
			jellyfinError = get(_)('network_settings.save_error');
		} finally {
			jellyfinSaving = false;
		}
	}

	function synologyFormSettings(): Record<string, unknown> {
		const settings: Record<string, unknown> = {
			host: synologyHostInput,
			port: synologyPortInput,
			use_https: synologyUseHttpsInput,
			username: synologyUsernameInput,
		};
		if (synologyPasswordInput) settings.password = synologyPasswordInput;
		return settings;
	}

	async function testSynology() {
		synologyTesting = true;
		synologyTestResult = null;
		try {
			synologyTestResult = await api.testNetworkIntegrationConnection('synology', synologyFormSettings());
		} catch {
			synologyTestResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			synologyTesting = false;
		}
	}

	async function saveSynology() {
		synologySaving = true;
		synologyError = null;
		try {
			const updated = await api.updateNetworkIntegration('synology', synologyFormSettings());
			synologySettings = updated.settings;
			synologyPasswordInput = '';
		} catch {
			synologyError = get(_)('network_settings.save_error');
		} finally {
			synologySaving = false;
		}
	}

	function asusFormSettings(): Record<string, unknown> {
		const settings: Record<string, unknown> = {
			host: asusHostInput,
			ssh_port: asusSshPortInput,
			username: asusUsernameInput,
		};
		if (asusPasswordInput) settings.password = asusPasswordInput;
		return settings;
	}

	async function testAsus() {
		asusTesting = true;
		asusTestResult = null;
		try {
			asusTestResult = await api.testNetworkIntegrationConnection('asus_router', asusFormSettings());
		} catch {
			asusTestResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			asusTesting = false;
		}
	}

	async function saveAsus() {
		asusSaving = true;
		asusError = null;
		try {
			const updated = await api.updateNetworkIntegration('asus_router', asusFormSettings());
			asusSettings = updated.settings;
			asusPasswordInput = '';
		} catch {
			asusError = get(_)('network_settings.save_error');
		} finally {
			asusSaving = false;
		}
	}

	function hdhomerunFormSettings(): Record<string, unknown> {
		return {
			tuner_host: hdhomerunTunerHostInput,
			tuner_port: hdhomerunTunerPortInput,
			dvr_host: hdhomerunDvrHostInput,
			dvr_port: hdhomerunDvrPortInput,
			epg_url: hdhomerunEpgUrlInput,
		};
	}

	async function testHdhomerunTuner() {
		hdhomerunTestingTuner = true;
		hdhomerunTunerTestResult = null;
		try {
			hdhomerunTunerTestResult = await api.testHDHomeRunTunerConnection(hdhomerunFormSettings());
		} catch {
			hdhomerunTunerTestResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			hdhomerunTestingTuner = false;
		}
	}

	async function testHdhomerunDvr() {
		hdhomerunTestingDvr = true;
		hdhomerunDvrTestResult = null;
		try {
			hdhomerunDvrTestResult = await api.testHDHomeRunDvrConnection(hdhomerunFormSettings());
		} catch {
			hdhomerunDvrTestResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			hdhomerunTestingDvr = false;
		}
	}

	async function saveHdhomerun() {
		hdhomerunSaving = true;
		hdhomerunError = null;
		try {
			const updated = await api.updateNetworkIntegration('hdhomerun', hdhomerunFormSettings());
			hdhomerunSettings = updated.settings;
		} catch {
			hdhomerunError = get(_)('network_settings.save_error');
		} finally {
			hdhomerunSaving = false;
		}
	}

	async function addHost() {
		if (!addHostNameInput.trim()) return;
		addingHost = true;
		addHostError = null;
		try {
			const defaults =
				addHostEngineInput === 'docker'
					? { engine: 'docker', connection: 'socket', socket_path: '/var/run/docker.sock', host: '', port: 2375 }
					: { engine: 'podman', connection: 'socket', socket_path: '/run/podman/podman.sock', host: '', port: 8080 };
			const created = await api.createContainerIntegration(addHostNameInput.trim(), defaults);
			containerHosts = [...containerHosts, created];
			addHostNameInput = '';
		} catch {
			addHostError = get(_)('network_settings.add_host_error');
		} finally {
			addingHost = false;
		}
	}

	function onHostUpdated(updated: NetworkIntegration) {
		containerHosts = containerHosts.map((h) => (h.id === updated.id ? updated : h));
	}

	function onHostDeleted(id: string) {
		containerHosts = containerHosts.filter((h) => h.id !== id);
	}
</script>

<div class="settings-page">
	<button class="back" onclick={() => goto('/settings')}>{$_('common.back')}</button>
	<h1>{$_('network_settings.title')}</h1>
	<p class="subtitle">{$_('network_settings.subtitle')}</p>

	{#if $user?.role !== 'admin'}
		<p class="hint">{$_('network_settings.admin_only_hint')}</p>
	{:else if loading}
		<p class="hint">{$_('network_settings.loading')}</p>
	{:else if loadError}
		<p class="hint error">{loadError}</p>
	{:else}
		<section>
			<h3>{$_('network_settings.section_pihole')}</h3>
			<label>
				{$_('pihole.detail.host_label')}
				<input type="text" bind:value={piholeHostInput} placeholder="pi.hole" />
			</label>
			<label>
				{$_('pihole.detail.port_label')}
				<input type="number" min="1" max="65535" bind:value={piholePortInput} />
			</label>
			<label class="checkbox">
				<input type="checkbox" bind:checked={piholeUseHttpsInput} />
				{$_('pihole.detail.use_https_label')}
			</label>
			<label>
				{$_('pihole.detail.password_label')}
				<input
					type="password"
					bind:value={piholePasswordInput}
					placeholder={piholeSettings.has_password ? $_('common.password_set_hint') : $_('common.password_not_set')}
				/>
			</label>

			<div class="test-row">
				<button class="test" disabled={piholeTesting} onclick={testPihole}>
					{piholeTesting ? $_('common.testing') : $_('common.test_connection')}
				</button>
				{#if piholeTestResult}
					{#if piholeTestResult.ok}
						<span class="test-result ok"
							>{$_('network_settings.test_ok', { values: { detail: piholeTestResult.detail } })}</span
						>
					{:else}
						<span class="test-result fail"
							>{$_('network_settings.test_fail', { values: { error: piholeTestResult.error } })}</span
						>
					{/if}
				{/if}
			</div>

			{#if piholeError}
				<p class="hint error">{piholeError}</p>
			{/if}

			<button class="save" disabled={piholeSaving} onclick={savePihole}>
				{piholeSaving ? $_('common.saving') : $_('common.save')}
			</button>
		</section>

		<section>
			<h3>{$_('network_settings.section_jellyfin')}</h3>
			<label>
				{$_('jellyfin.detail.host_label')}
				<input type="text" bind:value={jellyfinHostInput} placeholder="jellyfin.local" />
			</label>
			<label>
				{$_('jellyfin.detail.port_label')}
				<input type="number" min="1" max="65535" bind:value={jellyfinPortInput} />
			</label>
			<label class="checkbox">
				<input type="checkbox" bind:checked={jellyfinUseHttpsInput} />
				{$_('jellyfin.detail.use_https_label')}
			</label>

			<div class="auth-mode">
				<button
					type="button"
					class:active={jellyfinAuthModeInput === 'api_key'}
					onclick={() => (jellyfinAuthModeInput = 'api_key')}
				>
					{$_('jellyfin.detail.auth_mode_api_key')}
				</button>
				<button
					type="button"
					class:active={jellyfinAuthModeInput === 'password'}
					onclick={() => (jellyfinAuthModeInput = 'password')}
				>
					{$_('jellyfin.detail.auth_mode_password')}
				</button>
			</div>

			{#if jellyfinAuthModeInput === 'api_key'}
				<label>
					{$_('jellyfin.detail.auth_mode_api_key')}
					<input
						type="password"
						bind:value={jellyfinApiKeyInput}
						placeholder={jellyfinSettings.has_api_key ? $_('common.password_set_hint') : $_('common.password_not_set')}
					/>
				</label>
			{:else}
				<label>
					{$_('jellyfin.detail.username_label')}
					<input type="text" bind:value={jellyfinUsernameInput} />
				</label>
				<label>
					{$_('jellyfin.detail.password_label')}
					<input
						type="password"
						bind:value={jellyfinPasswordInput}
						placeholder={jellyfinSettings.has_password ? $_('common.password_set_hint') : $_('common.password_not_set')}
					/>
				</label>
			{/if}

			<div class="test-row">
				<button class="test" disabled={jellyfinTesting} onclick={testJellyfin}>
					{jellyfinTesting ? $_('common.testing') : $_('common.test_connection')}
				</button>
				{#if jellyfinTestResult}
					{#if jellyfinTestResult.ok}
						<span class="test-result ok"
							>{$_('network_settings.test_ok', { values: { detail: jellyfinTestResult.detail } })}</span
						>
					{:else}
						<span class="test-result fail"
							>{$_('network_settings.test_fail', { values: { error: jellyfinTestResult.error } })}</span
						>
					{/if}
				{/if}
			</div>

			{#if jellyfinError}
				<p class="hint error">{jellyfinError}</p>
			{/if}

			<button class="save" disabled={jellyfinSaving} onclick={saveJellyfin}>
				{jellyfinSaving ? $_('common.saving') : $_('common.save')}
			</button>
		</section>

		<section>
			<h3>{$_('network_settings.section_synology')}</h3>
			<label>
				{$_('synology.detail.host_label')}
				<input type="text" bind:value={synologyHostInput} placeholder="synology.local" />
			</label>
			<label>
				{$_('synology.detail.port_label')}
				<input type="number" min="1" max="65535" bind:value={synologyPortInput} />
			</label>
			<label class="checkbox">
				<input type="checkbox" bind:checked={synologyUseHttpsInput} />
				{$_('synology.detail.use_https_label')}
			</label>
			<label>
				{$_('synology.detail.username_label')}
				<input type="text" bind:value={synologyUsernameInput} placeholder="admin" />
			</label>
			<label>
				{$_('synology.detail.password_label')}
				<input
					type="password"
					bind:value={synologyPasswordInput}
					placeholder={synologySettings.has_password ? $_('common.password_set_hint') : $_('common.password_not_set')}
				/>
			</label>

			<div class="test-row">
				<button class="test" disabled={synologyTesting} onclick={testSynology}>
					{synologyTesting ? $_('common.testing') : $_('common.test_connection')}
				</button>
				{#if synologyTestResult}
					{#if synologyTestResult.ok}
						<span class="test-result ok"
							>{$_('network_settings.test_ok', { values: { detail: synologyTestResult.detail } })}</span
						>
					{:else}
						<span class="test-result fail"
							>{$_('network_settings.test_fail', { values: { error: synologyTestResult.error } })}</span
						>
					{/if}
				{/if}
			</div>

			{#if synologyError}
				<p class="hint error">{synologyError}</p>
			{/if}

			<button class="save" disabled={synologySaving} onclick={saveSynology}>
				{synologySaving ? $_('common.saving') : $_('common.save')}
			</button>
		</section>

		<section>
			<h3>{$_('network_settings.section_asus_router')}</h3>
			<label>
				{$_('asus_router.detail.host_label')}
				<input type="text" bind:value={asusHostInput} placeholder="router.asus.com" />
			</label>
			<label>
				{$_('asus_router.detail.ssh_port_label')}
				<input type="number" min="1" max="65535" bind:value={asusSshPortInput} />
			</label>
			<label>
				{$_('asus_router.detail.username_label')}
				<input type="text" bind:value={asusUsernameInput} placeholder="admin" />
			</label>
			<label>
				{$_('asus_router.detail.password_label')}
				<input
					type="password"
					bind:value={asusPasswordInput}
					placeholder={asusSettings.has_password ? $_('common.password_set_hint') : $_('common.password_not_set')}
				/>
			</label>

			<div class="test-row">
				<button class="test" disabled={asusTesting} onclick={testAsus}>
					{asusTesting ? $_('common.testing') : $_('common.test_connection')}
				</button>
				{#if asusTestResult}
					{#if asusTestResult.ok}
						<span class="test-result ok"
							>{$_('network_settings.test_ok', { values: { detail: asusTestResult.detail } })}</span
						>
					{:else}
						<span class="test-result fail"
							>{$_('network_settings.test_fail', { values: { error: asusTestResult.error } })}</span
						>
					{/if}
				{/if}
			</div>

			{#if asusError}
				<p class="hint error">{asusError}</p>
			{/if}

			<button class="save" disabled={asusSaving} onclick={saveAsus}>
				{asusSaving ? $_('common.saving') : $_('common.save')}
			</button>
		</section>

		<section>
			<h3>{$_('network_settings.section_hdhomerun')}</h3>
			<h4>{$_('hdhomerun.detail.tuner_heading')}</h4>
			<label>
				{$_('hdhomerun.detail.host_label')}
				<input type="text" bind:value={hdhomerunTunerHostInput} placeholder="hdhomerun.local" />
			</label>
			<label>
				{$_('hdhomerun.detail.port_label')}
				<input type="number" min="1" max="65535" bind:value={hdhomerunTunerPortInput} />
			</label>
			<div class="test-row">
				<button class="test" disabled={hdhomerunTestingTuner} onclick={testHdhomerunTuner}>
					{hdhomerunTestingTuner ? $_('common.testing') : $_('common.test_connection')}
				</button>
				{#if hdhomerunTunerTestResult}
					{#if hdhomerunTunerTestResult.ok}
						<span class="test-result ok"
							>{$_('network_settings.test_ok', { values: { detail: hdhomerunTunerTestResult.detail } })}</span
						>
					{:else}
						<span class="test-result fail"
							>{$_('network_settings.test_fail', { values: { error: hdhomerunTunerTestResult.error } })}</span
						>
					{/if}
				{/if}
			</div>

			<h4>{$_('hdhomerun.detail.guide_heading')} <span class="optional">{$_('hdhomerun.detail.optional')}</span></h4>
			<label>
				{$_('hdhomerun.detail.xmltv_url_label')}
				<input type="text" bind:value={hdhomerunEpgUrlInput} placeholder="http://example.com/guide.xml" />
			</label>
			<p class="hint">{$_('hdhomerun.detail.xmltv_hint')}</p>

			<h4>
				{$_('hdhomerun.detail.dvr_settings_heading')} <span class="optional">{$_('hdhomerun.detail.optional')}</span>
			</h4>
			<label>
				{$_('hdhomerun.detail.host_label')}
				<input type="text" bind:value={hdhomerunDvrHostInput} placeholder="dvr.local" />
			</label>
			<label>
				{$_('hdhomerun.detail.port_label')}
				<input type="number" min="1" max="65535" bind:value={hdhomerunDvrPortInput} />
			</label>
			<div class="test-row">
				<button class="test" disabled={hdhomerunTestingDvr} onclick={testHdhomerunDvr}>
					{hdhomerunTestingDvr ? $_('common.testing') : $_('common.test_connection')}
				</button>
				{#if hdhomerunDvrTestResult}
					{#if hdhomerunDvrTestResult.ok}
						<span class="test-result ok"
							>{$_('network_settings.test_ok', { values: { detail: hdhomerunDvrTestResult.detail } })}</span
						>
					{:else}
						<span class="test-result fail"
							>{$_('network_settings.test_fail', { values: { error: hdhomerunDvrTestResult.error } })}</span
						>
					{/if}
				{/if}
			</div>

			{#if hdhomerunError}
				<p class="hint error">{hdhomerunError}</p>
			{/if}

			<button class="save" disabled={hdhomerunSaving} onclick={saveHdhomerun}>
				{hdhomerunSaving ? $_('common.saving') : $_('common.save')}
			</button>
		</section>

		<section>
			<h3>{$_('network_settings.section_container')}</h3>

			{#if containerHosts.length === 0}
				<p class="hint">{$_('network_settings.no_container_hosts')}</p>
			{:else}
				<div class="host-list">
					{#each containerHosts as host (host.id)}
						<ContainerHostRow {host} onUpdated={onHostUpdated} onDeleted={onHostDeleted} />
					{/each}
				</div>
			{/if}

			<div class="add-host">
				<h4>{$_('network_settings.add_host_heading')}</h4>
				<label>
					{$_('network_settings.host_name_label')}
					<input type="text" bind:value={addHostNameInput} placeholder={$_('network_settings.host_name_placeholder')} />
				</label>
				<label>
					{$_('container.detail.engine_label')}
					<select bind:value={addHostEngineInput}>
						<option value="docker">Docker</option>
						<option value="podman">Podman</option>
					</select>
				</label>
				{#if addHostError}
					<p class="hint error">{addHostError}</p>
				{/if}
				<button class="save" disabled={addingHost || !addHostNameInput.trim()} onclick={addHost}>
					{addingHost ? $_('common.saving') : $_('network_settings.add_host_button')}
				</button>
			</div>
		</section>
	{/if}
</div>

<style>
	.settings-page {
		padding: 2rem;
		min-height: 100vh;
		max-width: 30rem;
	}

	.back {
		background: none;
		border: none;
		font-size: 1.1rem;
		color: var(--color-accent);
		margin-bottom: 1.5rem;
		cursor: pointer;
		padding: 0.5rem 0;
	}

	h1 {
		margin: 0 0 0.25rem;
	}

	.subtitle {
		margin: 0 0 1.5rem;
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	section {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-bottom: 1.5rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem;
	}

	section h3 {
		margin: 0;
		font-size: 1rem;
	}

	section h4 {
		margin: 0.5rem 0 0;
		font-size: 0.9rem;
	}

	section h4:first-of-type {
		margin-top: 0;
	}

	.optional {
		font-weight: normal;
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	label.checkbox {
		flex-direction: row;
		align-items: center;
		gap: 0.5rem;
	}

	input[type='text'],
	input[type='number'],
	input[type='password'],
	select {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.auth-mode {
		display: flex;
		gap: 0.5rem;
	}

	.auth-mode button {
		flex: 1;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.auth-mode button.active {
		border-color: var(--color-accent);
		color: var(--color-accent);
	}

	.test-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.test {
		align-self: flex-start;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.test-result {
		font-size: 0.85rem;
	}

	.test-result.ok {
		color: var(--color-success);
	}

	.test-result.fail {
		color: var(--color-error);
	}

	.save {
		align-self: flex-start;
		background: var(--color-accent);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}

	.host-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.add-host {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		border-top: 1px solid var(--color-border);
		padding-top: 1rem;
	}

	.add-host h4 {
		margin: 0;
		font-size: 0.9rem;
	}
</style>
