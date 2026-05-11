import os
import msal
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
TENANT_ID = os.getenv("TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["Files.ReadWrite.All", "User.Read", "offline_access"]

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


class OneDriveAuth:
    def __init__(self):
        self.app = msal.PublicClientApplication(
            client_id=CLIENT_ID,
            authority=AUTHORITY,
        )
        self._token = None

    def get_token(self):
        if self._token:
            return self._token

        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(SCOPES, account=accounts[0])
            if result and "access_token" in result:
                self._token = result["access_token"]
                return self._token

        return None

    def is_authenticated(self):
        return self.get_token() is not None

    def login(self):
        flow = self.app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise Exception(f"Failed to create device flow: {flow}")

        return flow

    def complete_login(self, flow):
        result = self.app.acquire_token_by_device_flow(flow)
        if "access_token" in result:
            self._token = result["access_token"]
            return True
        raise Exception(f"Login failed: {result.get('error_description', result.get('error', 'Unknown error'))}")

    def get_headers(self):
        token = self.get_token()
        if not token:
            raise Exception("Not authenticated. Please log in first.")
        return {"Authorization": f"Bearer {token}"}

    def get_user_info(self):
        headers = self.get_headers()
        resp = requests.get(f"{GRAPH_API_ENDPOINT}/me", headers=headers)
        resp.raise_for_status()
        return resp.json()

    def graph_get(self, url):
        headers = self.get_headers()
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def graph_patch(self, url, data):
        headers = self.get_headers()
        headers["Content-Type"] = "application/json"
        resp = requests.patch(url, headers=headers, json=data)
        resp.raise_for_status()
        return resp.json()

    def graph_delete(self, url):
        headers = self.get_headers()
        resp = requests.delete(url, headers=headers)
        resp.raise_for_status()
        return resp
