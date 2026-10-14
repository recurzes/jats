import type { ApplicationDetail, ApplicationSummary, StatusResponse } from '@/api/types'

// Most recently changed first, like the real list.
export const applications = [
  {
    id: '0b6e1f3a-1c1e-4a51-9a52-6f0d2c8e0001',
    company: 'Northwind Labs',
    role: 'Frontend Engineer',
    status: 'replied',
    needs_review: false,
    last_event_at: '2026-10-13T15:42:00Z',
    last_email_subject: 'Next steps: technical interview',
    last_email_at: '2026-10-13T15:40:00Z',
  },
  {
    id: '0b6e1f3a-1c1e-4a51-9a52-6f0d2c8e0002',
    company: 'Brightline',
    role: 'Software Engineer II',
    status: 'update',
    needs_review: true,
    last_event_at: '2026-10-13T09:10:00Z',
    last_email_subject: 'Your application status',
    last_email_at: '2026-10-13T09:08:00Z',
  },
  {
    id: '0b6e1f3a-1c1e-4a51-9a52-6f0d2c8e0003',
    company: 'Halcyon Health',
    role: 'Full Stack Developer',
    status: 'acknowledged',
    needs_review: false,
    last_event_at: '2026-10-12T18:25:00Z',
    last_email_subject: 'Thanks for applying to Halcyon Health',
    last_email_at: '2026-10-12T18:24:00Z',
  },
  {
    id: '0b6e1f3a-1c1e-4a51-9a52-6f0d2c8e0004',
    company: 'Parcel & Pine',
    role: null,
    status: 'acknowledged',
    needs_review: true,
    last_event_at: '2026-10-12T11:03:00Z',
    last_email_subject: 'We received your application',
    last_email_at: '2026-10-12T11:02:00Z',
  },
  {
    id: '0b6e1f3a-1c1e-4a51-9a52-6f0d2c8e0005',
    company: 'Quillmark',
    role: 'React Developer',
    status: 'rejected',
    needs_review: false,
    last_event_at: '2026-10-11T16:47:00Z',
    last_email_subject: 'Update on your Quillmark application',
    last_email_at: '2026-10-11T16:45:00Z',
  },
  {
    id: '0b6e1f3a-1c1e-4a51-9a52-6f0d2c8e0006',
    company: 'Stackhouse',
    role: 'Junior Web Developer',
    status: 'replied',
    needs_review: false,
    last_event_at: '2026-10-10T13:30:00Z',
    last_email_subject: 'Quick chat this week?',
    last_email_at: '2026-10-10T13:29:00Z',
  },
  {
    id: '0b6e1f3a-1c1e-4a51-9a52-6f0d2c8e0007',
    company: 'Orbital Freight',
    role: 'UI Engineer',
    status: 'update',
    needs_review: false,
    last_event_at: '2026-10-09T08:15:00Z',
    // Changed by hand before any email arrived.
    last_email_subject: null,
    last_email_at: null,
  },
  {
    id: '0b6e1f3a-1c1e-4a51-9a52-6f0d2c8e0008',
    company: 'Lumen Civic',
    role: 'Frontend Developer',
    status: 'acknowledged',
    needs_review: false,
    last_event_at: '2026-10-08T20:05:00Z',
    last_email_subject: 'Application received: Frontend Developer',
    last_email_at: '2026-10-08T20:04:00Z',
  },
  {
    id: '0b6e1f3a-1c1e-4a51-9a52-6f0d2c8e0009',
    company: 'Ferrous Systems',
    role: 'Web Platform Engineer',
    status: 'rejected',
    needs_review: false,
    last_event_at: '2026-10-07T10:50:00Z',
    last_email_subject: 'Regarding your application',
    last_email_at: '2026-10-07T10:49:00Z',
  },
] satisfies ApplicationSummary[]

// The full detail of the first application. Emails and events are newest first.
export const applicationDetail = {
  ...applications[0],
  first_seen_at: '2026-10-02T14:12:00Z',
  emails: [
    {
      id: '5d1c7a90-3f2b-4c8e-8b1a-2e7f9c4d0003',
      subject: 'Next steps: technical interview',
      from_address: 'talent@northwindlabs.example',
      snippet: 'Thanks for chatting with us! We would like to invite you to a technical interview…',
      received_at: '2026-10-13T15:40:00Z',
    },
    {
      id: '5d1c7a90-3f2b-4c8e-8b1a-2e7f9c4d0002',
      subject: 'Intro call with Northwind Labs',
      from_address: 'maria.chen@northwindlabs.example',
      snippet: 'Hi! I am the recruiter for the Frontend Engineer role. Do you have 20 minutes…',
      received_at: '2026-10-06T10:05:00Z',
    },
    {
      id: '5d1c7a90-3f2b-4c8e-8b1a-2e7f9c4d0001',
      subject: 'Thanks for applying to Northwind Labs',
      from_address: 'no-reply@northwindlabs.example',
      snippet: 'We have received your application for Frontend Engineer and will be in touch…',
      received_at: '2026-10-02T14:10:00Z',
    },
  ],
  status_events: [
    {
      id: '9a4e2b17-6c3d-4f5a-a1b2-7d8e9f0a0002',
      from_status: 'acknowledged',
      to_status: 'replied',
      source: 'ai',
      email_id: '5d1c7a90-3f2b-4c8e-8b1a-2e7f9c4d0003',
      created_at: '2026-10-13T15:42:00Z',
    },
    {
      id: '9a4e2b17-6c3d-4f5a-a1b2-7d8e9f0a0001',
      from_status: null,
      to_status: 'acknowledged',
      source: 'ai',
      email_id: '5d1c7a90-3f2b-4c8e-8b1a-2e7f9c4d0001',
      created_at: '2026-10-02T14:12:00Z',
    },
  ],
} satisfies ApplicationDetail

// A healthy pipeline. Later branches add variants for the error states.
export const status = {
  last_sync: {
    started_at: '2026-10-13T15:45:00Z',
    finished_at: '2026-10-13T15:45:06Z',
    result: 'ok',
    trigger: 'schedule',
    error: null,
  },
  gmail: { state: 'ok', address: 'me@example.com' },
  device: { last_seen_at: '2026-10-13T15:46:30Z', online: true },
  queue: { pending: 0, failed: 0 },
  failed_classifications: 0,
} satisfies StatusResponse
