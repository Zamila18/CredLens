/**
 * Short names for the API shapes.
 *
 * schema.d.ts is generated from the running API (`npm run types`, which reads
 * http://localhost:8000/openapi.json). Never edit it by hand: if Humayra changes
 * src/api/schemas.py, run `npm run types` again and the build shows what broke.
 */
import type { components } from './schema'

type S = components['schemas']

export type Health = S['HealthResponse']
export type DataMode = Health['data_mode']
export type QueueItem = S['MerchantQueueItem']
export type MerchantProfile = S['MerchantProfile']
export type TimelineEvent = S['TimelineEvent']
export type Score = S['ScoreResponse']
export type Reason = S['Reason']
export type InputPoints = S['InputPoints']
export type CoverageItem = S['CoverageItem']
export type Band = Score['band']
export type ConsentView = S['ConsentView']
export type ConsentRequest = S['ConsentRequestOut']
export type Decision = S['Decision']
export type DecisionCreate = S['DecisionCreate']
export type OfficerAction = DecisionCreate['officer_action']
export type QuestionnaireCreate = S['QuestionnaireCreate']
export type AuditEntry = S['AuditEntry']
export type ModelCard = S['ModelCard']
export type ImportReport = S['ImportReport']
export type BundleReport = S['BundleReport']

/** The demo users from the API's users table. A demo role switch, not a login. */
export const DEMO_USERS = ['officer-1', 'officer-2', 'admin-1', 'viewer-1'] as const
export type DemoUser = (typeof DEMO_USERS)[number]
export type Role = 'officer' | 'admin' | 'viewer'

/** The role behind each demo user (docs/API_NOTES.md, "Who may call what"). */
export function roleOf(user: DemoUser): Role {
  if (user.startsWith('officer')) return 'officer'
  if (user.startsWith('admin')) return 'admin'
  return 'viewer'
}
