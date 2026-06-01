# Credentials Setup Guide

## Connecting Microsoft Entra ID, SharePoint, and Azure OpenAI to the Platform

> **When to use this guide:** You have received your Microsoft 365 / Azure credentials and want to move the platform from dev-mode (stub SharePoint, local LLM) to a fully wired production-ready state.
>
> **Time required:** ~45–60 minutes end-to-end.
>
> **Prerequisites:** Access to the Azure Portal as a Global Administrator or Application Administrator, an active Microsoft 365 tenant with SharePoint, and an Azure OpenAI resource with a deployed model.

---

## Table of Contents

- [Step 1 — Register the App in Entra ID](#step-1--register-the-app-in-entra-id)
- [Step 2 — Add API Permissions](#step-2--add-api-permissions)
- [Step 3 — Define App Roles](#step-3--define-app-roles)
- [Step 4 — Find Your SharePoint SiteId and DriveId](#step-4--find-your-sharepoint-siteid-and-driveid)
- [Step 5 — Get Azure OpenAI Credentials](#step-5--get-azure-openai-credentials)
- [Step 6 — Fill In the Backend Configuration](#step-6--fill-in-the-backend-configuration)
- [Step 7 — Fill In the Docker Env File](#step-7--fill-in-the-docker-env-file)
- [Step 8 — Wire the Real GraphServiceClient in the Backend](#step-8--wire-the-real-graphserviceclient-in-the-backend)
- [Step 9 — Wire MSAL in the Frontend](#step-9--wire-msal-in-the-frontend)
- [Step 10 — Generate the First EF Core Migration](#step-10--generate-the-first-ef-core-migration)
- [Step 11 — Start a Tunnel and Activate Webhooks](#step-11--start-a-tunnel-and-activate-webhooks)
- [Step 12 — Build and Run](#step-12--build-and-run)
- [Step 13 — Verify Everything Works](#step-13--verify-everything-works)
- [Credentials Reference Card](#credentials-reference-card)

---

## Step 1 — Register the App in Entra ID

Go to **portal.azure.com → Microsoft Entra ID → App registrations → New registration**.

| Field | Value |
|---|---|
| Name | `Sothema Compliance Platform` |
| Supported account types | Accounts in this organizational directory only |
| Redirect URI | `http://localhost:5173` *(type: SPA)* for development — add your production URL later |

Click **Register**.

After creation, stay on the app overview page and note down these three values — you will need them throughout this guide:

| Value | Where it appears |
|---|---|
| **Tenant ID** | Overview page — "Directory (tenant) ID" |
| **Client ID** | Overview page — "Application (client) ID" |
| **Client Secret** | Go to **Certificates & secrets → New client secret**, set expiry 24 months, click Add, then **copy the Value immediately** — it is only shown once |

---

## Step 2 — Add API Permissions

Still on the app registration → **API permissions → Add a permission → Microsoft Graph → Application permissions**.

Add the following two permissions:

| Permission | Purpose |
|---|---|
| `Sites.Read.All` | Read SharePoint site metadata and search |
| `Files.Read.All` | Download document content **and** create change-notification subscriptions for sync |

> [!NOTE]
> `Files.Read.All` is sufficient for both reading files and creating Graph drive subscriptions. `Files.ReadWrite.All` is **not needed** and must not be added — the platform never writes to SharePoint.

After adding both permissions, click **Grant admin consent for [your organisation]**.

Both permissions must show a green tick under the Status column before continuing.

---

## Step 3 — Define App Roles

Still on the app registration → **App roles → Create app role**.

Create the following three roles exactly as shown. The **Value** field must match exactly — the backend authorization policies check for these exact strings.

| Display name | Value | Allowed member types | Description |
|---|---|---|---|
| Admin | `Admin` | Users/Groups | Full platform access |
| Analyst | `Analyst` | Users/Groups | Can trigger analyses |
| Viewer | `Viewer` | Users/Groups | Read-only access |

After creating all three roles, assign yourself the Admin role:

Go to **Enterprise applications → [your app name] → Users and groups → Add user/group**, select your account, and assign the `Admin` role.

---

## Step 4 — Find Your SharePoint SiteId and DriveId

You need the internal Graph API identifiers for the SharePoint site and document library you want to synchronise. The easiest way is via **Graph Explorer** (graph.microsoft.com/graph-explorer) — sign in with your Microsoft 365 account.

**Get the SiteId:**

```
GET https://graph.microsoft.com/v1.0/sites?search=<your-site-name>
```

In the response, find your site and copy the full `id` field. It has this format:

```
yourtenant.sharepoint.com,xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx,yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy
```

**Get the DriveId:**

```
GET https://graph.microsoft.com/v1.0/sites/<SiteId>/drives
```

In the response, find the document library you want to sync (usually named `Documents`). Copy its `id` field — that is the DriveId.

---

## Step 5 — Get Azure OpenAI Credentials

In **portal.azure.com → Azure OpenAI → your resource → Overview**:

- Copy the **Endpoint** URL — format: `https://your-resource.openai.azure.com/`
- Go to **Keys and Endpoint** and copy **Key 1**

**Deploy a chat model:**

Go to **Azure OpenAI Studio → Deployments → Create new deployment**:

| Field | Value |
|---|---|
| Model | `gpt-4o` or `gpt-4o-mini` |
| Deployment name | Choose any name, e.g. `gpt-4o` — you will paste this exact string into the config |

Note the deployment name — it is not the model name, it is the label you chose.

---

## Step 6 — Fill In the Backend Configuration

Open [`backend-dotnet-api/src/Sothema.Compliance.Api/appsettings.json`](../backend-dotnet-api/src/Sothema.Compliance.Api/appsettings.json) and replace the placeholder values:

```jsonc
{
  "UseDevAuth": false,                        // ← Change from true to false

  "AzureAd": {
    "Instance": "https://login.microsoftonline.com/",
    "TenantId": "<Tenant ID from Step 1>",
    "ClientId": "<Client ID from Step 1>",
    "Audience": "api://<Client ID from Step 1>"
  },

  "MicrosoftGraph": {
    "BaseUrl": "https://graph.microsoft.com/v1.0",
    "Scopes": "https://graph.microsoft.com/.default"
  },

  "SharePoint": {
    "TenantName": "<yourtenant>.sharepoint.com",
    "DefaultSiteId": "<SiteId from Step 4>"
  },

  "SharePointSync": {
    "Enabled": true,
    "SiteId": "<SiteId from Step 4>",
    "DriveId": "<DriveId from Step 4>",
    "PollingIntervalMinutes": 20,
    "BatchSize": 5,
    "BatchDelayMilliseconds": 2000,
    "WebhookClientState": "<generate a random GUID — run: uuidgen>",
    "WebhookBaseUrl": "https://<your-tunnel-url>",   // ← Fill in after Step 11
    "SubscriptionLifetimeDays": 29,
    "RenewalThresholdHours": 48
  }
}
```

> [!IMPORTANT]
> **Do not put the Client Secret in `appsettings.json`** — it would be committed to source control. Use .NET user-secrets instead:
>
> ```bash
> cd backend-dotnet-api
> dotnet user-secrets set "AzureAd:ClientSecret" "<your client secret from Step 1>" \
>   --project src/Sothema.Compliance.Api
> ```
>
> The `UserSecretsId` is already configured in `Sothema.Compliance.Api.csproj`.

---

## Step 7 — Fill In the Docker Env File

Open [`docker/.env`](../docker/.env) (create it from `.env.example` if it does not exist: `cp docker/.env.example docker/.env`):

```env
# SQL Server
SA_PASSWORD=YourStrong!Passw0rd

# AI Service shared key — must match on both backend and ai-service
# Generate with: openssl rand -hex 32
AI_SERVICE_API_KEY=<strong random string>

# LLM Provider — switch to azure now that you have credentials
LLM_PROVIDER=azure

# Azure OpenAI (from Step 5)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=<API key from Step 5>
AZURE_OPENAI_API_VERSION=2024-06-01
AZURE_OPENAI_CHAT_DEPLOYMENT=<deployment name from Step 5>
```

Leave the `GROQ_*` and `OLLAMA_*` lines in place — they are ignored when `LLM_PROVIDER=azure`.

---

## Step 8 — Wire the Real GraphServiceClient in the Backend

This is the only code change required in the backend. Two files need to be updated.

### 8a — Add the missing NuGet packages

```bash
cd backend-dotnet-api

dotnet add src/Sothema.Compliance.Infrastructure \
  package Microsoft.Identity.Web.MicrosoftGraph

dotnet add src/Sothema.Compliance.Api \
  package Microsoft.Identity.Web
```

### 8b — Update `Program.cs`

Open [`backend-dotnet-api/src/Sothema.Compliance.Api/Program.cs`](../backend-dotnet-api/src/Sothema.Compliance.Api/Program.cs).

Find the production JWT bearer block (the `else` branch, around line 38) and replace it:

```csharp
// Remove this:
builder.Services.AddAuthentication()
    .AddJwtBearer(options =>
    {
        var azureAd = builder.Configuration.GetSection("AzureAd");
        options.Authority = $"{azureAd["Instance"]}{azureAd["TenantId"]}/v2.0";
        options.Audience = azureAd["ClientId"];
    });

// Replace with this:
builder.Services.AddMicrosoftIdentityWebApiAuthentication(builder.Configuration)
    .EnableTokenAcquisitionToCallDownstreamApi()
    .AddMicrosoftGraph(builder.Configuration.GetSection("MicrosoftGraph"))
    .AddInMemoryTokenCaches();
```

Also add the using at the top of the file if not already present:

```csharp
using Microsoft.Identity.Web;
```

### 8c — Activate the real `SharePointService` in `DependencyInjection.cs`

Open [`backend-dotnet-api/src/Sothema.Compliance.Infrastructure/DependencyInjection.cs`](../backend-dotnet-api/src/Sothema.Compliance.Infrastructure/DependencyInjection.cs).

Find the `else` branch around line 54 and replace it:

```csharp
// Remove this:
else
{
    services.AddSingleton<ISharePointService, StubSharePointService>();
    // TODO: Replace with real SharePointService when credentials are available
    // services.AddScoped<ISharePointService, SharePointService>();
}

// Replace with this:
else
{
    services.AddScoped<ISharePointService, SharePointService>();
}
```

The `GraphServiceClient` is injected automatically by `AddMicrosoftGraph()` registered in `Program.cs` — no extra wiring is needed.

### 8d — Rebuild to confirm zero errors

```bash
cd backend-dotnet-api
dotnet build Sothema.Compliance.sln
```

Expected: `Build succeeded. 0 Warning(s) 0 Error(s)`.

---

## Step 9 — Wire MSAL in the Frontend

The frontend `AuthContext.tsx` currently uses a mock user from localStorage. These changes replace it with a real Microsoft login flow.

### 9a — Install MSAL packages

```bash
cd frontend-web
npm install @azure/msal-browser @azure/msal-react
```

### 9b — Update the frontend environment file

Open [`frontend-web/.env.development`](../frontend-web/.env.development) and add the two new variables:

```env
VITE_API_BASE_URL=http://localhost:5000
VITE_USE_MOCK=false
VITE_AZURE_CLIENT_ID=<Client ID from Step 1>
VITE_AZURE_TENANT_ID=<Tenant ID from Step 1>
```

### 9c — Create the MSAL configuration file

Create a new file `frontend-web/src/auth/msalConfig.ts`:

```ts
import { PublicClientApplication, type Configuration } from '@azure/msal-browser';

export const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AZURE_TENANT_ID}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);

export const loginRequest = {
  scopes: [`api://${import.meta.env.VITE_AZURE_CLIENT_ID}/access_as_user`],
};
```

### 9d — Replace `AuthContext.tsx` with the real MSAL implementation

Replace the contents of [`frontend-web/src/context/AuthContext.tsx`](../frontend-web/src/context/AuthContext.tsx):

```tsx
import { createContext, useEffect, useState, type ReactNode } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import type { User, UserRole } from '@/types';
import { loginRequest } from '@/auth/msalConfig';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  login: () => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  login: async () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!isAuthenticated || accounts.length === 0) {
      setUser(null);
      return;
    }

    const account = accounts[0];

    // Acquire a token silently and fetch the user profile from the backend.
    instance
      .acquireTokenSilent({ ...loginRequest, account })
      .then((result) => {
        localStorage.setItem('auth_token', result.accessToken);
        return fetch('/api/users/me', {
          headers: { Authorization: `Bearer ${result.accessToken}` },
        });
      })
      .then((res) => res.json())
      .then((profile) => setUser(profile))
      .catch(() => setUser(null));
  }, [isAuthenticated, accounts, instance]);

  const login = async () => {
    await instance.loginPopup(loginRequest);
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    instance.logoutPopup();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
```

### 9e — Wrap `main.tsx` with the MSAL provider

Open [`frontend-web/src/main.tsx`](../frontend-web/src/main.tsx) and wrap the app:

```tsx
import { MsalProvider } from '@azure/msal-react';
import { msalInstance } from '@/auth/msalConfig';

// Initialise MSAL before rendering
await msalInstance.initialize();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MsalProvider instance={msalInstance}>
      <App />
    </MsalProvider>
  </React.StrictMode>
);
```

---

## Step 10 — Generate the First EF Core Migration

The current dev setup uses `EnsureCreated()` which works but cannot evolve the schema. Create a proper migration so staging and production databases can be updated incrementally.

```bash
cd backend-dotnet-api

# Install EF tools if not already installed
dotnet tool install --global dotnet-ef

# Create the migration (generates files in Infrastructure/Migrations/)
dotnet ef migrations add InitialCreate \
  --project src/Sothema.Compliance.Infrastructure \
  --startup-project src/Sothema.Compliance.Api

# Apply the migration to your SQL Server database
dotnet ef database update \
  --project src/Sothema.Compliance.Infrastructure \
  --startup-project src/Sothema.Compliance.Api
```

Expected output: `Done.` and a new `Migrations/` directory with the generated files.

> [!NOTE]
> After this step, remove the `db.Database.EnsureCreated()` call from `Program.cs` (the `if (app.Environment.IsDevelopment())` block) — migrations now own schema creation.

---

## Step 11 — Start a Tunnel and Activate Webhooks

Microsoft Graph needs to POST change notifications to a **publicly reachable HTTPS URL**. Use Azure Dev Tunnels (recommended — no session expiry, official Microsoft tool):

```bash
# Install once (requires the Azure CLI or standalone installer)
winget install Microsoft.devtunnel     # Windows
brew install --cask devtunnel          # macOS

# Log in
devtunnel login

# Expose your local backend — run this in a dedicated terminal and keep it open
devtunnel host -p 5000 --allow-anonymous
```

The command prints a URL like `https://abc123-5000.devtunnels.ms`. Copy that URL.

Go back to [`appsettings.json`](../backend-dotnet-api/src/Sothema.Compliance.Api/appsettings.json) and paste it into the `SharePointSync:WebhookBaseUrl` field you left blank in Step 6:

```json
"WebhookBaseUrl": "https://abc123-5000.devtunnels.ms"
```

When the backend starts, `SubscriptionRenewalService` will automatically call Graph to create the change-notification subscription using this URL. Verify it worked by looking for this line in the startup logs:

```
SubscriptionRenewalService: created subscription {SubId} (expires {Expiry})
```

> [!NOTE]
> For a cloud deployment (Azure Container Apps, App Service, etc.) no tunnel is needed — use the app's public HTTPS URL directly as `WebhookBaseUrl`.

---

## Step 12 — Build and Run

### Option A — Docker Compose (all services together, recommended)

```bash
docker compose -f docker/docker-compose.yml up --build
```

Services will be available at:

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API + Swagger | http://localhost:5000/swagger |
| AI Service + docs | http://localhost:8000/docs |
| SQL Server | localhost:1433 |

### Option B — Local processes (faster iteration during development)

Run each in its own terminal:

```bash
# Terminal 1 — Backend API
cd backend-dotnet-api
dotnet run --project src/Sothema.Compliance.Api

# Terminal 2 — AI Service
cd ai-service-python
uvicorn app.main:app --reload --port 8000

# Terminal 3 — Frontend
cd frontend-web
npm run dev
```

---

## Step 13 — Verify Everything Works

Run through these checks in order. Each one builds on the previous.

| # | Check | How | Expected result |
|---|---|---|---|
| 1 | Backend is healthy | `GET http://localhost:5000/api/health` | `200 OK` `{"Status":"Healthy"}` |
| 2 | AI service is healthy | `GET http://localhost:8000/api/health` | `200 OK` with FAISS/BM25/DB status |
| 3 | Entra ID login | Click Login in the frontend, complete the Microsoft popup | User name and role appear in the top bar |
| 4 | JWT is sent | Browser DevTools → Network → any API call → check `Authorization: Bearer <token>` header is present | Token present, no 401 responses |
| 5 | SharePoint search | Documents page → search for a term that exists in your library | Results returned from real SharePoint |
| 6 | Document ingestion | Click a document → Ingest | `TextSegment` rows appear in SQL: `SELECT COUNT(*) FROM TextSegments` |
| 7 | Compliance analysis | Document detail page → Analyse | Analysis job created, status transitions `Pending → Processing → Completed`, score appears |
| 8 | Chat / RAG | Chat page → ask a compliance question | Answer cites real document chunks from your SharePoint library |
| 9 | Webhook subscription | Check startup logs | `SubscriptionRenewalService: created subscription ...` |
| 10 | Live sync | Upload a new PDF to your SharePoint document library | Within ~30 seconds: new `Document` row and `TextSegment` rows in SQL; new document appears in search |
| 11 | Modify sync | Edit and save a document in SharePoint | Old segments deleted, new segments created (segment count may change); search returns new content |
| 12 | Delete sync | Delete a document from SharePoint | `Document` row and all `TextSegment` rows removed; document no longer appears in search |

---

## Credentials Reference Card

Keep this table filled in somewhere secure (a password manager, Azure Key Vault, etc.). **Never commit secrets to source control.**

| Credential | Where you got it | Where it is used |
|---|---|---|
| **Tenant ID** | Entra ID app overview | `appsettings.json → AzureAd:TenantId` and `frontend/.env → VITE_AZURE_TENANT_ID` |
| **Client ID** | Entra ID app overview | `appsettings.json → AzureAd:ClientId` and `frontend/.env → VITE_AZURE_CLIENT_ID` |
| **Client Secret** | Entra ID → Certificates & secrets | .NET user-secrets `AzureAd:ClientSecret` only — never in any file |
| **SharePoint SiteId** | Graph Explorer `GET /sites` | `appsettings.json → SharePoint:DefaultSiteId` and `SharePointSync:SiteId` |
| **SharePoint DriveId** | Graph Explorer `GET /sites/{id}/drives` | `appsettings.json → SharePointSync:DriveId` |
| **Azure OpenAI Endpoint** | Azure OpenAI resource overview | `docker/.env → AZURE_OPENAI_ENDPOINT` |
| **Azure OpenAI API Key** | Azure OpenAI resource → Keys | `docker/.env → AZURE_OPENAI_API_KEY` |
| **Model deployment name** | Azure OpenAI Studio → Deployments | `docker/.env → AZURE_OPENAI_CHAT_DEPLOYMENT` |
| **WebhookClientState** | Generated by you (`uuidgen`) | `appsettings.json → SharePointSync:WebhookClientState` — treat as a secret |
| **AI_SERVICE_API_KEY** | Generated by you (`openssl rand -hex 32`) | `docker/.env` — shared between backend and AI service containers |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `401 Unauthorized` on all API calls | `UseDevAuth` still `true` in `appsettings.Development.json`, or the MSAL token is not being sent | Set `UseDevAuth: false`; check the `Authorization` header in browser DevTools |
| `403 Forbidden` on `/api/documents` | User account not assigned an App Role in Entra ID | Go to Enterprise applications → Users and groups and assign the Admin or Analyst role |
| Graph search returns empty results | API permissions not granted admin consent | Go to API permissions and click Grant admin consent |
| `SharePointService` throws `ServiceException` | `GraphServiceClient` not registered — `AddMicrosoftGraph` not called in `Program.cs` | Confirm Step 8b was applied and the new packages are installed |
| Webhook subscription not created | `WebhookBaseUrl` is empty or not publicly reachable | Confirm the tunnel is running (Step 11) and the URL is pasted into `appsettings.json` |
| AI service `502` on analysis | Azure OpenAI deployment name is wrong | Check `AZURE_OPENAI_CHAT_DEPLOYMENT` in `docker/.env` matches the exact deployment name in Azure OpenAI Studio |
| EF migration fails | `EnsureCreated()` already ran and created the schema without migration history | Drop and recreate the database, then run `dotnet ef database update` |
