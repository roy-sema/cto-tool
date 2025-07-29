import type { CurrentUserResponse, UpdateCurrentUser } from "@/common/api.d";

export const BASE_URL = import.meta.env.VITE_SITE_DOMAIN || "http://127.0.0.1:8000";

// Source: https://docs.djangoproject.com/en/4.2/howto/csrf/#using-csrf-protection-with-ajax
function getCookie(name: string) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      // Does this cookie string begin with the name we want?
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

const csrftoken = getCookie("csrftoken");

export async function parseApiResponse(response: Response): Promise<any> {
  if (!response.ok) {
    throw new Error(response.statusText);
  }

  return response.json();
}

export async function postJSON(url: string, data: any): Promise<any> {
  return await sendJSONData("POST", url, data);
}

export async function putJSON(url: string, data: any): Promise<any> {
  return await sendJSONData("PUT", url, data);
}

export async function sendJSONData(method: "POST" | "PUT", url: string, data: any): Promise<any> {
  const response = await fetch(url, {
    method: method,
    body: JSON.stringify(data),
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrftoken || "",
    },
    credentials: "include",
  });

  return parseApiResponse(response);
}

export async function sendMultipartFormData(method: "POST" | "PUT", url: string, formData: FormData): Promise<any> {
  const response = await fetch(url, {
    method: method,
    body: formData,
    headers: {
      "X-CSRFToken": csrftoken || "",
    },
    credentials: "include",
  });

  return parseApiResponse(response);
}

export async function getCurrentUser(): Promise<CurrentUserResponse> {
  const url = `${BASE_URL}/api/me/`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function updateCurrentUser(data: UpdateCurrentUser): Promise<CurrentUserResponse> {
  const url = `${BASE_URL}/api/me/`;

  const formData = new FormData();

  formData.append("first_name", data.first_name);
  formData.append("last_name", data.last_name);
  formData.append("email", data.email);
  if (data.initials) {
    formData.append("initials", data.initials);
  }
  if (data.profile_image) {
    formData.append("profile_image", data.profile_image);
  }

  return sendMultipartFormData("PUT", url, formData);
}
