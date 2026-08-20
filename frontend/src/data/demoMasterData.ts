/**
 * Placeholder master-data options until E14 list APIs are available.
 * IDs are arbitrary positive integers accepted by POST /applications.
 */

export type DemoUniversity = {
  id: number
  name: string
  country: string
}

export type DemoProgram = {
  id: number
  name: string
  university_id: number
}

export const DEMO_UNIVERSITIES: DemoUniversity[] = [
  { id: 1, name: 'University of Toronto', country: 'Canada' },
  { id: 2, name: 'University of Melbourne', country: 'Australia' },
  { id: 3, name: 'Arizona State University', country: 'United States' },
]

export const DEMO_PROGRAMS: DemoProgram[] = [
  { id: 10, name: 'MSc Computer Science', university_id: 1 },
  { id: 11, name: 'MBA', university_id: 1 },
  { id: 20, name: 'Master of Engineering', university_id: 2 },
  { id: 21, name: 'Master of Data Science', university_id: 2 },
  { id: 30, name: 'MS Business Analytics', university_id: 3 },
  { id: 31, name: 'MS Information Technology', university_id: 3 },
]

export function programsForUniversity(universityId: number): DemoProgram[] {
  return DEMO_PROGRAMS.filter((program) => program.university_id === universityId)
}
