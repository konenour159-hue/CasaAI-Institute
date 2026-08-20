import { api } from "./apiClient";
import type { UserProfile } from "../types/api";

export interface UserProfileUpdateInput {
  profile_type_id: string | null;
  level: string | null;
  career_objectives: string | null;
  goal_ids: string[];
  interest_skill_ids: string[];
}

export const profileService = {
  getMyOnboardingProfile: () => api.get<UserProfile>("/api/me/onboarding-profile", true),
  updateMyOnboardingProfile: (data: UserProfileUpdateInput) =>
    api.put<UserProfile>("/api/me/onboarding-profile", data, true),
};
