import { PublicClientApplication, type Configuration } from '@azure/msal-browser';

const clientId = import.meta.env.VITE_AZURE_CLIENT_ID as string | undefined;
const tenantId = import.meta.env.VITE_AZURE_TENANT_ID as string | undefined;

export const msalEnabled = Boolean(clientId && tenantId);

const config: Configuration | null = msalEnabled
  ? {
      auth: {
        clientId: clientId!,
        authority: `https://login.microsoftonline.com/${tenantId}`,
        redirectUri: window.location.origin,
      },
      cache: {
        cacheLocation: 'sessionStorage',
      },
    }
  : null;

export const msalInstance = config ? new PublicClientApplication(config) : null;

export const loginRequest = {
  scopes: clientId ? [`api://${clientId}/access_as_user`] : [],
};
