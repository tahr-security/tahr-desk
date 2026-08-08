import { AxiosError } from "axios"
import type {
  AgentCreate,
  AgentUpdate,
  AssignmentUpdate,
  Body_public_create_case,
  Body_public_create_public_message,
  Body_staff_create_message,
  CaseCredentials,
  ClassificationUpdate,
  ExportCreate,
  ServiceCategoryCreate,
  ServiceCategoryUpdate,
  SiteSettingsUpdate,
  TransitionRequest,
  WebhookCreate,
  WebhookUpdate,
} from "@/client"
import {
  AdminService,
  PublicService,
  StaffService,
  UsersService,
} from "@/client"

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

type GeneratedResponse<T> = { data: T }

function apiError(error: unknown): ApiError {
  if (error instanceof AxiosError) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)
      ?.detail
    return new ApiError(
      typeof detail === "string"
        ? detail
        : "Something went wrong. Please try again.",
      error.response?.status ?? 0,
    )
  }
  return new ApiError("Something went wrong. Please try again.", 0)
}

async function dataOf<T>(
  response: PromiseLike<GeneratedResponse<T>>,
): Promise<T> {
  try {
    return (await response).data
  } catch (error) {
    throw apiError(error)
  }
}

export const api = {
  site: () => dataOf(PublicService.getSite()),
  services: () => dataOf(PublicService.listServices()),
  service: (slug: string) =>
    dataOf(PublicService.getService({ path: { slug } })),
  createCase: (body: Body_public_create_case) =>
    dataOf(PublicService.createCase({ body })),
  lookupCase: (body: CaseCredentials) =>
    dataOf(PublicService.lookupCase({ body })),
  createPublicMessage: (body: Body_public_create_public_message) =>
    dataOf(PublicService.createPublicMessage({ body })),
  me: () => dataOf(UsersService.readUserMe()),
  staff: {
    dashboard: () => dataOf(StaffService.getDashboard()),
    cases: (query?: Parameters<typeof StaffService.listCases>[0]) =>
      dataOf(StaffService.listCases(query)),
    case: (id: string) =>
      dataOf(StaffService.getCase({ path: { case_id: id } })),
    assign: (id: string, version: number, body: AssignmentUpdate) =>
      dataOf(
        StaffService.updateAssignment({
          path: { case_id: id },
          headers: { "if-match": `W/"${version}"` },
          body,
        }),
      ),
    classify: (id: string, version: number, body: ClassificationUpdate) =>
      dataOf(
        StaffService.updateClassification({
          path: { case_id: id },
          headers: { "if-match": `W/"${version}"` },
          body,
        }),
      ),
    transition: (id: string, version: number, body: TransitionRequest) =>
      dataOf(
        StaffService.updateStatus({
          path: { case_id: id },
          headers: { "if-match": `W/"${version}"` },
          body,
        }),
      ),
    message: (id: string, version: number, body: Body_staff_create_message) =>
      dataOf(
        StaffService.createMessage({
          path: { case_id: id },
          headers: { "if-match": `W/"${version}"` },
          body,
        }),
      ),
    exports: () => dataOf(StaffService.listExports()),
    createExport: (body: ExportCreate) =>
      dataOf(StaffService.createExport({ body })),
  },
  admin: {
    agents: () => dataOf(AdminService.listAgents()),
    createAgent: (body: AgentCreate) =>
      dataOf(AdminService.createAgent({ body })),
    updateAgent: (id: string, body: AgentUpdate) =>
      dataOf(AdminService.updateAgent({ path: { user_id: id }, body })),
    resetAgentPassword: (id: string, newPassword: string) =>
      dataOf(
        AdminService.resetAgentPassword({
          path: { user_id: id },
          body: { new_password: newPassword },
        }),
      ),
    site: () => dataOf(AdminService.getSite()),
    updateSite: (body: SiteSettingsUpdate) =>
      dataOf(AdminService.updateSite({ body })),
    services: () => dataOf(AdminService.listServices()),
    createService: (body: ServiceCategoryCreate) =>
      dataOf(AdminService.createService({ body })),
    updateService: (id: string, body: ServiceCategoryUpdate) =>
      dataOf(AdminService.updateService({ path: { service_id: id }, body })),
    webhooks: () => dataOf(AdminService.listWebhooks()),
    createWebhook: (body: WebhookCreate) =>
      dataOf(AdminService.createWebhook({ body })),
    updateWebhook: (id: string, body: WebhookUpdate) =>
      dataOf(AdminService.updateWebhook({ path: { endpoint_id: id }, body })),
  },
}

async function saveDownload(
  response: PromiseLike<GeneratedResponse<unknown>>,
  filename: string,
) {
  try {
    const data = (await response).data
    if (!(data instanceof Blob)) {
      throw new ApiError("The file could not be downloaded.", 0)
    }
    const url = URL.createObjectURL(data)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = filename
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw apiError(error)
  }
}

export const downloadStaffAttachment = (
  attachmentId: string,
  filename: string,
) =>
  saveDownload(
    StaffService.downloadAttachment({
      path: { attachment_id: attachmentId },
      responseType: "blob",
    }),
    filename,
  )

export const downloadExport = (exportId: string, filename: string) =>
  saveDownload(
    StaffService.downloadExport({
      path: { export_id: exportId },
      responseType: "blob",
    }),
    filename,
  )

export async function downloadPublicAttachment(
  credentials: CaseCredentials,
  attachmentId: string,
  filename: string,
) {
  return saveDownload(
    PublicService.downloadAttachment({
      body: { ...credentials, attachment_id: attachmentId },
      responseType: "blob",
    }),
    filename,
  )
}
