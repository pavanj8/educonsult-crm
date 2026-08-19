/** Return Authorization headers for API requests (JWT verification wired in E5). */
export function makeAuthHeaders(accessToken = 'test-access-token'): Record<string, string> {
  return { Authorization: `Bearer ${accessToken}` }
}
