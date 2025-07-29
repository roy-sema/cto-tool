export interface BasePaginatedResponse {
  count: number;
  total_pages: number;
  current_page: number;
  next_page: number;
  previous_page: number;
}

export interface CurrentUserResponse {
  initials: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  email: string;
  organization: {
    id: string;
    onboarding_completed: boolean;
  };
  organizations: Record<string, string>;
  profile_image: string;
  profile_image_thumbnail: string;
  hide_environment_banner: boolean;
}

export interface UpdateCurrentUser {
  initials?: string;
  first_name: string;
  last_name: string;
  email: string;
  profile_image?: File;
  profile_image_thumbnail?: File;
}

export interface IntegrationStatusMap {
  [key: string]: {
    status: boolean;
    display_name: string;
  };
}
