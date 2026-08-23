# Calendar OAuth & Account Integrations

This guide provides step-by-step instructions for setting up OAuth credentials for **Google Calendar** and **Microsoft 365 / Outlook**, as well as configuring standard **CalDAV** servers.

---

## Google Calendar OAuth 2.0 Setup

To connect Google Calendar accounts to Tilora:

### 1. Create a Project in Google Cloud Console
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project named **Tilora Dashboard**.
3. Enable the **Google Calendar API** (*APIs & Services → Library → Search "Google Calendar API" → Enable*).

### 2. Configure OAuth Consent Screen
1. Go to *APIs & Services → OAuth consent screen*.
2. User Type: **External**.
3. App name: `Tilora Dashboard`, User support email: your email.
4. Scopes: Add `.../auth/calendar.readonly` and `.../auth/calendar.events.readonly`.
5. **Audience / Test Users (Crucial)**: In the *Test users* section, add every Google account email address that will connect to Tilora. (For personal use, keeping the app in "Testing" mode with test users is completely free and avoids the complex Google app verification process).

### 3. Create OAuth 2.0 Client ID
1. Go to *APIs & Services → Credentials → Create Credentials → OAuth client ID*.
2. Application type: **Web application**.
3. Name: `Tilora Server`.
4. **Authorized redirect URIs**: Add your backend callback endpoint:
   `http://<your-backend-host>:8000/api/calendar/auth/callback` (e.g. `http://localhost:8000/api/calendar/auth/callback` or `http://192.168.1.50:8000/api/calendar/auth/callback`).
5. Copy the **Client ID** and **Client Secret**.
6. Paste both into **Settings → Admin settings → Google Calendar** in Tilora.

---

## Microsoft 365 / Outlook Setup

To connect Microsoft Outlook or Office 365 calendar accounts:

1. Open the [Microsoft Entra ID (Azure Portal)](https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/RegisteredApps).
2. Go to **App registrations → New registration**.
3. Supported account types: *Accounts in any organizational directory and personal Microsoft accounts*.
4. **Redirect URI**: Web platform → `http://<your-backend-host>:8000/api/calendar/auth/microsoft/callback`.
5. Under **Certificates & secrets**, create a **New client secret**.
6. Under **API permissions**, add `Calendars.Read` (Delegated).
7. Paste the **Application (client) ID** and **Client Secret value** into **Settings → Admin settings → Microsoft 365 Calendar**.

---

## CalDAV Setup (iCloud, Fastmail, Nextcloud)

CalDAV connects directly via standard Basic/Digest credentials:

- **Server URL**:
    - Apple iCloud: `https://caldav.icloud.com`
    - Fastmail: `https://caldav.fastmail.com/dav/calendars/user/your-email@fastmail.com/`
    - Nextcloud: `https://your-nextcloud.domain/remote.php/dav/principals/users/username/`
- **Username**: Your CalDAV account username/email.
- **Password**: An **app-specific password** generated in your provider's security settings (e.g. Apple ID App-Specific Password).
- Enter these in **Settings → Admin settings → CalDAV Calendar**.
