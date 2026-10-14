// The endpoint functions against the mock handlers, so both stay in step with the real API.
import {
  getApplication,
  getApplications,
  patchApplication,
  reprintApplication,
} from '@/api/applications'
import { createDevice } from '@/api/devices'
import { getGmailConnectUrl, startSync } from '@/api/gmail'
import { getStatus } from '@/api/status'
import { db } from '@/mocks/db'
import { applicationDetail, applications, status } from '@/mocks/fixtures'

const firstId = applications[0].id
const flagged = applications.find((application) => application.needs_review)!

describe('applications', () => {
  test('lists every application, newest change first', async () => {
    const list = await getApplications()

    expect(list).toHaveLength(9)
    expect(list[0]).toEqual(applications[0])
    expect(list[0]).not.toHaveProperty('emails')
  })

  test('filters by status and needs_review', async () => {
    expect((await getApplications({ status: 'rejected' })).map((a) => a.company)).toEqual([
      'Quillmark',
      'Ferrous Systems',
    ])
    expect(await getApplications({ needs_review: true })).toHaveLength(2)
    expect(await getApplications({ needs_review: false })).toHaveLength(7)
  })

  test('gets one application with its emails and events', async () => {
    await expect(getApplication(firstId)).resolves.toEqual(applicationDetail)
  })

  test('an unknown id is NOT_FOUND', async () => {
    await expect(getApplication('nope')).rejects.toMatchObject({ code: 'NOT_FOUND', status: 404 })
  })

  test('a status change adds a manual event and clears needs_review', async () => {
    const updated = await patchApplication(flagged.id, { status: 'rejected' })

    expect(updated.status).toBe('rejected')
    expect(updated.needs_review).toBe(false)
    expect(updated.status_events[0]).toMatchObject({
      from_status: flagged.status,
      to_status: 'rejected',
      source: 'manual',
      email_id: null,
    })
    expect((await getApplications())[0].id).toBe(flagged.id)
  })

  test('a status change keeps needs_review when the same request sets it', async () => {
    const updated = await patchApplication(firstId, { status: 'update', needs_review: true })

    expect(updated.needs_review).toBe(true)
  })

  test('null clears the role', async () => {
    await expect(patchApplication(firstId, { role: null })).resolves.toMatchObject({ role: null })
  })

  test('reprint queues once, then answers REPRINT_PENDING', async () => {
    await expect(reprintApplication(firstId)).resolves.toEqual({ job_id: expect.any(String) })
    await expect(reprintApplication(firstId)).rejects.toMatchObject({
      code: 'REPRINT_PENDING',
      status: 409,
    })
  })

  test('changes are undone between tests', async () => {
    expect((await getApplication(flagged.id)).needs_review).toBe(true)
    await expect(reprintApplication(firstId)).resolves.toBeDefined()
  })
})

describe('status and misc', () => {
  test('reads the status', async () => {
    await expect(getStatus()).resolves.toEqual(status)
  })

  test('starts a sync', async () => {
    await expect(startSync()).resolves.toEqual({ status: 'started' })
  })

  test('a sync without Gmail is GMAIL_NOT_CONNECTED', async () => {
    db.status.gmail = { state: 'not_connected', address: null }

    await expect(startSync()).rejects.toMatchObject({ code: 'GMAIL_NOT_CONNECTED', status: 409 })
  })

  test('creates a device and returns its key', async () => {
    await expect(createDevice('Desk printer')).resolves.toEqual({
      id: expect.any(String),
      name: 'Desk printer',
      key: expect.stringMatching(/^mock-/),
    })
  })

  test('a blank device name is VALIDATION', async () => {
    await expect(createDevice(' ')).rejects.toMatchObject({ code: 'VALIDATION', status: 422 })
  })

  test('the connect URL points back into the app', async () => {
    await expect(getGmailConnectUrl()).resolves.toEqual({ url: '/?gmail=connected' })
  })
})
