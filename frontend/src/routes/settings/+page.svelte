<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { api, type AppSettings, type VersionInfo, type DeviceListEntry, type HouseholdUser } from '$lib/api';
	import { user, logout } from '$lib/stores/user';
	import { device as currentDevice, renameDevice as renameCurrentDevice } from '$lib/stores/device';
	import { reloadWidgets } from '$lib/stores/widgets';

	let settings = $state<AppSettings | null>(null);
	let version = $state<VersionInfo | null>(null);
	let aiModelInput = $state('');
	let timezoneInput = $state('UTC');
	let anthropicKeyInput = $state('');
	let openaiKeyInput = $state('');
	let geminiKeyInput = $state('');
	let googleCalendarClientIdInput = $state('');
	let googleCalendarClientSecretInput = $state('');
	let microsoftCalendarClientIdInput = $state('');
	let microsoftCalendarClientSecretInput = $state('');
	let caldavUrlInput = $state('');
	let caldavUsernameInput = $state('');
	let caldavPasswordInput = $state('');
	let icloudUsernameInput = $state('');
	let icloudPasswordInput = $state('');
	let timezoneOptions = $state<string[]>(['UTC']);
	let saving = $state(false);
	let saved = $state(false);
	let error = $state<string | null>(null);

	// Name/avatar/PIN for the logged-in profile — separate save flow from
	// the app-wide settings above since it hits /api/users/me, not
	// /api/settings.
	let profileNameInput = $state('');
	let profileAvatarInput = $state('');
	let profilePinInput = $state('');
	let profileHasPin = $state(false);
	let profileSaving = $state(false);
	let profileSaved = $state(false);
	let profileError = $state<string | null>(null);
	let confirmingDeleteProfile = $state(false);
	let deletingProfile = $state(false);
	let profileInitialized = false;

	// $user loads asynchronously (see +layout.svelte's gate), so seed these
	// inputs the first time it becomes available rather than in onMount.
	$effect(() => {
		if ($user && !profileInitialized) {
			profileInitialized = true;
			profileNameInput = $user.name;
			profileAvatarInput = $user.avatar ?? '';
			const currentUserId = $user.id;
			api
				.listUsers()
				.then((profiles) => {
					profileHasPin = profiles.find((p) => p.id === currentUserId)?.has_pin ?? false;
				})
				.catch(() => {
					// leave the PIN section assuming no PIN is set
				});
		}
	});

	// /api/settings is admin-only — load it lazily once $user is known to be
	// an admin, mirroring profileInitialized below, so a member never fires a
	// request that's guaranteed to 403.
	let settingsInitialized = false;

	$effect(() => {
		if ($user?.role === 'admin' && !settingsInitialized) {
			settingsInitialized = true;
			loadSettings();
		}
	});

	async function loadSettings() {
		try {
			settings = await api.settings();
			aiModelInput = settings.ai_model;
			timezoneInput = settings.timezone;
			caldavUrlInput = settings.caldav_url;
			caldavUsernameInput = settings.caldav_username;
			icloudUsernameInput = settings.icloud_username;
			if (!timezoneOptions.includes(timezoneInput)) timezoneOptions = [timezoneInput, ...timezoneOptions];
		} catch {
			error = 'Could not load settings.';
		}
	}

	let householdUsers = $state<HouseholdUser[]>([]);
	let householdError = $state<string | null>(null);
	let householdLoading = $state(false);
	let updatingRoleId = $state<string | null>(null);
	let confirmingRemoveId = $state<string | null>(null);
	let removingId = $state<string | null>(null);
	let householdInitialized = false;

	$effect(() => {
		if ($user?.role === 'admin' && !householdInitialized) {
			householdInitialized = true;
			loadHouseholdUsers();
		}
	});

	async function loadHouseholdUsers() {
		householdLoading = true;
		householdError = null;
		try {
			householdUsers = await api.listHouseholdUsers();
		} catch {
			householdError = 'Could not load household members.';
		} finally {
			householdLoading = false;
		}
	}

	async function toggleRole(member: HouseholdUser) {
		const nextRole = member.role === 'admin' ? 'member' : 'admin';
		updatingRoleId = member.id;
		householdError = null;
		try {
			const updated = await api.updateUserRole(member.id, nextRole);
			householdUsers = householdUsers.map((existing) => (existing.id === member.id ? updated : existing));
		} catch {
			householdError = member.role === 'admin' ? "Can't demote the last remaining admin." : 'Could not update role.';
		} finally {
			updatingRoleId = null;
		}
	}

	async function removeMember(id: string) {
		removingId = id;
		householdError = null;
		try {
			await api.removeHouseholdUser(id);
			householdUsers = householdUsers.filter((u) => u.id !== id);
		} catch {
			householdError = 'Could not remove this member.';
		} finally {
			removingId = null;
			confirmingRemoveId = null;
		}
	}

	let devices = $state<DeviceListEntry[]>([]);
	let devicesError = $state<string | null>(null);
	let deviceNameInput = $state('');
	let savingDeviceName = $state(false);
	let confirmingForgetDeviceId = $state<string | null>(null);
	let forgettingDeviceId = $state<string | null>(null);
	let deviceNameInitialized = false;
	let copySourceId = $state('');
	let confirmingCopyLayout = $state(false);
	let copyingLayout = $state(false);
	let copyLayoutError = $state<string | null>(null);

	$effect(() => {
		if ($currentDevice && !deviceNameInitialized) {
			deviceNameInitialized = true;
			deviceNameInput = $currentDevice.name;
		}
	});

	async function loadDevices() {
		try {
			devices = await api.listDevices();
			const firstOther = devices.find((d) => d.id !== $currentDevice?.id);
			if (firstOther) copySourceId = firstOther.id;
		} catch {
			devicesError = 'Could not load devices.';
		}
	}

	onMount(async () => {
		try {
			// Intl.supportedValuesOf isn't in every browser's types yet, but is
			// available in the Chromium the kiosk runs — avoids shipping a
			// hardcoded IANA timezone list.
			const supported = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.(
				'timeZone',
			);
			if (supported?.length) timezoneOptions = supported;
		} catch {
			// keep the UTC-only fallback
		}

		try {
			version = await api.version();
		} catch {
			// leave the update section hidden
		}

		await loadDevices();
	});

	async function save() {
		saving = true;
		saved = false;
		error = null;
		try {
			const partial: Record<string, string> = {
				ai_model: aiModelInput,
				timezone: timezoneInput,
				caldav_url: caldavUrlInput,
				caldav_username: caldavUsernameInput,
				icloud_username: icloudUsernameInput,
			};
			if (anthropicKeyInput) partial.anthropic_api_key = anthropicKeyInput;
			if (openaiKeyInput) partial.openai_api_key = openaiKeyInput;
			if (geminiKeyInput) partial.gemini_api_key = geminiKeyInput;
			if (googleCalendarClientIdInput) partial.google_calendar_client_id = googleCalendarClientIdInput;
			if (googleCalendarClientSecretInput) partial.google_calendar_client_secret = googleCalendarClientSecretInput;
			if (microsoftCalendarClientIdInput) partial.microsoft_calendar_client_id = microsoftCalendarClientIdInput;
			if (microsoftCalendarClientSecretInput)
				partial.microsoft_calendar_client_secret = microsoftCalendarClientSecretInput;
			if (caldavPasswordInput) partial.caldav_password = caldavPasswordInput;
			if (icloudPasswordInput) partial.icloud_password = icloudPasswordInput;

			settings = await api.updateSettings(partial);
			anthropicKeyInput = '';
			openaiKeyInput = '';
			geminiKeyInput = '';
			googleCalendarClientIdInput = '';
			googleCalendarClientSecretInput = '';
			microsoftCalendarClientIdInput = '';
			microsoftCalendarClientSecretInput = '';
			caldavPasswordInput = '';
			icloudPasswordInput = '';
			saved = true;
		} catch {
			error = 'Could not save settings.';
		} finally {
			saving = false;
		}
	}

	async function clearKey(
		key:
			| 'anthropic_api_key'
			| 'openai_api_key'
			| 'gemini_api_key'
			| 'google_calendar_client_id'
			| 'google_calendar_client_secret'
			| 'microsoft_calendar_client_id'
			| 'microsoft_calendar_client_secret'
			| 'caldav_password'
			| 'icloud_password',
	) {
		error = null;
		try {
			settings = await api.updateSettings({ [key]: '' });
		} catch {
			error = 'Could not clear the key.';
		}
	}

	async function saveProfile() {
		if (profilePinInput && !/^\d{4,8}$/.test(profilePinInput)) {
			profileError = 'PIN must be 4-8 digits.';
			return;
		}
		profileSaving = true;
		profileSaved = false;
		profileError = null;
		try {
			const partial: { name?: string; avatar?: string; pin?: string } = {
				name: profileNameInput.trim(),
				avatar: profileAvatarInput.trim(),
			};
			if (profilePinInput) partial.pin = profilePinInput;
			const updated = await api.updateUser(partial);
			user.set(updated);
			if (profilePinInput) profileHasPin = true;
			profilePinInput = '';
			profileSaved = true;
		} catch {
			profileError = 'Could not save profile.';
		} finally {
			profileSaving = false;
		}
	}

	async function clearPin() {
		profileError = null;
		try {
			const updated = await api.updateUser({ pin: '' });
			user.set(updated);
			profileHasPin = false;
		} catch {
			profileError = 'Could not clear PIN.';
		}
	}

	async function deleteProfile() {
		deletingProfile = true;
		profileError = null;
		try {
			await api.deleteUser();
			await logout().catch(() => {});
			goto('/login');
		} catch {
			profileError = 'Could not delete profile — it may be the only one left.';
			deletingProfile = false;
			confirmingDeleteProfile = false;
		}
	}

	async function saveDeviceName() {
		savingDeviceName = true;
		devicesError = null;
		try {
			await renameCurrentDevice(deviceNameInput.trim());
			await loadDevices();
		} catch {
			devicesError = 'Could not rename device.';
		} finally {
			savingDeviceName = false;
		}
	}

	async function forgetDevice(id: string) {
		forgettingDeviceId = id;
		devicesError = null;
		try {
			await api.deleteDevice(id);
			devices = devices.filter((d) => d.id !== id);
		} catch {
			devicesError = 'Could not forget device.';
		} finally {
			forgettingDeviceId = null;
			confirmingForgetDeviceId = null;
		}
	}

	async function copyLayout() {
		if (!copySourceId) return;
		copyingLayout = true;
		copyLayoutError = null;
		try {
			await api.copyDeviceLayout(copySourceId);
			await reloadWidgets();
			confirmingCopyLayout = false;
		} catch {
			copyLayoutError = 'Could not copy layout.';
		} finally {
			copyingLayout = false;
		}
	}
</script>

<div class="settings-page">
	<button class="back" onclick={() => goto('/')}>← Back</button>
	<h1>Settings</h1>

	{#if $user?.role === 'admin'}
		<div class="settings-group">
			<h2 class="group-title">Admin settings</h2>
			<p class="group-subtitle">Shared across the whole household — visible only to admins.</p>

			<section>
				<h3>Household members</h3>
				{#if householdError}
					<p class="hint error">{householdError}</p>
				{/if}
				{#if householdLoading && householdUsers.length === 0}
					<p class="hint">Loading…</p>
				{:else}
					<ul class="member-list">
						{#each householdUsers as member (member.id)}
							<li>
								<span class="member-info">
									<span class="avatar-sm">{member.avatar || member.name.charAt(0).toUpperCase()}</span>
									<span class="member-name">{member.name}</span>
									<span class="role-badge" class:admin={member.role === 'admin'}>{member.role}</span>
								</span>
								{#if member.id === $user.id}
									<span class="hint">(you)</span>
								{:else}
									<span class="member-actions">
										<button class="clear" onclick={() => toggleRole(member)} disabled={updatingRoleId === member.id}>
											{member.role === 'admin' ? 'Demote to member' : 'Promote to admin'}
										</button>
										{#if confirmingRemoveId === member.id}
											<span class="confirm-actions">
												<button
													class="cancel"
													onclick={() => (confirmingRemoveId = null)}
													disabled={removingId === member.id}
												>
													Cancel
												</button>
												<button
													class="danger"
													onclick={() => removeMember(member.id)}
													disabled={removingId === member.id}
												>
													{removingId === member.id ? 'Removing…' : 'Remove'}
												</button>
											</span>
										{:else}
											<button class="danger-link" onclick={() => (confirmingRemoveId = member.id)}>Remove</button>
										{/if}
									</span>
								{/if}
							</li>
						{/each}
					</ul>
				{/if}
			</section>

			{#if !settings}
				<p class="hint">{error ?? 'Loading…'}</p>
			{:else}
				<section>
					<h3>AI provider</h3>
					<label>
						Model
						<input type="text" bind:value={aiModelInput} placeholder="anthropic/claude-sonnet-5" />
					</label>
					<p class="hint">
						Follows litellm's "&lt;provider&gt;/&lt;model&gt;" convention, e.g. anthropic/claude-sonnet-5, openai/gpt-5,
						or gemini/gemini-2.5-flash.
					</p>

					<label>
						Anthropic API key
						<input
							type="password"
							bind:value={anthropicKeyInput}
							placeholder={settings.has_anthropic_api_key ? 'Set — enter a new value to replace it' : 'Not set'}
						/>
					</label>
					{#if settings.has_anthropic_api_key}
						<button class="clear" onclick={() => clearKey('anthropic_api_key')}>Clear key</button>
					{/if}

					<label>
						OpenAI API key
						<input
							type="password"
							bind:value={openaiKeyInput}
							placeholder={settings.has_openai_api_key ? 'Set — enter a new value to replace it' : 'Not set'}
						/>
					</label>
					{#if settings.has_openai_api_key}
						<button class="clear" onclick={() => clearKey('openai_api_key')}>Clear key</button>
					{/if}

					<label>
						Gemini API key
						<input
							type="password"
							bind:value={geminiKeyInput}
							placeholder={settings.has_gemini_api_key ? 'Set — enter a new value to replace it' : 'Not set'}
						/>
					</label>
					{#if settings.has_gemini_api_key}
						<button class="clear" onclick={() => clearKey('gemini_api_key')}>Clear key</button>
					{/if}
				</section>

				<section>
					<h3>Google Calendar</h3>
					<label>
						Client ID
						<input
							type="password"
							bind:value={googleCalendarClientIdInput}
							placeholder={settings.has_google_calendar_client_id ? 'Set — enter a new value to replace it' : 'Not set'}
						/>
					</label>
					{#if settings.has_google_calendar_client_id}
						<button class="clear" onclick={() => clearKey('google_calendar_client_id')}> Clear client ID </button>
					{/if}

					<label>
						Client secret
						<input
							type="password"
							bind:value={googleCalendarClientSecretInput}
							placeholder={settings.has_google_calendar_client_secret
								? 'Set — enter a new value to replace it'
								: 'Not set'}
						/>
					</label>
					{#if settings.has_google_calendar_client_secret}
						<button class="clear" onclick={() => clearKey('google_calendar_client_secret')}>
							Clear client secret
						</button>
					{/if}
					<p class="hint">
						From an OAuth 2.0 Client ID (console.cloud.google.com). Once saved, connect your account from the Calendar
						widget's detail view.
					</p>
				</section>

				<section>
					<h3>Microsoft 365 Calendar</h3>
					<label>
						Client ID
						<input
							type="password"
							bind:value={microsoftCalendarClientIdInput}
							placeholder={settings.has_microsoft_calendar_client_id
								? 'Set — enter a new value to replace it'
								: 'Not set'}
						/>
					</label>
					{#if settings.has_microsoft_calendar_client_id}
						<button class="clear" onclick={() => clearKey('microsoft_calendar_client_id')}> Clear client ID </button>
					{/if}

					<label>
						Client secret
						<input
							type="password"
							bind:value={microsoftCalendarClientSecretInput}
							placeholder={settings.has_microsoft_calendar_client_secret
								? 'Set — enter a new value to replace it'
								: 'Not set'}
						/>
					</label>
					{#if settings.has_microsoft_calendar_client_secret}
						<button class="clear" onclick={() => clearKey('microsoft_calendar_client_secret')}>
							Clear client secret
						</button>
					{/if}
					<p class="hint">
						From an app registration (portal.azure.com -> Microsoft Entra ID -> App registrations). Once saved, connect
						your account from a Calendar widget's detail view whose
						<code>provider</code> is <code>microsoft</code>.
					</p>
				</section>

				<section>
					<h3>CalDAV Calendar</h3>
					<label>
						Server URL
						<input type="text" bind:value={caldavUrlInput} placeholder="https://caldav.icloud.com" />
					</label>

					<label>
						Username
						<input type="text" bind:value={caldavUsernameInput} />
					</label>

					<label>
						Password
						<input
							type="password"
							bind:value={caldavPasswordInput}
							placeholder={settings.has_caldav_password ? 'Set — enter a new value to replace it' : 'Not set'}
						/>
					</label>
					{#if settings.has_caldav_password}
						<button class="clear" onclick={() => clearKey('caldav_password')}>Clear password</button>
					{/if}
					<p class="hint">
						Works with iCloud, Fastmail, Nextcloud, and most self-hosted calendars — usually an app-specific password
						rather than your account password. Set a calendar widget's
						<code>provider</code> to <code>caldav</code> in <code>dashboard.yaml</code> to use it.
					</p>
				</section>

				<section>
					<h3>iCloud Photos</h3>
					<label>
						Apple ID
						<input type="text" bind:value={icloudUsernameInput} />
					</label>

					<label>
						Password
						<input
							type="password"
							bind:value={icloudPasswordInput}
							placeholder={settings.has_icloud_password ? 'Set — enter a new value to replace it' : 'Not set'}
						/>
					</label>
					{#if settings.has_icloud_password}
						<button class="clear" onclick={() => clearKey('icloud_password')}>Clear password</button>
					{/if}
					<p class="hint">
						Your real Apple ID and account password (Apple doesn't support app-specific passwords here), so this grants
						full account access, not just Photos — only fill this in if you're comfortable with that. Set a photos
						widget's <code>provider</code>
						to
						<code>icloud_private</code> in <code>dashboard.yaml</code>, save this section, then connect (including any
						2FA prompt) from that widget's detail view.
					</p>
				</section>

				<section>
					<h3>Timezone</h3>
					<label>
						Used by the clock and date widgets
						<select bind:value={timezoneInput}>
							{#each timezoneOptions as tz (tz)}
								<option value={tz}>{tz}</option>
							{/each}
						</select>
					</label>
				</section>

				{#if error}
					<p class="hint error">{error}</p>
				{/if}
				{#if saved}
					<p class="hint">Saved.</p>
				{/if}

				<button class="save" disabled={saving} onclick={save}>
					{saving ? 'Saving…' : 'Save'}
				</button>
			{/if}
		</div>
	{/if}

	<div class="settings-group">
		<h2 class="group-title">Your settings</h2>
		<p class="group-subtitle">Specific to your profile on this device.</p>

		<section>
			<h3>Profile</h3>
			<label>
				Name
				<input type="text" bind:value={profileNameInput} maxlength="40" />
			</label>
			<label>
				Avatar (emoji, optional)
				<input type="text" bind:value={profileAvatarInput} placeholder="🐱" maxlength="8" />
			</label>
			<label>
				PIN
				<input
					type="password"
					inputmode="numeric"
					bind:value={profilePinInput}
					placeholder={profileHasPin ? 'Set — enter a new value to replace it' : 'Not set — optional'}
					maxlength="8"
				/>
			</label>
			{#if profileHasPin}
				<button class="clear" onclick={clearPin}>Clear PIN</button>
			{/if}
			{#if profileError}
				<p class="hint error">{profileError}</p>
			{/if}
			{#if profileSaved}
				<p class="hint">Saved.</p>
			{/if}
			<button class="save" disabled={profileSaving || !profileNameInput.trim()} onclick={saveProfile}>
				{profileSaving ? 'Saving…' : 'Save profile'}
			</button>

			{#if confirmingDeleteProfile}
				<p class="hint error">Delete this profile? Its layout and preferences on every device are lost.</p>
				<div class="confirm-actions">
					<button class="cancel" onclick={() => (confirmingDeleteProfile = false)} disabled={deletingProfile}>
						Cancel
					</button>
					<button class="danger" onclick={deleteProfile} disabled={deletingProfile}>
						{deletingProfile ? 'Deleting…' : 'Delete profile'}
					</button>
				</div>
			{:else}
				<button class="danger-link" onclick={() => (confirmingDeleteProfile = true)}>Delete this profile</button>
			{/if}
		</section>

		<section>
			<h3>Devices</h3>
			{#if $currentDevice}
				<label>
					This device
					<input type="text" bind:value={deviceNameInput} maxlength="40" />
				</label>
				<button class="save" disabled={savingDeviceName || !deviceNameInput.trim()} onclick={saveDeviceName}>
					{savingDeviceName ? 'Saving…' : 'Rename this device'}
				</button>
			{/if}

			{#if devicesError}
				<p class="hint error">{devicesError}</p>
			{/if}

			{#if devices.filter((d) => d.id !== $currentDevice?.id).length > 0}
				<ul class="device-list">
					{#each devices.filter((d) => d.id !== $currentDevice?.id) as d (d.id)}
						<li>
							<span class="device-name">{d.name}</span>
							{#if confirmingForgetDeviceId === d.id}
								<span class="confirm-actions">
									<button
										class="cancel"
										onclick={() => (confirmingForgetDeviceId = null)}
										disabled={forgettingDeviceId === d.id}
									>
										Cancel
									</button>
									<button class="danger" onclick={() => forgetDevice(d.id)} disabled={forgettingDeviceId === d.id}>
										{forgettingDeviceId === d.id ? 'Forgetting…' : 'Forget'}
									</button>
								</span>
							{:else}
								<button class="danger-link" onclick={() => (confirmingForgetDeviceId = d.id)}>Forget device</button>
							{/if}
						</li>
					{/each}
				</ul>

				<label>
					Copy layout from another device
					<select bind:value={copySourceId}>
						{#each devices.filter((d) => d.id !== $currentDevice?.id) as d (d.id)}
							<option value={d.id}>{d.name}</option>
						{/each}
					</select>
				</label>

				{#if copyLayoutError}
					<p class="hint error">{copyLayoutError}</p>
				{/if}

				{#if confirmingCopyLayout}
					<p class="hint error">
						This will replace your layout on {$currentDevice?.name} with your layout from {devices.find(
							(d) => d.id === copySourceId,
						)?.name}. This can't be undone.
					</p>
					<div class="confirm-actions">
						<button class="cancel" onclick={() => (confirmingCopyLayout = false)} disabled={copyingLayout}>
							Cancel
						</button>
						<button class="danger" onclick={copyLayout} disabled={copyingLayout}>
							{copyingLayout ? 'Copying…' : 'Copy layout'}
						</button>
					</div>
				{:else}
					<button class="danger-link" disabled={!copySourceId} onclick={() => (confirmingCopyLayout = true)}>
						Copy layout to this device…
					</button>
				{/if}
			{/if}
		</section>

		{#if version}
			<section>
				<h3>Software update</h3>
				<p class="hint">Running version {version.current_version}.</p>
				{#if version.update_available}
					<p class="hint">
						Update available: v{version.latest_version}
						{#if version.release_url}
							— <a href={version.release_url} target="_blank" rel="noreferrer">view release</a>
						{/if}
					</p>
				{/if}
			</section>
		{/if}
	</div>
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
		margin: 0 0 1.5rem;
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

	.settings-group {
		margin-bottom: 2rem;
	}

	.group-title {
		margin: 0 0 0.25rem;
		font-size: 1.2rem;
	}

	.group-subtitle {
		margin: 0 0 1rem;
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

	input,
	select {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.clear {
		align-self: flex-start;
		background: none;
		border: none;
		color: var(--color-text-muted);
		text-decoration: underline;
		cursor: pointer;
		padding: 0;
		font-size: 0.85rem;
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

	.save:disabled,
	.danger:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.danger-link {
		align-self: flex-start;
		background: none;
		border: none;
		color: var(--color-error);
		text-decoration: underline;
		cursor: pointer;
		padding: 0;
		font-size: 0.85rem;
	}

	.confirm-actions {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.confirm-actions .cancel {
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		padding: 0;
		font-size: 0.85rem;
	}

	.danger {
		background: var(--color-error);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		cursor: pointer;
		font-size: 0.85rem;
	}

	.device-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.device-list li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.device-name {
		font-size: 0.9rem;
	}

	.member-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.member-list li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.member-info {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.avatar-sm {
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		background: var(--color-surface-hover, var(--color-border));
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1rem;
	}

	.member-name {
		font-size: 0.9rem;
	}

	.role-badge {
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-text-muted);
		border: 1px solid var(--color-border);
		border-radius: 999px;
		padding: 0.1rem 0.5rem;
	}

	.role-badge.admin {
		color: var(--color-accent);
		border-color: var(--color-accent);
	}

	.member-actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.hint a {
		color: var(--color-accent);
	}

	.hint {
		color: var(--color-text-muted);
		margin: 0.25rem 0 0;
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
